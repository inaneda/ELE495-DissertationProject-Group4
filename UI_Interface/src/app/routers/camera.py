"""
File Name       : camera.py
Author          : Eda
Project         : ELE 496 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-04
Last Modified   : 2026-02-04

Description:
This router provides camera endpoints for the web UI.
Currently supports a snapshot endpoint returning a JPEG image.
"""

from fastapi import APIRouter, Response
from src.app.services.camera_service import camera_service
from src.app.routers.status import SYSTEM_STATE

router = APIRouter(prefix="/api", tags=["Camera"])


@router.get("/camera/snapshot")
def camera_snapshot():
    jpg = camera_service.get_jpeg()
    if jpg is None:
        # Kamera yoksa bağlantıyı false yap
        SYSTEM_STATE["connections"]["camera"] = False
        return Response(content=b"", status_code=503)

    SYSTEM_STATE["connections"]["camera"] = True
    return Response(content=jpg, media_type="image/jpeg")
