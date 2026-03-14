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

# ***
# eslestirme ve yerlestirme icin
def _reset_selection_state() -> None:
    """Reset measurement / target / resolved selection fields."""
    from src.app.routers.status import SYSTEM_STATE

    SYSTEM_STATE["measurements"] = {
        "R1": "-",
        "R2": "-",
        "R3": "-",
        "R4": "-",
        "R5": "-",
        "R6": "-",
        "D1": "-",
        "D2": "-",
    }

    SYSTEM_STATE["measurement_ohm"] = {
        "R1": None,
        "R2": None,
        "R3": None,
        "R4": None,
        "R5": None,
        "R6": None,
    }

    SYSTEM_STATE["resistor_targets"] = {
        "R1": None,
        "R2": None,
    }

    SYSTEM_STATE["resolved_assignments"] = {
        "R1": None,
        "R2": None,
    }

    SYSTEM_STATE["program"]["pcb_done"] = {
        "R1": False,
        "R2": False,
        "D1": False,
        "D2": False,
    }
# ***

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
        - test_measure
    """
    from src.app.routers.status import SYSTEM_STATE
    from src.app.main import gcode_runner 

    name = (cmd.name or "").strip().lower()
    payload = cmd.payload or {}

    if gcode_runner is None:
        raise HTTPException(status_code=500, detail="GCodeRunner not initialized")
# ***
    # SET RESISTOR TARGETS
    if name == "set_resistor_targets":
        r1_code = payload.get("r1_code")
        r2_code = payload.get("r2_code")

        valid_codes = {"102", "103", "472", "333", "104"} # !!!! 6 direnc olacak

        if not r1_code or str(r1_code).strip() not in valid_codes:
            raise HTTPException(status_code=400, detail="Invalid R1 target code")

        if not r2_code or str(r2_code).strip() not in valid_codes:
            raise HTTPException(status_code=400, detail="Invalid R2 target code")

        SYSTEM_STATE["resistor_targets"]["R1"] = str(r1_code).strip()
        SYSTEM_STATE["resistor_targets"]["R2"] = str(r2_code).strip()

        # temizlik
        SYSTEM_STATE["resolved_assignments"]["R1"] = None
        SYSTEM_STATE["resolved_assignments"]["R2"] = None

        _log(
            f"Command received: SET_RESISTOR_TARGETS "
            f"(R1={SYSTEM_STATE['resistor_targets']['R1']}, "
            f"R2={SYSTEM_STATE['resistor_targets']['R2']})"
        )
        return {
            "ok": True,
            "message": "Resistor targets saved",
            "targets": SYSTEM_STATE["resistor_targets"],
        }
# ***  
    # START
    if name == "start":
        # ***
        targets = SYSTEM_STATE.get("resistor_targets", {})
        if not targets.get("R1") or not targets.get("R2"):
            raise HTTPException(
                status_code=400,
                detail="Resistor targets must be selected before start"
            )
        # ***

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
        # ***
        _reset_selection_state()
        # ***
        _log("Command received: RESET")
        return {"ok": True, "message": "Program reset"}
    
    # buton kalkti gerek yok
    # komponent olcumleri
    # if name == "test_measure":
    #     gcode_runner._run_test_measure(step_id=None, manual=True)
    #     _log("Command received: TEST_MEASURE")
    #     return {"ok": True, "message": "Manual measurement completed"}
    
    # buton kalkti gerek yok
    # manuel test icin hareket
    # if name == "manual_test":
    #     ok = gcode_runner.run_manual_test_cycle()

    #     if not ok:
    #         raise HTTPException(status_code=400, detail="Manual test could not be completed")

    #     _log("Command received: MANUAL_TEST")
    #     return {"ok": True, "message": "Manual test completed"}
    
    # if name == "test_measure":
    #     from src.app.main import arduino_service
    #     if arduino_service is None:
    #         raise HTTPException(status_code=500, detail="Arduino service not initialized")

    #     data = arduino_service.measure()
    #     SYSTEM_STATE["teststation"]["mode"] = data.get("mode", "none")
    #     SYSTEM_STATE["teststation"]["last_adc"] = data.get("value_text", "-")   # eskiden adc'ydi artik VALUE TEXT
    #     SYSTEM_STATE["teststation"]["last_voltage_v"] = data.get("voltage", 0.0)
    #     SYSTEM_STATE["teststation"]["last_result"] = data.get("result", "UNKNOWN")
    #     SYSTEM_STATE["teststation"]["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    #     _log("Command received: TEST_MEASURE")
    #     return {"ok": True, "data": data}

    # Error : bilinmeyen bir komut
    _log(f"Unknown command received: {cmd.name}")
    return {"ok": False, "error": f"Unknown command: {cmd.name}"}
