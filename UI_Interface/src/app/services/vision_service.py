"""
File Name       : vision_service.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-25
Last Modified   : 2026-02-25

Description:
This service provides camera frames for the web UI.
In this stage, it serves a snapshot image (JPEG) using OpenCV VideoCapture.
Later, it can be extended to MJPEG streaming.
Camera service with DEMO and REAL modes.
- DEMO mode: Uses PC webcam (index 0)
- REAL mode: Uses Raspberry Pi Camera Module
"""
from __future__ import annotations

import os
from typing import List, Optional

import cv2
import numpy as np

try:
    import onnxruntime as ort
except Exception:
    ort = None


class VisionService:
    def __init__(
        self,
        model_path: str,
        conf_thres: float = 0.7,
        imgsz: int = 640,
    ):
        self.model_path = model_path
        self.imgsz = int(imgsz)
        self.conf_thres = float(conf_thres)

        self.session = None
        self.input_name = None
        self.class_names = {0: "resistor", 1: "diode"}

        if ort is None:
            print("[VISION] onnxruntime not available")
            return

        if not os.path.exists(self.model_path):
            print(f"[VISION] Model not found: {self.model_path}")
            return

        self.session = ort.InferenceSession(
            self.model_path,
            providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name
        print(f"[VISION] Model loaded: {self.model_path}")


    def is_ready(self) -> bool:
        return self.session is not None and self.input_name is not None

    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        self.orig_h, self.orig_w = frame.shape[:2]

        img = cv2.resize(frame, (self.imgsz, self.imgsz))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))
        img = np.expand_dims(img, axis=0)
        return img

    def postprocess(self, outputs):
        preds = outputs[0][0].T

        boxes = []
        scores = []
        class_ids = []

        for p in preds:
            cx, cy, w, h = p[:4]
            class_scores = p[4:]

            cls = int(np.argmax(class_scores))
            conf = float(class_scores[cls])

            if conf < self.conf_thres:
                continue

            x1 = int((cx - w / 2) * self.orig_w / self.imgsz)
            y1 = int((cy - h / 2) * self.orig_h / self.imgsz)
            x2 = int((cx + w / 2) * self.orig_w / self.imgsz)
            y2 = int((cy + h / 2) * self.orig_h / self.imgsz)

            boxes.append([x1, y1, x2, y2])
            scores.append(conf)
            class_ids.append(cls)

        return boxes, scores, class_ids


    def detect(self, frame: np.ndarray):
        if not self.is_ready():
            return [], [], []
        inp = self.preprocess(frame)
        outputs = self.session.run(None, {self.input_name: inp})  # only once
        return self.postprocess(outputs)
    
    def compute_iou(self, boxA, boxB) -> float:
        if boxB is None:
            return 0.0

        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        inter = max(0, xB - xA) * max(0, yB - yA)
        areaA = max(0, boxA[2] - boxA[0]) * max(0, boxA[3] - boxA[1])
        areaB = max(0, boxB[2] - boxB[0]) * max(0, boxB[3] - boxB[1])

        union = areaA + areaB - inter
        return inter / union if union > 0 else 0.0

    def score_target(self, target_box, detected_boxes):
        best_iou = 0.0
        best_box = None

        for box in detected_boxes:
            iou = self.compute_iou(target_box, box)
            if iou > best_iou:
                best_iou = iou
                best_box = box

        return {
            "target_box": target_box,
            "matched_box": best_box,
            "iou": best_iou,
            "accuracy": best_iou * 100.0,
            "error": 100.0 * (1.0 - best_iou),
        }

    

    def summarize_detection(self, boxes, scores, class_ids):
        if not boxes:
            return {
                "component": None,
                "type": None,
                "confidence": None,
            }

        top_box = boxes[0]
        top_score = scores[0]
        top_cls = class_ids[0]
        top_name = self.class_names.get(top_cls, f"id{top_cls}")

        return {
            "component": top_name.upper(),
            "type": top_name,
            "confidence": float(top_score),
            "box": top_box,
        }

    def draw_overlay(self, frame, boxes, scores, class_ids, target_box=None, score_result=None):
        out = frame.copy()
        for box, score, cls in zip(boxes, scores, class_ids):
            cv2.rectangle(out, box[:2], box[2:], (0, 255, 0), 2)
            cv2.putText(
                out,
                f"ID:{cls} {score:.2f}",
                (box[0], max(15, box[1] - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1
            )

        if target_box is not None:
            tx1, ty1, tx2, ty2 = target_box
            cv2.rectangle(out, (tx1, ty1), (tx2, ty2), (255, 0, 0), 2)
            cv2.putText(
                out,
                "TARGET",
                (tx1, max(15, ty1 - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 0, 0),
                1
            )

        if score_result is not None and target_box is not None:
            tx1, ty1, _, _ = target_box
            cv2.putText(
                out,
                f"IoU:{score_result['iou']:.3f}  Acc:{score_result['accuracy']:.1f}%  Err:{score_result['error']:.1f}%",
                (tx1 + 5, ty1 + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 255, 255),
                1
            )

        return out


vision_service = None


def init_vision_service():
    global vision_service
    model_path = os.environ.get("PNP_VISION_MODEL", "src/app/vision/best.onnx")
    conf = float(os.environ.get("PNP_VISION_CONF", "0.7"))
    vision_service = VisionService(model_path=model_path, conf_thres=conf)
    return vision_service

# !!!!! model degistirirsek inference2.py ile vision_service.py dikkat et
# inference2 kendi onnx kodu var, vision_service runtime