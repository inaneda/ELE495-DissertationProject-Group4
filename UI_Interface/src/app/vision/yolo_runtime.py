"""
File Name       : yolo_runtime.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-25
Last Modified   : 2026-02-27

Description:
YOLO-style ONNX inference runtime.
Provides a single source of truth for model loading, preprocessing, postprocessing,
and detection output parsing. Designed to be reused by both backend services
(VisionService) and standalone debug scripts.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Dict

import cv2
import numpy as np

try:
    import onnxruntime as ort
except Exception:
    ort = None


@dataclass
class Detection:
    box: List[int]       # [x1,y1,x2,y2]
    score: float
    class_id: int


class YoloRuntime:
    """
    YOLO-style ONNX runtime (based on inference2.py logic).
    - preprocess: resize->RGB->normalize->CHW
    - postprocess: obj_conf * class_score
    """

    def __init__(
        self,
        model_path: str,
        imgsz: int = 640,
        conf_thres: float = 0.5,
        providers: Optional[List[str]] = None,
        class_names: Optional[Dict[int, str]] = None,
    ):
        self.model_path = model_path
        self.imgsz = int(imgsz)
        self.conf_thres = float(conf_thres)
        self.class_names = class_names or {0: "resistor", 1: "diode"}

        self.session = None
        self.input_name = None

        if ort is None:
            print("[YOLO_RUNTIME] onnxruntime not available.")
            return

        if not os.path.exists(self.model_path):
            print(f"[YOLO_RUNTIME] Model not found: {self.model_path}")
            return

        if providers is None:
            providers = ["CPUExecutionProvider"]

        self.session = ort.InferenceSession(self.model_path, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        print(f"[YOLO_RUNTIME] Loaded model: {self.model_path}")

    def is_ready(self) -> bool:
        return self.session is not None and self.input_name is not None

    def preprocess(self, frame_bgr: np.ndarray) -> np.ndarray:
        img = cv2.resize(frame_bgr, (self.imgsz, self.imgsz))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))[None]  # 1x3x640x640
        return img

    def postprocess(self, outputs, orig_shape_hw) -> List[Detection]:
        # inference2.py: outputs[0][0]  -> (num_boxes, 85)
        preds = outputs[0][0]

        h, w = orig_shape_hw
        dets: List[Detection] = []

        for pred in preds:
            obj_conf = float(pred[4])
            class_scores = pred[5:]
            cls_id = int(np.argmax(class_scores))
            score = obj_conf * float(class_scores[cls_id])  # YOLO stili bu sekilde

            if score < self.conf_thres:
                continue

            cx, cy, bw, bh = pred[:4]

            x1 = int((cx - bw / 2) * w / self.imgsz)
            y1 = int((cy - bh / 2) * h / self.imgsz)
            x2 = int((cx + bw / 2) * w / self.imgsz)
            y2 = int((cy + bh / 2) * h / self.imgsz)

            # clamp
            x1 = max(0, min(w - 1, x1))
            y1 = max(0, min(h - 1, y1))
            x2 = max(0, min(w - 1, x2))
            y2 = max(0, min(h - 1, y2))

            dets.append(Detection([x1, y1, x2, y2], float(score), cls_id))

        dets.sort(key=lambda d: d.score, reverse=True)
        return dets

    def detect(self, frame_bgr: np.ndarray) -> List[Detection]:
        if not self.is_ready():
            return []

        inp = self.preprocess(frame_bgr)
        outputs = self.session.run(None, {self.input_name: inp})
        h, w = frame_bgr.shape[:2]
        return self.postprocess(outputs, (h, w))