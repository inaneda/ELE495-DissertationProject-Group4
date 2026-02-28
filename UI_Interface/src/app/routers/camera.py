"""
File Name       : camera.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-04
Last Modified   : 2026-02-25

Description:
This router provides camera endpoints for the web UI.
Currently supports a snapshot endpoint returning a JPEG image.
"""

from fastapi import APIRouter, Response
import src.app.services.camera_service as cam_mod
from src.app.routers.status import SYSTEM_STATE

from fastapi import HTTPException, Query, Header, Depends
from src.app.core.config import API_KEY, DEMO_MODE

import numpy as np
import cv2

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
        mode = "DEMO" if getattr(svc, "demo_mode", True) else "REAL"
        SYSTEM_STATE["connections"]["camera"]["port"] = f"{mode} camera"
        # SYSTEM_STATE["connections"]["camera"]["port"] = f"index {getattr(svc, 'device_index', 0)}"
    else:
        SYSTEM_STATE["connections"]["camera"]["port"] = None


def require_camera_auth(token: str = Query(default=""), x_api_key: str | None = Header(default=None, alias="X-API-Key"),) -> None:
    """
    DEMO mode:
        Accept either ?token= query parameter OR X-API-Key header.

    REAL mode:
        Accept ONLY X-API-Key header.
        Query token is NOT accepted (for security reasons).
    """
    # demo
    if DEMO_MODE:
        if token == API_KEY or x_api_key == API_KEY:
            return
        raise HTTPException(status_code=401, detail="Unauthorized")

    # real
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/camera/snapshot", dependencies=[Depends(require_camera_auth)])
def snapshot():
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

@router.post("/camera/restart", dependencies=[Depends(require_camera_auth)])
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

# camera overlay'i icin yeni endpoint
@router.get("/camera/overlay", dependencies=[Depends(require_camera_auth)])
def overlay():
    from src.app.services.vision_service import vision_service
    
    svc = _get_cam()
    if svc is None:
        _set_camera_conn(False)
        raise HTTPException(status_code=503, detail="Camera service not initialized")

    jpg = svc.get_jpeg()
    if jpg is None:
        _set_camera_conn(False)
        return Response(content=b"", status_code=503)

    # jpeg -> frame
    arr = np.frombuffer(jpg, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        _set_camera_conn(False)
        return Response(content=b"", status_code=503)

    # detect + draw
    if vision_service is None or not vision_service.is_ready():
        # model yoksa raw don - bos kalmamasi icin
        _set_camera_conn(True)
        return Response(content=jpg, media_type="image/jpeg")

    dets = vision_service.detect(frame)
    overlay_img = vision_service.draw_overlay(frame, dets)

    ok, buf = cv2.imencode(".jpg", overlay_img)
    if not ok:
        _set_camera_conn(True)
        return Response(content=jpg, media_type="image/jpeg")

    _set_camera_conn(True)
    return Response(content=buf.tobytes(), media_type="image/jpeg")