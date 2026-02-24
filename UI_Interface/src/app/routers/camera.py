"""
File Name       : camera.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-04
Last Modified   : 2026-02-04

Description:
This router provides camera endpoints for the web UI.
Currently supports a snapshot endpoint returning a JPEG image.
"""

from fastapi import APIRouter, Response
import src.app.services.camera_service as cam_mod
from src.app.routers.status import SYSTEM_STATE

from fastapi import HTTPException, Query
from src.app.core.config import API_KEY

router = APIRouter(
    prefix="/api", 
    tags=["Camera"],
)

def _get_cam():
    # init unutulduysa bile crash etmesin
    if cam_mod.camera_service is None:
        return None
    return cam_mod.camera_service


def _set_camera_conn(status: bool):
    # baglanti: {"status": bool, "port": str|None}
    cam = SYSTEM_STATE["connections"].get("camera")
    if not isinstance(cam, dict):
        SYSTEM_STATE["connections"]["camera"] = {"status": False, "port": None}

    SYSTEM_STATE["connections"]["camera"]["status"] = bool(status)

    # port: demo’da index yazalım, real’da da aynı
    svc = _get_cam()
    if svc is not None:
        SYSTEM_STATE["connections"]["camera"]["port"] = f"index {getattr(svc, 'device_index', 0)}"
    else:
        SYSTEM_STATE["connections"]["camera"]["port"] = None

@router.get("/camera/snapshot")
def snapshot(token: str = Query(default="")):
    if token != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    svc = _get_cam()
    if svc is None:
        _set_camera_conn(False)
        raise HTTPException(status_code=503, detail="Camera service not initialized")

    jpg = svc.get_jpeg()
    if jpg is None:
        _set_camera_conn(False)
        return Response(content=b"", status_code=503)

    _set_camera_conn(True)
    return Response(content=jpg, media_type="image/jpeg")

@router.post("/camera/restart")
def restart_camera():
    # restart endpoint
    try:
        svc = _get_cam()
        if svc is None:
            _set_camera_conn(False)
            raise HTTPException(status_code=503, detail="Camera service not initialized")

        svc.close()
        ok = svc.open()
        _set_camera_conn(ok)

        if not ok:
            raise HTTPException(status_code=503, detail="Camera restart failed")

        return {"ok": True}

    except HTTPException:
        raise
    except Exception as e:
        _set_camera_conn(False)
        raise HTTPException(status_code=500, detail=f"Camera restart error: {e}")