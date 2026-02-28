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

import os
from typing import List, Optional

import cv2
import numpy as np

from src.app.vision.yolo_runtime import YoloRuntime, Detection

class VisionService:
    def __init__(
        self,
        model_path: str,
        conf_thres: float = 0.6,
        imgsz: int = 640,
        class_names: Optional[dict[int, str]] = None,
    ):
        self.model_path = model_path
        self.conf_thres = float(conf_thres)
        self.imgsz = int(imgsz)
        self.class_names = class_names or {0: "resistor", 1: "diode"}

        # gercek tek inference kaynagi
        self.runtime = YoloRuntime(
            model_path=self.model_path,
            imgsz=self.imgsz,
            conf_thres=self.conf_thres,
            class_names=self.class_names,
        )
        # self.session = None
        # self.input_name = None


    def is_ready(self) -> bool:
        return self.runtime is not None and self.runtime.is_ready()


    def detect(self, frame_bgr: np.ndarray) -> List[Detection]:
        if not self.is_ready():
            return []
        return self.runtime.detect(frame_bgr)
    

    def draw_overlay(self, frame_bgr: np.ndarray, dets: List[Detection]) -> np.ndarray:
        out = frame_bgr.copy()
        for d in dets:
            x1, y1, x2, y2 = d.box
            name = self.class_names.get(d.class_id, f"id{d.class_id}")
            cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                out,
                f"{name} {d.score:.2f}",
                (x1, max(15, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
            )
        return out


vision_service = None


def init_vision_service():
    global vision_service
    model_path = os.environ.get("PNP_VISION_MODEL", "src/app/vision/best.onnx")
    conf = float(os.environ.get("PNP_VISION_CONF", "0.6"))
    vision_service = VisionService(model_path=model_path, conf_thres=conf)
    return vision_service

# !!!!! model degistirirsek inference2.py ile vision_service.py dikkat et
# inference2 kendi onnx kodu var, vision_service runtime