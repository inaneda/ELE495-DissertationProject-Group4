"""
File Name       : gcode_runner.py
Author          : Eda
Description:
Runs a fixed G-code program step-by-step with stop/resume/reset support.
Updates SYSTEM_STATE for UI (task/logs, vacuum state, PCB completion).
"""

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

        self._pause_event = threading.Event()  # when set => paused
        self._stop_event = threading.Event()   # when set => hard stop thread loop (used by reset)

        self.current_step_idx = 0
        self.vacuum_on: bool = False

        # start'a basinca (!!ozellikle idx=0 iken) yeniden build edilecek
        self.program = []

        print("[GCODE_RUNNER] Initialized")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _log(self, msg: str) -> None:
        from src.app.routers.status import SYSTEM_STATE
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        SYSTEM_STATE["logs"].append(f"[{ts}] {msg}")

        # loglarin siniri
        if len(SYSTEM_STATE["logs"]) > 300:
            SYSTEM_STATE["logs"] = SYSTEM_STATE["logs"][-300:]

    def start(self) -> None:
        """
        Start or resume.
        If already running, just unpause.
        """
        from src.app.routers.status import SYSTEM_STATE

        try: # eksik bir yer varsa hata versin
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

            # eger bastan baslaniyorsa yeniden build et (!!idx=0)
            if self.current_step_idx == 0 and not self.is_running():
                self.program = build_program()


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
        """
        Pause execution. Vacuum state stays as-is.
        """
        self._pause_event.set()
        self._log("GCodeRunner: STOP (paused)")

        from src.app.routers.status import SYSTEM_STATE
        SYSTEM_STATE["robot"]["status"] = "stopped"
        SYSTEM_STATE["robot"]["current_task"] = "-"
        SYSTEM_STATE["program"]["paused"] = True
        SYSTEM_STATE["program"]["running"] = True  
        # paused ama program hala "aktif"

    def reset(self) -> None:
        """
        Reset = stop thread + go to home + vacuum off + index=0.
        After reset, new start begins from step 0.
        """
        with self._lock:
            self._pause_event.clear()
            self._stop_event.set()

        self._log("GCodeRunner: RESET requested")

        # calisan thread varsa bir sure bekle
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

        try:
            from src.app.main import robot_service
            if robot_service is not None:
                # Vacuum OFF
                robot_service.send_gcode("M9")
                # home'a gitmek istiyorsak asagidakini yaz:
                # robot_service.send_gcode("...HOME GCODE...")
        except Exception as e:
            self._log(f"GCodeRunner reset safety actions failed: {e}")

        self.current_step_idx = 0
        self.vacuum_on = False

        from src.app.routers.status import SYSTEM_STATE
        SYSTEM_STATE["robot"]["status"] = "idle"
        SYSTEM_STATE["robot"]["current_task"] = "-"
        SYSTEM_STATE["program"]["current_step"] = 0
        SYSTEM_STATE["program"]["total_steps"] = 0
        SYSTEM_STATE["program"]["current_label"] = "-"
        SYSTEM_STATE["program"]["vacuum_on"] = False
        SYSTEM_STATE["program"]["running"] = False
        SYSTEM_STATE["program"]["paused"] = False

        # pcb tamamlamasini sifirlama
        for k in SYSTEM_STATE["program"]["pcb_done"].keys():
            SYSTEM_STATE["program"]["pcb_done"][k] = False

        self._log("GCodeRunner: RESET done")
        self._thread = None


    def _wait_if_paused(self) -> bool:
        """
        Returns False if hard-stopped, True otherwise.
        """
        while self._pause_event.is_set():
            if self._stop_event.is_set():
                return False
            time.sleep(0.05)
        return not self._stop_event.is_set()

    def _send_many(self, robot, lines: list[str]) -> bool:
        from src.app.routers.status import SYSTEM_STATE

        for line in lines:
            if not self._wait_if_paused():
                return False
            
            line = (line or "").strip()
            if not line:
                continue  # bos satir atlama

            ok = robot.send_gcode(line)

            # GRBL'in son bilgisi ile UI guncellenmeli
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
    

    # vision
    def _extract_comp_and_pad(self, step_id: str):
        """
        Extract the component/pad information from the STEP ID. 
        For example: 
            R1_PICK_Z -> comp=R1, pad=A
            D2_PLACE  -> comp=D2, pad=D
        """
        comp = None
        pad = None

        if "_" in step_id:
            comp = step_id.split("_")[0]

        from src.app.services.gcode_programs import PAD_BY_COMPONENT
        if comp in PAD_BY_COMPONENT:
            pad = PAD_BY_COMPONENT[comp]

        return comp, pad


    def _run_pick_vision(self, step_id: str) -> None:
        from src.app.routers.status import SYSTEM_STATE
        from src.app.main import camera_service, vision_service

        if camera_service is None or vision_service is None:
            return
        if not vision_service.is_ready():
            return

        frame = camera_service.get_frame()
        if frame is None:
            return

        boxes, scores, class_ids = vision_service.detect(frame)
        det = vision_service.summarize_detection(boxes, scores, class_ids)

        SYSTEM_STATE["image_processing"]["last_detection"] = {
            "component": det.get("component"),
            "type": det.get("type"),
            "confidence": det.get("confidence"),
        }
        SYSTEM_STATE["image_processing"]["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    def _run_place_vision(self, step_id: str) -> None:
        from src.app.routers.status import SYSTEM_STATE
        from src.app.main import camera_service, vision_service
        from src.app.services.gcode_programs import TARGET_BOX_BY_PAD

        if camera_service is None or vision_service is None:
            return
        if not vision_service.is_ready():
            return

        comp, pad = self._extract_comp_and_pad(step_id)
        if not pad:
            return

        target_box = TARGET_BOX_BY_PAD.get(pad)
        if not target_box:
            SYSTEM_STATE["image_processing"]["last_placement"] = {
                "pad": pad,
                "accuracy": None,
                "status": "NO_TARGET_BOX"
            }
            SYSTEM_STATE["image_processing"]["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            return

        frame = camera_service.get_frame()
        if frame is None:
            return

        boxes, scores, class_ids = vision_service.detect(frame)
        det = vision_service.summarize_detection(boxes, scores, class_ids)
        result = vision_service.score_target(target_box, boxes)

        status_txt = "OK" if result["iou"] > 0 else "NO_MATCH"

        SYSTEM_STATE["image_processing"]["last_detection"] = {
            "component": det.get("component"),
            "type": det.get("type"),
            "confidence": det.get("confidence"),
        }

        SYSTEM_STATE["image_processing"]["last_placement"] = {
            "pad": pad,
            "accuracy": float(result["accuracy"]),
            "status": status_txt
        }

        SYSTEM_STATE["image_processing"]["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")


    # test station
    def _run_test_measure(self) -> None:
        """
        Test istasyonu adimindan sonra Arduino olcumunu tetikler
        ve SYSTEM_STATE["teststation"] icini gunceller.
        """
        from src.app.routers.status import SYSTEM_STATE
        from src.app.main import arduino_service

        if arduino_service is None:
            self._log("Test measure skipped: Arduino service not initialized")
            return

        try:
            data = arduino_service.measure()

            SYSTEM_STATE["teststation"]["mode"] = data.get("mode", "none")
            SYSTEM_STATE["teststation"]["last_adc"] = data.get("value_text", "-")
            SYSTEM_STATE["teststation"]["last_voltage_v"] = data.get("voltage", 0.0)
            SYSTEM_STATE["teststation"]["last_result"] = data.get("result", "UNKNOWN")
            SYSTEM_STATE["teststation"]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")

            self._log(f"Test measurement done: {data.get('result', 'UNKNOWN')}")
        except Exception as e:
            self._log(f"Test measurement failed: {e}")


    def _loop(self) -> None:
        from src.app.routers.status import SYSTEM_STATE
        from src.app.main import robot_service

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

        while self.current_step_idx < total:
            if self._stop_event.is_set():
                break

            if self._pause_event.is_set():
                SYSTEM_STATE["program"]["paused"] = True
                if not self._wait_if_paused():
                    break
                SYSTEM_STATE["program"]["paused"] = False
                SYSTEM_STATE["robot"]["status"] = "running"

            step = self.program[self.current_step_idx]

            SYSTEM_STATE["program"]["current_step"] = self.current_step_idx + 1
            SYSTEM_STATE["program"]["current_label"] = step.label
            SYSTEM_STATE["program"]["vacuum_on"] = self.vacuum_on

            SYSTEM_STATE["robot"]["status"] = "running"
            SYSTEM_STATE["robot"]["current_task"] = step.label
            self._log(f"STEP {self.current_step_idx + 1}/{total}: {step.label}")

            # gcode calistirma
            ok = self._send_many(robot_service, step.gcode)
            if not ok:
                return
            

            # vision
            # PICK sonrasi detection
            if step.id.endswith("_PICK_Z"):
                self._run_pick_vision(step.id)


            # TEST sonrasi arduino olcumu
            if step.id.endswith("_TEST_PRESS"):
                self._run_test_measure()


            # vision
            # PLACE sonrasi placement verification
            if step.id.endswith("_PLACE"):
                self._run_place_vision(step.id)


            # vakum takibinin guncellemesi
            if step.vacuum_expected is not None:
                self.vacuum_on = bool(step.vacuum_expected)
                SYSTEM_STATE["program"]["vacuum_on"] = self.vacuum_on

            # yerlestirme bitince PCB'de bitti isaretlemesi yapiliyor
            # boylelikle UI'de yerlestirilenin rengi degisebilecek
            # vakum kapandiginda
            if step.marks_done_component:
                SYSTEM_STATE["program"]["pcb_done"][step.marks_done_component] = True

            self.current_step_idx += 1

        # finished
        SYSTEM_STATE["robot"]["status"] = "idle"
        SYSTEM_STATE["robot"]["current_task"] = "done"
        SYSTEM_STATE["program"]["running"] = False
        SYSTEM_STATE["program"]["paused"] = False
        SYSTEM_STATE["program"]["current_label"] = "done"
        self._log("GCodeRunner: finished")


gcode_runner = None


def init_gcode_runner():
    global gcode_runner
    gcode_runner = GCodeRunner()
    return gcode_runner