"""
File Name       : plan_runner.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-05
Last Modified   : 2026-02-05

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

    def _loop(self) -> None:
        from src.app.routers.status import SYSTEM_STATE

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
            time.sleep(self.step_delay_s)

            # STOP tekrar kontrol
            if self._stop_event.is_set():
                self._log("PlanRunner stopped by user.")
                SYSTEM_STATE["robot"]["status"] = "stopped"
                SYSTEM_STATE["robot"]["current_task"] = "-"
                self.current_step = i
                self.paused = True
                return

            # PLACE
            SYSTEM_STATE["robot"]["current_task"] = f"Step {step_no}/{total}: PLACE {part} -> {pad}"
            self._log(f"Step {step_no}: PLACE {part} -> {pad}")
            time.sleep(self.step_delay_s)

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
