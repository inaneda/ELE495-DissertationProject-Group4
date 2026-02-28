"""
File Name       : config.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-05
Last Modified   : 2026-02-25

Description:
Provides minimal configuration to the frontend (demo use).
API key can be served for LAN usage only.
For REAL mode, exposing API key is unsafe for WAN.
"""

from fastapi import APIRouter
from src.app.core.config import API_KEY, DEMO_MODE

router = APIRouter(prefix="/api", tags=["Config"])

@router.get("/config")
def get_config():
    # demo: UI key'i alabilsin (LAN)
    if DEMO_MODE:
        return {
            "mode": "DEMO",
            "api_key": API_KEY
        }
    return {
        "mode": "REAL",
        "api_key": None,
        "message": "API key is not exposed in REAL mode. Set it manually in the client.",
    }