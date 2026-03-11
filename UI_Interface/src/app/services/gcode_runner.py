from __future__ import annotations
import threading
import time
from datetime import datetime
from typing import Optional

from src.app.services.gcode_programs import build_program, validate_required_gcodes


class GCodeRunner:
    def __init__(self):
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

        self._pause_event = threading.Event()
        self._stop_event = threading.Event()

        self.current_step_idx = 0
        self.vacuum_on: bool = False
        self.program = []

        print("[GCODE_RUNNER] Initialized")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _log(self, msg: str) -> None:
        from src.app.routers.status import SYSTEM_STATE

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        SYSTEM_STATE["logs"].append(f"[{ts}] {msg}")

        if len(SYSTEM_STATE["logs"]) > 300:
            SYSTEM_STATE["logs"] = SYSTEM_STATE["logs"][-300:]

    def start(self) -> None:
        from src.app.routers.status import SYSTEM_STATE

        try:
            validate_required_gcodes()
        except Exception as e:
            self._log(f"GCodeRunner: START blocked - {e}")
            SYSTEM_STATE["robot"]["status"] = "error"
            SYSTEM_STATE["robot"]["current_task"] = "GCODE missing"
            SYSTEM_STATE["program"]["running"] = False
            SYSTEM_STATE["program"]["paused"] = False
            return

        with self._lock:
            self._pause_event.clear()
            self._stop_event.clear()

            if self.current_step_idx == 0 and not self.is_running():
                self.program = build_program()

                if not self.program:
                    self._log("Program build failed (empty)")
                    return

            if self.is_running():
                SYSTEM_STATE["program"]["paused"] = False
                SYSTEM_STATE["program"]["running"] = True
                SYSTEM_STATE["robot"]["status"] = "running"
                self._log("GCodeRunner: RESUME")
                return

            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

            SYSTEM_STATE["program"]["running"] = True
            SYSTEM_STATE["program"]["paused"] = False
            SYSTEM_STATE["robot"]["status"] = "running"

            self._log("GCodeRunner: START")

    def stop(self) -> None:
        self._pause_event.set()
        self._log("GCodeRunner: STOP (paused)")

        from src.app.routers.status import SYSTEM_STATE

        SYSTEM_STATE["robot"]["status"] = "stopped"
        SYSTEM_STATE["robot"]["current_task"] = "-"
        SYSTEM_STATE["program"]["paused"] = True
        SYSTEM_STATE["program"]["running"] = True

    def reset(self) -> None:
        with self._lock:
            self._pause_event.clear()
            self._stop_event.set()

        self._log("GCodeRunner: RESET requested")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

        self.current_step_idx = 0
        self.vacuum_on = False
        self.program = []

        from src.app.routers.status import SYSTEM_STATE

        SYSTEM_STATE["robot"]["status"] = "idle"
        SYSTEM_STATE["robot"]["current_task"] = "-"

        SYSTEM_STATE["program"]["current_step"] = 0
        SYSTEM_STATE["program"]["total_steps"] = 0
        SYSTEM_STATE["program"]["current_label"] = "-"
        SYSTEM_STATE["program"]["vacuum_on"] = False

        SYSTEM_STATE["program"]["running"] = False
        SYSTEM_STATE["program"]["paused"] = False

        for k in SYSTEM_STATE["program"]["pcb_done"].keys():
            SYSTEM_STATE["program"]["pcb_done"][k] = False

        for k in SYSTEM_STATE["measurements"].keys():
            SYSTEM_STATE["measurements"][k] = None

        SYSTEM_STATE["teststation"]["last_result"] = None
        SYSTEM_STATE["teststation"]["last_voltage_v"] = None
        SYSTEM_STATE["teststation"]["last_resistance_ohm"] = None
        SYSTEM_STATE["teststation"]["last_updated"] = None
        SYSTEM_STATE["teststation"]["mode"] = None
        SYSTEM_STATE["teststation"]["value_text"] = None
        SYSTEM_STATE["teststation"]["raw_text"] = None

        self._thread = None

        self._log("GCodeRunner: RESET done")

    def _wait_if_paused(self) -> bool:
        while self._pause_event.is_set():
            if self._stop_event.is_set():
                return False
            time.sleep(0.05)

        return not self._stop_event.is_set()

    def _send_many(self, robot, lines: list[str]) -> bool:
        from src.app.routers.status import SYSTEM_STATE

        if not lines:
            return True

        for line in lines:
            if not self._wait_if_paused():
                return False

            line = (line or "").strip()
            if not line:
                continue

            ok = robot.send_gcode(line)

            SYSTEM_STATE["grbl"]["last_line"] = line
            SYSTEM_STATE["grbl"]["last_ok"] = bool(ok)
            SYSTEM_STATE["grbl"]["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")

            if not ok:
                self._log(f"GCode error on: {line}")
                SYSTEM_STATE["robot"]["status"] = "error"
                SYSTEM_STATE["robot"]["current_task"] = "G-code error"
                SYSTEM_STATE["program"]["running"] = False
                SYSTEM_STATE["program"]["paused"] = False
                return False

        return True

    def _run_measurement(self) -> None:
        from src.app.routers.status import SYSTEM_STATE
        from src.app.main import arduino_service

        if arduino_service is None:
            SYSTEM_STATE["teststation"]["last_result"] = "NO_SERVICE"
            SYSTEM_STATE["teststation"]["last_voltage_v"] = 0.0
            SYSTEM_STATE["teststation"]["last_resistance_ohm"] = None
            SYSTEM_STATE["teststation"]["mode"] = "none"
            SYSTEM_STATE["teststation"]["value_text"] = "-"
            SYSTEM_STATE["teststation"]["raw_text"] = ""
            SYSTEM_STATE["teststation"]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")

            if "measurements" in SYSTEM_STATE:
                if "result" in SYSTEM_STATE["measurements"]:
                    SYSTEM_STATE["measurements"]["result"] = "NO_SERVICE"
                if "voltage" in SYSTEM_STATE["measurements"]:
                    SYSTEM_STATE["measurements"]["voltage"] = 0.0
                if "resistance_ohm" in SYSTEM_STATE["measurements"]:
                    SYSTEM_STATE["measurements"]["resistance_ohm"] = None
                if "value_text" in SYSTEM_STATE["measurements"]:
                    SYSTEM_STATE["measurements"]["value_text"] = "-"
                if "raw_text" in SYSTEM_STATE["measurements"]:
                    SYSTEM_STATE["measurements"]["raw_text"] = ""

            return

        try:
            measurement = arduino_service.measure()

            SYSTEM_STATE["teststation"]["last_result"] = measurement.get("result")
            SYSTEM_STATE["teststation"]["last_voltage_v"] = measurement.get("voltage", 0.0)
            SYSTEM_STATE["teststation"]["last_resistance_ohm"] = measurement.get("resistance_ohm")
            SYSTEM_STATE["teststation"]["mode"] = measurement.get("mode", "none")
            SYSTEM_STATE["teststation"]["value_text"] = measurement.get("value_text", "-")
            SYSTEM_STATE["teststation"]["raw_text"] = measurement.get("raw_text", "")
            SYSTEM_STATE["teststation"]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")

            if "measurements" in SYSTEM_STATE:
                if "result" in SYSTEM_STATE["measurements"]:
                    SYSTEM_STATE["measurements"]["result"] = measurement.get("result")
                if "voltage" in SYSTEM_STATE["measurements"]:
                    SYSTEM_STATE["measurements"]["voltage"] = measurement.get("voltage", 0.0)
                if "resistance_ohm" in SYSTEM_STATE["measurements"]:
                    SYSTEM_STATE["measurements"]["resistance_ohm"] = measurement.get("resistance_ohm")
                if "value_text" in SYSTEM_STATE["measurements"]:
                    SYSTEM_STATE["measurements"]["value_text"] = measurement.get("value_text", "-")
                if "raw_text" in SYSTEM_STATE["measurements"]:
                    SYSTEM_STATE["measurements"]["raw_text"] = measurement.get("raw_text", "")

        except Exception as e:
            self._log(f"Measurement error: {e}")
            SYSTEM_STATE["teststation"]["last_result"] = "ERROR"
            SYSTEM_STATE["teststation"]["last_voltage_v"] = 0.0
            SYSTEM_STATE["teststation"]["last_resistance_ohm"] = None
            SYSTEM_STATE["teststation"]["mode"] = "none"
            SYSTEM_STATE["teststation"]["value_text"] = "-"
            SYSTEM_STATE["teststation"]["raw_text"] = ""
            SYSTEM_STATE["teststation"]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")

            if "measurements" in SYSTEM_STATE:
                if "result" in SYSTEM_STATE["measurements"]:
                    SYSTEM_STATE["measurements"]["result"] = "ERROR"
                if "voltage" in SYSTEM_STATE["measurements"]:
                    SYSTEM_STATE["measurements"]["voltage"] = 0.0
                if "resistance_ohm" in SYSTEM_STATE["measurements"]:
                    SYSTEM_STATE["measurements"]["resistance_ohm"] = None
                if "value_text" in SYSTEM_STATE["measurements"]:
                    SYSTEM_STATE["measurements"]["value_text"] = "-"
                if "raw_text" in SYSTEM_STATE["measurements"]:
                    SYSTEM_STATE["measurements"]["raw_text"] = ""

    def _loop(self) -> None:
        from src.app.routers.status import SYSTEM_STATE
        from src.app.main import robot_service

        try:
            if robot_service is None:
                self._log("Robot service not initialized")
                SYSTEM_STATE["robot"]["status"] = "error"
                SYSTEM_STATE["program"]["running"] = False
                return

            SYSTEM_STATE["robot"]["status"] = "running"
            SYSTEM_STATE["program"]["running"] = True
            SYSTEM_STATE["program"]["paused"] = False

            total = len(self.program)
            SYSTEM_STATE["program"]["total_steps"] = total

            if total == 0:
                self._log("Program empty")
                return

            while self.current_step_idx < total:
                if self._stop_event.is_set():
                    break

                step = self.program[self.current_step_idx]

                SYSTEM_STATE["program"]["current_step"] = self.current_step_idx + 1
                SYSTEM_STATE["program"]["current_label"] = step.label
                SYSTEM_STATE["program"]["vacuum_on"] = self.vacuum_on

                SYSTEM_STATE["robot"]["status"] = "running"
                SYSTEM_STATE["robot"]["current_task"] = step.label

                self._log(f"STEP {self.current_step_idx + 1}/{total}: {step.label}")

                ok = self._send_many(robot_service, step.gcode)
                if not ok:
                    return

                if step.vacuum_expected is not None:
                    self.vacuum_on = bool(step.vacuum_expected)
                    SYSTEM_STATE["program"]["vacuum_on"] = self.vacuum_on

                if step.trigger_measurement:
                    self._run_measurement()

                if step.marks_done_component:
                    if step.marks_done_component in SYSTEM_STATE["program"]["pcb_done"]:
                        SYSTEM_STATE["program"]["pcb_done"][step.marks_done_component] = True

                self.current_step_idx += 1

            SYSTEM_STATE["robot"]["status"] = "idle"
            SYSTEM_STATE["robot"]["current_task"] = "done"
            SYSTEM_STATE["program"]["running"] = False
            SYSTEM_STATE["program"]["paused"] = False
            SYSTEM_STATE["program"]["current_label"] = "done"

            self._log("GCodeRunner: finished")

        except Exception as e:
            self._log(f"GCodeRunner crashed: {e}")
            SYSTEM_STATE["robot"]["status"] = "error"
            SYSTEM_STATE["program"]["running"] = False


gcode_runner = None


def init_gcode_runner():
    global gcode_runner
    gcode_runner = GCodeRunner()
    return gcode_runner
