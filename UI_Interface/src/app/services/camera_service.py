"""
File Name       : camera_service.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-04
Last Modified   : 2026-02-04

Description:
This service provides camera frames for the web UI.
In this stage, it serves a snapshot image (JPEG) using OpenCV VideoCapture.
Later, it can be extended to MJPEG streaming.
Camera service with DEMO and REAL modes.
- DEMO mode: Uses PC webcam (index 0)
- REAL mode: Uses Raspberry Pi Camera Module
"""

import cv2

class CameraService:
    def __init__(self, demo_mode: bool = True, device_index: int = 0):
        self.demo_mode = demo_mode
        self.device_index = device_index
        self.cap = None
        print(f"[CAMERA] Initialized in {'DEMO' if demo_mode else 'REAL'} mode")

    def open(self) -> bool:
        """Open the camera device."""
        if self.cap is not None:
            return True
        
        # demo:
        if self.demo_mode:
            cap = cv2.VideoCapture(self.device_index, cv2.CAP_DSHOW)
        else:
            # real: raspberry pi camera (picamera2 ???)
            cap = cv2.VideoCapture(self.device_index)
        
        if not cap.isOpened():
            print(f"[CAMERA] Failed to open camera at index {self.device_index}")
            return False
        
        self.cap = cap
        print(f"[CAMERA] Camera opened successfully at index {self.device_index}")
        return True
    

    def close(self) -> None:
        """Release camera device."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            print("[CAMERA] Camera closed")


    def get_jpeg(self) -> bytes | None:
        """Capture one frame and return it as JPEG bytes."""
        if self.cap is None and not self.open():
            return None

        ok, frame = self.cap.read()

        if not ok or frame is None:
            print("[CAMERA] Failed to read frame")
            return None
        
        # jpeg'e donusturme
        ok2, buf = cv2.imencode(".jpg", frame)
        if not ok2:
            print("[CAMERA] Failed to encode frame")
            return None
        
        return buf.tobytes()


camera_service = None


def init_camera_service(demo_mode: bool, device_index: int = 0):
    """Initialize camera service singleton"""
    global camera_service
    camera_service = CameraService(demo_mode=demo_mode, device_index=device_index)
    return camera_service
