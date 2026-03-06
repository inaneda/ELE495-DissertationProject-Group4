"""
File Name       : commands.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-01
Last Modified   : 2026-02-04

Description:
This module defines the /api/commands endpoint.
It receives control commands from the web UI (Start, Stop, Reset)
and updates the system state accordingly.
"""

from fastapi import APIRouter
from fastapi import HTTPException
from pydantic import BaseModel
from datetime import datetime


# status router'inin icindeki SYSTEM_STATE'i kullaniyoruz
#from src.app.routers.status import SYSTEM_STATE

# artik main'de uretiliyor
#from src.app.services.plan_runner import plan_runner

# API key
from fastapi import Depends
from src.app.security import require_api_key

# tum endpointler
router = APIRouter(
    prefix="/api/commands",
    tags=["Commands"],
    dependencies=[Depends(require_api_key)] # API key
)


# request modeli - gelen JSON sekli ile alakali : hata icin
class CommandRequest(BaseModel):
    name: str
    payload: dict | None = None


# modul ici icin
def _log(msg: str) -> None:
    """Append a timestamped message to SYSTEM_STATE logs."""
    from src.app.routers.status import SYSTEM_STATE
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    SYSTEM_STATE["logs"].append(f"[{ts}] {msg}")

    # log sinirlandirmasi : son 300 satir
    if len(SYSTEM_STATE["logs"]) > 300:
        SYSTEM_STATE["logs"] = SYSTEM_STATE["logs"][-300:]

# endpoint : POST
# CommandRequest gelen veri JSON -> Python Object
@router.post("/")
def post_command(cmd: CommandRequest):
    """
    Receive a command from the UI and update system state.

    Supported commands:
        - start
        - stop
        - reset
        - set_test_mode (payload: {"mode": "resistor"|"diode"|"none"})
        - test_measure
    """
    from src.app.routers.status import SYSTEM_STATE
    from src.app.main import gcode_runner 

    name = (cmd.name or "").strip().lower()
    payload = cmd.payload or {}

    if gcode_runner is None:
        raise HTTPException(status_code=500, detail="GCodeRunner not initialized")

    # START
    if name == "start":
        gcode_runner.start()
        _log("Command received: START")
        return {"ok": True, "message": "Program started/resumed"}

    # STOP
    if name == "stop":
        gcode_runner.stop()
        _log("Command received: STOP")
        return {"ok": True, "message": "Program paused"}

    # RESET
    if name == "reset":
        gcode_runner.reset()
        _log("Command received: RESET")
        return {"ok": True, "message": "Program reset"}

    # TEST MODE
    if name == "set_test_mode":
        mode = str(payload.get("mode", "none")).lower()
        SYSTEM_STATE["teststation"]["mode"] = mode
        _log(f"Command received: SET_TEST_MODE ({mode})")
        return {"ok": True, "message": f"Test mode set to {mode}"}
    
    if name == "test_measure":
        from src.app.main import arduino_service
        if arduino_service is None:
            raise HTTPException(status_code=500, detail="Arduino service not initialized")

        data = arduino_service.measure()
        SYSTEM_STATE["teststation"]["mode"] = data.get("mode", "none")
        SYSTEM_STATE["teststation"]["last_adc"] = data.get("value_text", "-")   # eskiden adc'ydi artik VALUE TEXT
        SYSTEM_STATE["teststation"]["last_voltage_v"] = data.get("voltage", 0.0)
        SYSTEM_STATE["teststation"]["last_result"] = data.get("result", "UNKNOWN")
        SYSTEM_STATE["teststation"]["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        _log("Command received: TEST_MEASURE")
        return {"ok": True, "data": data}

    # Error : bilinmeyen bir komut
    _log(f"Unknown command received: {cmd.name}")
    return {"ok": False, "error": f"Unknown command: {cmd.name}"}
