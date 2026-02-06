"""
File Name       : config.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-05
Last Modified   : 2026-02-05

Description:
Provides minimal configuration to the frontend (demo use).
For this project/demo, API key can be served for LAN usage only.
"""

from fastapi import APIRouter
from src.app.core.config import API_KEY

router = APIRouter(prefix="/api", tags=["Config"])

@router.get("/config")
def get_config():
    return {
        "api_key": API_KEY
    }
