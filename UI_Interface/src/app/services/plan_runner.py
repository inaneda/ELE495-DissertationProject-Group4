"""
File Name       : plan_runner.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-05
Last Modified   : 2026-02-05

Description:
Demo plan runner that iterates through the received placement plan (pick/place steps).
It updates SYSTEM_STATE["robot"]["current_task"] and appends logs for each step.
Later this module will be replaced/extended with real robot motion + pick/place control.
"""

import threading
import time
from datetime import datetime
from typing import Optional

from src.app.routers.status import SYSTEM_STATE


class PlanRunner:
    def __init__(self, step_delay_s: float = 1.2):
        self.step_delay_s = step_delay_s
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

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

    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        SYSTEM_STATE["logs"].append(f"[{ts}] {msg}")

    def _loop(self) -> None:
        plan = SYSTEM_STATE.get("plan", [])
        if not plan:
            self._log("PlanRunner: no plan to run.")
            SYSTEM_STATE["robot"]["status"] = "idle"
            SYSTEM_STATE["robot"]["current_task"] = "-"
            return

        SYSTEM_STATE["robot"]["status"] = "running"
        self._log(f"PlanRunner started. Steps: {len(plan)}")

        # Step-by-step demo execution
        for i, step in enumerate(plan, start=1):
            if self._stop_event.is_set():
                self._log("PlanRunner stopped by user.")
                SYSTEM_STATE["robot"]["status"] = "stopped"
                SYSTEM_STATE["robot"]["current_task"] = "-"
                return

            part = str(step.get("part", "")).upper()
            pad = str(step.get("padLabel", step.get("padName", ""))).upper()

            SYSTEM_STATE["robot"]["current_task"] = f"Step {i}/{len(plan)}: PICK {part}"
            self._log(f"Step {i}: PICK {part}")
            time.sleep(self.step_delay_s)

            if self._stop_event.is_set():
                self._log("PlanRunner stopped by user.")
                SYSTEM_STATE["robot"]["status"] = "stopped"
                SYSTEM_STATE["robot"]["current_task"] = "-"
                return

            SYSTEM_STATE["robot"]["current_task"] = f"Step {i}/{len(plan)}: PLACE {part} -> {pad}"
            self._log(f"Step {i}: PLACE {part} -> {pad}")
            time.sleep(self.step_delay_s)

        SYSTEM_STATE["robot"]["status"] = "idle"
        SYSTEM_STATE["robot"]["current_task"] = "done"
        self._log("PlanRunner finished.")


# single instance
plan_runner = PlanRunner()
