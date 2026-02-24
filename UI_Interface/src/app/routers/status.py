"""
File Name       : status.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-01
Last Modified   : 2026-02-04

Description:
This module defines the /api/status endpoint.
It provides the current system status information to the web UI,
including robot state, test station state, logs, and connection status.

This endpoint is periodically polled by the dashboard frontend.
"""

from fastapi import APIRouter

# API key
from fastapi import Depends
from src.app.security import require_api_key

# Router
router = APIRouter(
    prefix="/api/status",
    tags=["Status"],
    dependencies=[Depends(require_api_key)] # API key
)

# sonra bak !!!!!!! - gecici veri
# sistem durumu - gecici
SYSTEM_STATE = {
    "robot": {
        "status": "idle",
        "current_task": "-",
        "x": 0,
        "y": 0,
        "z": 0
    },

    "grbl": {
        "state": "idle",                 # Idle/Run/Hold/Alarm
        "mpos": {"x": 0.0, "y": 0.0, "z": 0.0},
        "last_ok": None,                 # True/False/None
        "last_line": None,               # son gcode satırı - demo
        "last_updated": None             # ISO string
    },

    "teststation": {
        "mode": "none",
        "last_adc": None,
        "last_voltage_v": None,
        "last_result": None,
        "last_updated": None
    },

    "logs": [
        "Backend started (demo mode)"
    ],

    "image_processing": {
        "last_detection": {
            "component": None,      # R1, R2, D1, D2
            "type": None,           # R, D
            "confidence": 0.0       # 0 - 1
        },
        "last_placement": {         # yerlestirme dogrulaması
            "pad": None,            # a, b, c, d
            "accuracy": 0.0,        # dogruluk 0 -100
            "status": "unknown"
        },
        "last_updated": None
    },

    "connections": {
        "arduino_motors": {
           "status": False,
            "port": None
        },
        "arduino_teststation": {
            "status": False,
            "port": None
        },
        "camera": {
        "status": False,
        "port": None
        }
    },
    
    "plan": [],

    "plan_received_at": None
}

# sistemin su anki durumunu alir : GET
@router.get("/")
def get_status():
    """
    Get the current system status.

    Returns:
        dict: A dictionary containing robot state, test station state,
              connection flags, and system logs.
    """
    return SYSTEM_STATE
