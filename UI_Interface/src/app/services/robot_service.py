"""
File Name       : robotService.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-03
Last Modified   : 2026-02-04

Description:
This service simulates robot motion for demo/testing purposes.
When the robot status is 'running', it updates x/y/z periodically.
Later, this module will be replaced/extended with real motion control.
"""

import threading
import time
from src.app.routers.status import SYSTEM_STATE


class RobotService:
    def __init__(self, interval_s: float = 0.4):
        self.interval_s = interval_s
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the background simulation thread (only once)."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background simulation thread."""
        self._stop_event.set()

    def _loop(self) -> None:
        """Background loop updating robot coordinates while running."""
        direction = 1
        while not self._stop_event.is_set():
            robot = SYSTEM_STATE["robot"]

            if robot.get("status") == "running":
                # Basit demo hareket: X ileri-geri, Y yavas artıs, Z sabit
                robot["x"] = int(robot.get("x", 0)) + direction * 2
                robot["y"] = int(robot.get("y", 0)) + 1
                robot["z"] = int(robot.get("z", 0))

                # X belli aralikta gidip gelsin
                if robot["x"] >= 50:
                    direction = -1
                elif robot["x"] <= 0:
                    direction = 1

                # Y
                if robot["y"] >= 200:
                    robot["y"] = 0

            time.sleep(self.interval_s)


# tek instance
robot_service = RobotService()
