"""
File Name       : status.py
Author          : Eda
Project         : ELE 496 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-01
Last Modified   : 2026-02-04

Description:
This module defines the /api/status endpoint.
It provides the current system status information to the web UI,
including robot state, test station state, logs, and connection status.

This endpoint is periodically polled by the dashboard frontend.
"""

from fastapi import APIRouter

# Router
router = APIRouter(
    prefix="/api/status",
    tags=["Status"]
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
    "connections": {
        "arduino": False,
        "camera": False
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
