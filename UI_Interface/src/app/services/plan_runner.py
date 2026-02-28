"""
File Name       : plan_runner.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-05
Last Modified   : 2026-02-25

Description:
Plan execution service.
Executes pick-and-place plan step by step.
"""

import threading
import time
from datetime import datetime
from typing import Optional


class PlanRunner:
    def __init__(self, step_delay_s: float = 1.2):
        self.step_delay_s = step_delay_s
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # start yapildiktan sonra stop yapilip tekrar start yapildiginda kaldigi yerden devam edebilsin
        self.paused = False     #durdurma
        self.current_step = 0   #kalinan yeri tutma

        print("[PLAN_RUNNER] Initialized")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start running the current plan (only one runner at a time)."""
        with self._lock:
            if self.is_running():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Request stop."""
        self._stop_event.set()
        self.paused = True

    # reset eklendi
    def reset(self) -> None:
        """Reset plan execution"""
        print("[PLAN_RUNNER] Reset requested")
        self._stop_event.set()
        self.paused = False
        self.current_step = 0

    def _log(self, msg: str) -> None:
        # circular import x! lazy import
        from src.app.routers.status import SYSTEM_STATE
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        SYSTEM_STATE["logs"].append(f"[{ts}] {msg}")

    def _wait(self, seconds: float) -> bool:
        """Wait but stop instantly if stop requested. Returns False if stopped."""
        return not self._stop_event.wait(seconds)

    def _loop(self) -> None:
        from src.app.routers.status import SYSTEM_STATE

        from src.app.main import robot_service, arduino_service, camera_service
        try:
            from src.app.main import vision_service
        except Exception:
            vision_service = None

        from src.app.services.robot_actions import pick_part, goto_test_station, place_part
        if robot_service is None:
            self._log("Robot service not initialized")
            SYSTEM_STATE["robot"]["status"] = "error"
            return
        if arduino_service is None:
            self._log("Arduino service not initialized (test station disabled)")


        plan = SYSTEM_STATE.get("plan", [])
        if not plan:
            self._log("PlanRunner: no plan to run.")
            SYSTEM_STATE["robot"]["status"] = "idle"
            SYSTEM_STATE["robot"]["current_task"] = "-"
            self.current_step = 0
            self.paused = False
            return
        
        start_index = self.current_step if self.paused else 0
        total = len(plan)
        self._log(f"PlanRunner started. Steps: {total} (from step {start_index + 1})")
        SYSTEM_STATE["robot"]["status"] = "running"

        # step-by-step
        for i in range(start_index, total):
            step = plan[i]

            if self._stop_event.is_set():
                self._log("PlanRunner stopped by user.")
                SYSTEM_STATE["robot"]["status"] = "stopped"
                SYSTEM_STATE["robot"]["current_task"] = "-"
                self.current_step = i # resume mantigi, kaldigi yerden devam edebilmesi icin
                self.paused = True
                return

            part = str(step.get("part", "")).upper()
            pad = str(step.get("padLabel", step.get("padName", ""))).upper()
            step_no = i + 1
            
            # PICK
            SYSTEM_STATE["robot"]["current_task"] = f"Step {step_no}/{total}: PICK {part}"
            self._log(f"Step {step_no}: PICK {part}")
            ok = pick_part(robot_service, part)
            
            if not self._wait(self.step_delay_s):
                self._log("PlanRunner stopped by user.")
                SYSTEM_STATE["robot"]["status"] = "stopped"
                SYSTEM_STATE["robot"]["current_task"] = "-"
                self.current_step = i
                self.paused = True
                return
            
            if not ok:
                self._log(f"Step {step_no}: PICK failed for {part}")
                SYSTEM_STATE["robot"]["status"] = "error"
                return

            # --- PICK dogrulama (vision)
            if camera_service is not None:
                jpg = camera_service.get_jpeg()
                if jpg and vision_service is not None and getattr(vision_service, "is_ready", lambda: False)():
                    import numpy as np
                    import cv2
                    arr = np.frombuffer(jpg, dtype=np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if frame is not None:
                        dets = vision_service.detect(frame)
                        if dets:
                            top = dets[0]
                            SYSTEM_STATE["image_processing"]["last_detection"] = {
                                "component": part,
                                "type": vision_service.class_names.get(top.class_id, str(top.class_id)),
                                "confidence": float(top.score),
                            }
            SYSTEM_STATE["image_processing"]["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")

            # STOP tekrar kontrol
            if self._stop_event.is_set():
                self._log("PlanRunner stopped by user.")
                SYSTEM_STATE["robot"]["status"] = "stopped"
                SYSTEM_STATE["robot"]["current_task"] = "-"
                self.current_step = i
                self.paused = True
                return

            # TEST STATION
            SYSTEM_STATE["robot"]["current_task"] = f"Step {step_no}/{total}: TEST {part}"
            self._log(f"Step {step_no}: TEST {part}")

            ok = goto_test_station(robot_service)

            if not self._wait(self.step_delay_s):
                self._log("PlanRunner stopped by user.")
                SYSTEM_STATE["robot"]["status"] = "stopped"
                SYSTEM_STATE["robot"]["current_task"] = "-"
                self.current_step = i
                self.paused = True
                return

            if not ok:
                self._log(f"Step {step_no}: goto_test_station failed")
                SYSTEM_STATE["robot"]["status"] = "error"
                return

            # --- arduino'dan olcum alma
            data = arduino_service.measure() if arduino_service is not None else {"result": "NO_SERVICE"}
            SYSTEM_STATE["teststation"]["mode"] = data.get("mode", "none")
            SYSTEM_STATE["teststation"]["last_adc"] = data.get("value_text", "-")
            SYSTEM_STATE["teststation"]["last_voltage_v"] = data.get("voltage",  0.0)
            SYSTEM_STATE["teststation"]["last_result"] = data.get("result", "UNKOWN")
            SYSTEM_STATE["teststation"]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")

            # PLACE
            SYSTEM_STATE["robot"]["current_task"] = f"Step {step_no}/{total}: PLACE {part} -> {pad}"
            self._log(f"Step {step_no}: PLACE {part} -> {pad}")
            
            ok = place_part(robot_service, pad)

            if not self._wait(self.step_delay_s):
                self._log("PlanRunner stopped by user.")
                SYSTEM_STATE["robot"]["status"] = "stopped"
                SYSTEM_STATE["robot"]["current_task"] = "-"
                self.current_step = i
                self.paused = True
                return
            
            if not ok:
                self._log(f"Step {step_no}: PLACE failed for {part} -> {pad}")
                SYSTEM_STATE["robot"]["status"] = "error"
                return

            # --- PLACE dogrulama (vision)
            if camera_service is not None:
                jpg = camera_service.get_jpeg()
                if jpg and vision_service is not None and getattr(vision_service, "is_ready", lambda: False)():
                    import numpy as np
                    import cv2
                    from src.app.vision.placement_verify import verify_placement

                    arr = np.frombuffer(jpg, dtype=np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if frame is not None:
                        dets = vision_service.detect(frame)
                        # sonra bak !!! detection var yok var simdilik
                        # acc = 100.0 if len(dets) > 0 else 0.0
                        if dets:
                            top = dets[0]  # en yuksek skor
                            res = verify_placement(pad, top.box, tolerance_px=30)
                        else:
                            res = {"pad": pad, "status": "NO_DETECTION", "accuracy": 0.0}
                        
                        SYSTEM_STATE["image_processing"]["last_placement"] = res
                        SYSTEM_STATE["image_processing"]["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                        

        # plan bitince
        SYSTEM_STATE["robot"]["status"] = "idle"
        SYSTEM_STATE["robot"]["current_task"] = "done"
        self.current_step = 0
        self.paused = False
        self._log("PlanRunner finished.")


plan_runner = None

def init_plan_runner():
    """Initialize plan runner singleton"""
    global plan_runner
    plan_runner = PlanRunner()
    return plan_runner
