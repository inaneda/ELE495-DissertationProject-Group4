"""
File Name       : camera_service.py
Author          : Eda
Project         : ELE 496 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-04
Last Modified   : 2026-02-04

Description:
This service provides camera frames for the web UI.
In this stage, it serves a snapshot image (JPEG) using OpenCV VideoCapture.
Later, it can be extended to MJPEG streaming.
"""

import cv2


class CameraService:
    def __init__(self, device_index: int = 0):
        self.device_index = device_index
        self.cap = None

    def open(self) -> bool:
        """Open the camera device."""
        if self.cap is not None:
            return True
        cap = cv2.VideoCapture(self.device_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            return False
        self.cap = cap

        print("Opening camera index:", self.device_index)
        print("isOpened:", cap.isOpened())
        return True
    

    def close(self) -> None:
        """Release camera device."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def get_jpeg(self) -> bytes | None:
        """Capture one frame and return it as JPEG bytes."""
        if self.cap is None and not self.open():
            return None

        ok, frame = self.cap.read()
        if not ok or frame is None:
            return None

        ok2, buf = cv2.imencode(".jpg", frame)
        if not ok2:
            return None
        
        print("Reading frame...")
        ok, frame = self.cap.read()
        print("read ok:", ok, "frame is None:", frame is None)

        return buf.tobytes()


camera_service = CameraService(device_index=0)
