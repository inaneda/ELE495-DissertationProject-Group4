"""
File Name       : robotService.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-03
Last Modified   : 2026-03-07

Description:
Robot control service with DEMO and REAL modes.
- DEMO mode: Simulates robot motion
- REAL mode: Communicates with GRBL over serial
"""

import threading
import time
import re
from typing import Dict, Any


class RobotService:

    def __init__(self, demo_mode: bool = True, port: str = "/dev/ttyACM0", baudrate: int = 115200):
        self.demo_mode = demo_mode
        self.port = port
        self.baudrate = baudrate
        self.interval_s = 0.2  # 200ms polling
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self._serial_lock = threading.Lock()
        self.ser = None

        self.position = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.status = "idle"  # idle, running, alarm, disconnected, error

        print(f"[ROBOT] Initialized in {'DEMO' if demo_mode else 'REAL'} mode")

    def _safe_readline(self) -> str:
        """Read a line safely from serial (REAL mode)."""
        if not self.ser:
            return ""
        try:
            return self.ser.readline().decode("utf-8", errors="ignore").strip()
        except Exception:
            return ""

    def _drain_input(self, max_lines: int = 20) -> None:
        """Drain some pending lines to clear buffer (REAL mode)."""
        if not self.ser:
            return
        for _ in range(max_lines):
            line = self._safe_readline()
            if not line:
                break

    def connect(self) -> bool:
        """Connect to GRBL (REAL mode only)."""
        if self.demo_mode:
            print("[ROBOT] DEMO mode - no serial connection needed")
            return True

        try:
            import serial

            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)

            startup_lines = []
            for _ in range(5):
                line = self._safe_readline()
                if line:
                    startup_lines.append(line)
            if startup_lines:
                print("[ROBOT] GRBL startup:", " | ".join(startup_lines))

            # soft reset
            self.ser.write(b"\x18")
            time.sleep(1)

            self._drain_input()
            self.status = "idle"
            print(f"[ROBOT] Connected to GRBL on {self.port} @ {self.baudrate}")
            return True

        except Exception as e:
            print(f"[ROBOT] Connection failed: {e}")
            self.ser = None
            self.status = "disconnected"
            return False

    def disconnect(self) -> None:
        """Disconnect from GRBL."""
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

        self.status = "disconnected"
        print("[ROBOT] Disconnected from GRBL")

    def _parse_grbl_status(self, line: str) -> Dict[str, Any]:
        """
        Parse GRBL status line.
        Example: <Idle|MPos:...,...,...|FS:...>
        """
        result = {"status": "unknown", "x": 0.0, "y": 0.0, "z": 0.0}

        match = re.search(r"<(\w+)\|", line)
        if match:
            result["status"] = match.group(1).lower()

        match = re.search(r"MPos:([\d.-]+),([\d.-]+),([\d.-]+)", line)
        if match:
            result["x"] = float(match.group(1))
            result["y"] = float(match.group(2))
            result["z"] = float(match.group(3))

        return result

    def _query_status_locked(self) -> Dict[str, Any]:
        """
        Query GRBL status.
        Must be called while serial lock is already held.
        """
        if not self.ser:
            return {"status": "disconnected", "x": 0.0, "y": 0.0, "z": 0.0}

        try:
            self.ser.write(b"?\n")
            deadline = time.time() + 2.0

            while time.time() < deadline:
                line = self._safe_readline()
                if not line:
                    continue
                if line.startswith("<"):
                    return self._parse_grbl_status(line)

            return {"status": "unknown", "x": 0.0, "y": 0.0, "z": 0.0}

        except Exception as e:
            print(f"[ROBOT] Status query error: {e}")
            return {"status": "error", "x": 0.0, "y": 0.0, "z": 0.0}

    def _wait_until_idle_locked(self, timeout_s: float = 30.0) -> bool:
        """
        Wait until GRBL becomes Idle.
        Must be called while serial lock is already held.
        """
        deadline = time.time() + timeout_s

        while time.time() < deadline:
            status = self._query_status_locked()
            state = status.get("status", "unknown")

            if state == "idle":
                self.position["x"] = status.get("x", 0.0)
                self.position["y"] = status.get("y", 0.0)
                self.position["z"] = status.get("z", 0.0)
                self.status = "idle"
                return True

            if state in ("alarm", "error"):
                self.status = state
                print(f"[ROBOT] Machine entered {state} while waiting for Idle")
                return False

            self.position["x"] = status.get("x", 0.0)
            self.position["y"] = status.get("y", 0.0)
            self.position["z"] = status.get("z", 0.0)
            self.status = state
            time.sleep(0.05)

        print("[ROBOT] Timeout waiting for machine to become Idle")
        return False

    def _needs_idle_wait(self, cmd: str) -> bool:
        """
        Commands that should complete physically before next step.
        """
        cmd = cmd.strip().upper()
        return (
            cmd.startswith("G0")
            or cmd.startswith("G1")
            or cmd.startswith("G2")
            or cmd.startswith("G3")
            or cmd.startswith("G38")
            or cmd.startswith("G4")
        )

    def _command_timeout(self, cmd: str) -> float:
        """
        Timeout for waiting parser response / command handling.
        """
        cmd_u = cmd.strip().upper()

        if cmd_u.startswith("G38.2"):
            return 90.0

        if cmd_u.startswith("G4"):
            # Parse dwell time from P word if possible
            m = re.search(r"\bP([0-9]+(?:\.[0-9]+)?)\b", cmd_u)
            if m:
                dwell_s = float(m.group(1))
                return max(10.0, dwell_s + 10.0)
            return 15.0

        return 10.0

    def _idle_wait_timeout(self, cmd: str) -> float:
        cmd_u = cmd.strip().upper()

        if cmd_u.startswith("G38.2"):
            return 90.0

        if cmd_u.startswith("G4"):
            m = re.search(r"\bP([0-9]+(?:\.[0-9]+)?)\b", cmd_u)
            if m:
                dwell_s = float(m.group(1))
                return max(10.0, dwell_s + 10.0)
            return 15.0

        if cmd_u.startswith(("G0", "G1", "G2", "G3")):
            return 30.0

        return 10.0

    def send_gcode(self, gcode: str) -> bool:
        """
        Send G-code command to GRBL (REAL mode) or simulate (DEMO mode).
        """
        if self.demo_mode:
            print(f"[ROBOT DEMO] G-code: {gcode}")
            time.sleep(0.05)
            return True

        if not self.ser:
            print("[ROBOT] Not connected to GRBL")
            self.status = "disconnected"
            return False

        try:
            cmd = gcode.strip()
            if not cmd:
                return True

            with self._serial_lock:
                self._drain_input(max_lines=10)

                print(f"[ROBOT] SEND: {cmd}")
                self.ser.write((cmd + "\n").encode("utf-8"))

                deadline = time.time() + self._command_timeout(cmd)
                got_ok = False

                while time.time() < deadline:
                    line = self._safe_readline()
                    if not line:
                        continue

                    print(f"[ROBOT] RESP for '{cmd}': {line}")

                    # GRBL status / feedback lines
                    if line.startswith("<") or line.startswith("["):
                        continue

                    if line.lower().startswith("ok"):
                        got_ok = True
                        break

                    if line.lower().startswith("error") or line.lower().startswith("alarm"):
                        print(f"[ROBOT] G-code error for '{cmd}': {line}")
                        self.status = "alarm"
                        return False

                if not got_ok:
                    print(f"[ROBOT] Timeout waiting ok for: {cmd}")
                    self.status = "error"
                    return False

                print(f"[ROBOT] G-code ok: {cmd}")

                # IMPORTANT:
                # For motion/probe/dwell, wait until machine is actually idle
                if self._needs_idle_wait(cmd):
                    idle_ok = self._wait_until_idle_locked(
                        timeout_s=self._idle_wait_timeout(cmd)
                    )
                    if not idle_ok:
                        print(f"[ROBOT] Machine did not become Idle after: {cmd}")
                        return False

                return True

        except Exception as e:
            print(f"[ROBOT] Send error: {e}")
            self.status = "error"
            return False

    def query_status(self) -> Dict[str, Any]:
        """Query GRBL status or return simulated status."""
        if self.demo_mode:
            return {
                "status": self.status,
                "x": self.position["x"],
                "y": self.position["y"],
                "z": self.position["z"],
            }

        if not self.ser:
            return {"status": "disconnected", "x": 0, "y": 0, "z": 0}

        try:
            with self._serial_lock:
                result = self._query_status_locked()
                self._drain_input(max_lines=4)
                return result

        except Exception as e:
            print(f"[ROBOT] Query error: {e}")
            return {"status": "error", "x": 0, "y": 0, "z": 0}

    def start_polling(self) -> None:
        """Start background status polling."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._polling_loop, daemon=True)
        self._thread.start()
        print("[ROBOT] Polling started")

    def stop_polling(self) -> None:
        """Stop background status polling."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        print("[ROBOT] Polling stopped")

    def _polling_loop(self) -> None:
        """Background loop for status polling."""
        from src.app.routers.status import SYSTEM_STATE

        if self.demo_mode:
            SYSTEM_STATE["connections"]["arduino_motors"]["status"] = True
            SYSTEM_STATE["connections"]["arduino_motors"]["port"] = self.port
        else:
            SYSTEM_STATE["connections"]["arduino_motors"]["status"] = self.ser is not None
            SYSTEM_STATE["connections"]["arduino_motors"]["port"] = self.port if self.ser is not None else None

        direction = 1

        while not self._stop_event.is_set():
            if self.demo_mode:
                robot = SYSTEM_STATE["robot"]

                if robot.get("status") == "running":
                    self.position["x"] = self.position.get("x", 0) + direction * 2
                    self.position["y"] = self.position.get("y", 0) + 1

                    if self.position["x"] >= 50:
                        direction = -1
                    elif self.position["x"] <= 0:
                        direction = 1

                    if self.position["y"] >= 200:
                        self.position["y"] = 0

                    robot["x"] = int(self.position["x"])
                    robot["y"] = int(self.position["y"])
                    robot["z"] = int(self.position.get("z", 0))
                    robot["status"] = "running"
                    self.status = "running"
                else:
                    robot["status"] = robot.get("status", "idle")
                    self.status = robot["status"]

                SYSTEM_STATE["grbl"] = {
                    "state": robot.get("status", "idle"),
                    "mpos": {
                        "x": float(robot.get("x", 0)),
                        "y": float(robot.get("y", 0)),
                        "z": float(robot.get("z", 0)),
                    },
                    "last_ok": True,
                    "last_line": "G0 X... Y... (demo)",
                    "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }

                if robot.get("status") == "running":
                    SYSTEM_STATE["image_processing"] = {
                        "last_detection": {"component": "R1", "type": "resistor", "confidence": 0.92},
                        "last_placement": {"pad": "B", "accuracy": 87.5, "status": "OK"},
                        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    }
                else:
                    SYSTEM_STATE["image_processing"] = {
                        "last_detection": {"component": None, "type": None, "confidence": None},
                        "last_placement": {"pad": None, "accuracy": None, "status": None},
                        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    }

            else:
                data = self.query_status()
                SYSTEM_STATE["robot"].update(data)
                SYSTEM_STATE["grbl"] = {
                    "state": SYSTEM_STATE["robot"].get("status", "unknown"),
                    "mpos": {
                        "x": float(SYSTEM_STATE["robot"].get("x", 0)),
                        "y": float(SYSTEM_STATE["robot"].get("y", 0)),
                        "z": float(SYSTEM_STATE["robot"].get("z", 0)),
                    },
                    "last_ok": None,
                    "last_line": None,
                    "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }

            time.sleep(self.interval_s)

        SYSTEM_STATE["connections"]["arduino_motors"]["status"] = False


robot_service = None


def init_robot_service(demo_mode: bool, port: str = "/dev/ttyACM0"):
    """Initialize robot service singleton."""
    global robot_service
    robot_service = RobotService(demo_mode=demo_mode, port=port)
    return robot_service
def wait_until_idle(self, timeout: float = 30.0) -> bool:
    import time

    start = time.time()

    while time.time() - start < timeout:
        status = self.get_status()

        if status and "Idle" in status:
            return True

        time.sleep(0.05)

    return False
