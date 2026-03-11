"""
File Name       : status.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-01
Last Modified   : 2026-03-10

Description:
This module defines the /api/status endpoint.
It provides the current system status information to the web UI,
including robot state, test station state, logs, and connection status.

This endpoint is periodically polled by the dashboard frontend.
"""

from fastapi import APIRouter, Depends
from src.app.security import require_api_key


router = APIRouter(
    prefix="/api/status",
    tags=["Status"],
    dependencies=[Depends(require_api_key)]
)


SYSTEM_STATE = {
    "robot": {
        "status": "idle",
        "current_task": "-",
        "x": 0,
        "y": 0,
        "z": 0
    },

    "program": {
        "running": False,
        "paused": False,
        "current_step": 0,
        "total_steps": 0,
        "current_label": "-",
        "vacuum_on": False,
        "pcb_done": {
            "R1": False,
            "R2": False,
            "D1": False,
            "D2": False,
        },
    },

    "grbl": {
        "state": "unknown",
        "mpos": {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0
        },
        "last_ok": None,
        "last_line": None,
        "last_updated": None
    },

    "teststation": {
        "mode": "none",
        "last_adc": None,
        "last_voltage_v": None,
        "last_resistance_ohm": None,
        "last_result": None,
        "last_updated": None,
        "value_text": None,
        "raw_text": None
    },

    "measurements": {
        "result": None,
        "voltage": None,
        "resistance_ohm": None,
        "value_text": None,
        "raw_text": None
    },

    "logs": [],

    "image_processing": {
        "last_detection": {
            "component": None,
            "type": None,
            "confidence": None
        },
        "last_placement": {
            "pad": None,
            "accuracy": None,
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
}


@router.get("/")
def get_status():
    """
    Get the current system status.

    Returns:
        dict: A dictionary containing robot state, test station state,
              connection flags, and system logs.
    """
    return SYSTEM_STATE
