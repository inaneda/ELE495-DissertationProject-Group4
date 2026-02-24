"""
File Name       : robotService.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-03
Last Modified   : 2026-02-04

Description:
Robot control service with DEMO and REAL modes.
- DEMO mode: Simulates robot motion
- REAL mode: Communicates with GRBL over serial
"""

import threading
import time
import re
from typing import Dict, Any
#from src.app.routers.status import SYSTEM_STATE


class RobotService:
    def __init__(self, demo_mode: bool = True, port: str = "/dev/ttyACM0", baudrate: int = 115200):
        self.demo_mode = demo_mode
        self.port = port
        self.baudrate = baudrate
        self.interval_s = 0.2 # 200ms polling
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # grbl - sadece real mode'da
        self.ser = None

        # ilk konum - grbl ile guncellenecek veya simulasyon ile - real+demo
        self.position = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.status = "idle"  # idle, running, alarm

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
        """Connect to GRBL (REAL mode only)"""
        if self.demo_mode:
            print("[ROBOT] DEMO mode - no serial connection needed")
            return True
        
        try:
            import serial
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # grbl startup time
            
            # grbl'in karsilama mesajini okuma
            startup_lines = []
            for _ in range(5):
                line = self._safe_readline()
                if line:
                    startup_lines.append(line)
            if startup_lines:
                print("[ROBOT] GRBL startup:", " | ".join(startup_lines))
            
            # soft reset
            self.ser.write(b'\x18')  # Ctrl+X
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
        """Disconnect from GRBL"""
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
        self.status = "disconnected"
        print("[ROBOT] Disconnected from GRBL")

    # g-code gonderme
    def send_gcode(self, gcode: str) -> bool:
        """
        Send G-code command to GRBL (REAL mode) or simulate (DEMO mode)
        """
        if self.demo_mode:
            # demo:
            print(f"[ROBOT DEMO] G-code: {gcode}")
            time.sleep(0.05)
            return True
        
        if not self.ser:
            print("[ROBOT] Not connected to GRBL")
            self.status = "disconnected"
            return False
        
        try:
            self.ser.write((gcode.strip() + "\n").encode("utf-8"))
            
            # grbl'den "ok" bilgisini bekleme
            deadline = time.time() + 1.5
            while time.time() < deadline:
                line = self._safe_readline()
                if not line:
                    continue

                # basarili
                if line.lower().startswith("ok"):
                    print(f"[ROBOT] G-code ok: {gcode}")
                    return True

                # hatali: format: "error:xx"
                if line.lower().startswith("error") or "alarm" in line.lower():
                    print(f"[ROBOT] G-code error for '{gcode}': {line}")
                    self.status = "alarm"
                    return False
                
            print(f"[ROBOT] Timeout waiting ok for: {gcode}")
            return False    
        
        except Exception as e:
            print(f"[ROBOT] Send error: {e}")
            self.status = "error"
            return False
    
    def query_status(self) -> Dict[str, Any]: 
        """Query GRBL status or return simulated status"""
        if self.demo_mode:
            # demo:
            return {
                "status": self.status,
                "x": self.position["x"],
                "y": self.position["y"],
                "z": self.position["z"]
            }
        
        if not self.ser:
            return {"status": "disconnected", "x": 0, "y": 0, "z": 0}
        
        try:
            # durum bilgisini almak icin grbl'e sor
            self.ser.write(b'?\n')
            
            # grbl yaniti formati: <Idle|MPos:...,...,...|FS:...>
            # <...> bu bicimi gorene kadar okuma yapilmali
            for _ in range(8):
                line = self._safe_readline()
                if not line:
                    continue
                if line.startswith("<"):
                    return self._parse_grbl_status(line)
            return {"status": "unknown", "x": 0.0, "y": 0.0, "z": 0.0}
        
        except Exception as e:
            print(f"[ROBOT] Query error: {e}")
            return {"status": "error", "x": 0, "y": 0, "z": 0}
    

    # grbl bilgisi (text biciminde) -> arayuz icin anlamli olabilmesi icin JSON olmali
    def _parse_grbl_status(self, line: str) -> Dict[str, Any]:
        """
        Parse GRBL status line
        Example: <Idle|MPos:...,...,...|FS:...>
        """
        result = {"status": "unknown", "x": 0, "y": 0, "z": 0}
        
        # grbl durum (Idle/Run/Hold/Alarm)
        match = re.search(r'<(\w+)\|', line)
        if match:
            result["status"] = match.group(1).lower()
        
        # koordinatlar (MPos:x,y,z)
        match = re.search(r'MPos:([\d.-]+),([\d.-]+),([\d.-]+)', line)
        if match:
            result["x"] = float(match.group(1))
            result["y"] = float(match.group(2))
            result["z"] = float(match.group(3))
        
        return result
    
    # polling
    def start_polling(self) -> None:
        """Start background status polling"""
        if self._thread and self._thread.is_alive():
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._polling_loop, daemon=True)
        self._thread.start()
        print("[ROBOT] Polling started")

    def stop_polling(self) -> None:
        """Stop background polling"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        print("[ROBOT] Polling stopped")

    def _polling_loop(self) -> None:
        """Background loop for status polling"""
        from src.app.routers.status import SYSTEM_STATE 
        # onceden bastaydi circular import olmasin diye buraya tasidik
        
        # arduino - nema17 (GRBL) baglanti durumu
        if self.demo_mode:
            SYSTEM_STATE["connections"]["arduino_motors"]["status"] = True
            SYSTEM_STATE["connections"]["arduino_motors"]["port"] = self.port  # demo'da port string dursun
        else:
            SYSTEM_STATE["connections"]["arduino_motors"]["status"] = self.ser is not None
            SYSTEM_STATE["connections"]["arduino_motors"]["port"] = self.port if self.ser is not None else None

        direction = 1  # demo icin
        
        while not self._stop_event.is_set():
            if self.demo_mode:
                # demo:
                robot = SYSTEM_STATE["robot"]
                
                if robot.get("status") == "running":
                    # demo hareketi
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
                # demo icin simulasyon
                if robot.get("status") == "running":
                    SYSTEM_STATE["image_processing"] = {
                        "last_detection": {"component": "R1", "type": "resistor", "confidence": 0.92},
                        "last_placement": {"pad": "B", "accuracy": 87.5, "status": "OK"},
                        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S")
                    }
                else:
                    SYSTEM_STATE["image_processing"] = {
                        "last_detection": {"component": None, "type": None, "confidence": None},
                        "last_placement": {"pad": None, "accuracy": None, "status": None},
                        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S")
                    }

            else:
                # real: grbl bilgisi
                data = self.query_status()
                SYSTEM_STATE["robot"].update(data)
                SYSTEM_STATE["grbl"] = {
                    "state": SYSTEM_STATE["robot"].get("status", "unknown"),
                    "mpos": {
                        "x": float(SYSTEM_STATE["robot"].get("x", 0)),
                        "y": float(SYSTEM_STATE["robot"].get("y", 0)),
                        "z": float(SYSTEM_STATE["robot"].get("z", 0))
                    },
                    "last_ok": None,    # ok veya err
                    "last_line": None,  # son gcode
                    "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S")
                }
            
            time.sleep(self.interval_s)

        SYSTEM_STATE["connections"]["arduino_motors"]["status"] = False


robot_service = None

def init_robot_service(demo_mode: bool, port: str = "/dev/ttyACM0"):
    """Initialize robot service singleton"""
    global robot_service
    robot_service = RobotService(demo_mode=demo_mode, port=port)
    return robot_service
    


    