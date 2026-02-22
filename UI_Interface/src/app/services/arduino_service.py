"""
File Name       : arduino_service.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-04
Last Modified   : 2026-02-04

Description:
This service handles communication with the Arduino board via USB serial.
The Arduino is connected to the Raspberry Pi and provides sensor readings
(e.g., ADC, voltage, component test results).

Description:
Test station Arduino service with DEMO and REAL modes.
- DEMO mode: Simulates ADC readings
- REAL mode: Reads from Arduino via USB serial
"""

import threading
import time
from typing import Dict, Any


class ArduinoService:
    def __init__(self, demo_mode: bool = True, port: str = "/dev/ttyUSB0", baudrate: int = 9600):
        self.demo_mode = demo_mode
        self.port = port
        self.baudrate = baudrate
        self.interval_s = 1.0 # 1s polling
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._connected = False

        # real: serial baglanti 
        self.ser = None
        print(f"[ARDUINO] Initialized in {'DEMO' if demo_mode else 'REAL'} mode")

    def connect(self) -> bool:
        """Connect to Arduino (REAL mode only)"""
        if self.demo_mode:
            print("[ARDUINO] DEMO mode - no serial connection needed")
            self._connected = True
            return True
        try:
            import serial
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)
            print(f"[ARDUINO] Connected to {self.port}")
            self._connected = True
            return True
           
        except Exception as e:
            print(f"[ARDUINO] Connection failed: {e}")
            self._connected = False
            return False
    
    def disconnect(self):
        """Disconnect from Arduino"""
        if self.ser:
            self.ser.close()
            self.ser = None
        self._connected = False
        print("[ARDUINO] Disconnected")

    def read_adc(self) -> Dict[str, Any]:
        """Read ADC value from Arduino or simulate"""
        if self.demo_mode:
            # demo:
            import random
            adc_value = random.randint(100, 800)
            voltage = round(adc_value * 5.0 / 1023.0, 2)
            
            return {
                "adc": adc_value,
                "voltage": voltage,
                "result": "OK" if voltage < 4.5 else "HIGH"
            }
        
        if not self.ser or not self._connected:
            return {"adc": 0, "voltage": 0.0, "result": "NO_CONNECTION"}
        
        try:
            # real:
            line = self.ser.readline().decode('utf-8').strip()
            
            if line.startswith("ADC:"):
                adc_value = int(line.split(":")[1])
                voltage = round(adc_value * 5.0 / 1023.0, 2)
                
                return {
                    "adc": adc_value,
                    "voltage": voltage,
                    "result": "OK"
                }
            else:
                return {"adc": 0, "voltage": 0.0, "result": "PARSE_ERROR"}
                
        except Exception as e:
            print(f"[ARDUINO] Read error: {e}")
            return {"adc": 0, "voltage": 0.0, "result": "ERROR"}


    def start_polling(self):
        """Start background polling"""
        if self._thread and self._thread.is_alive():
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._polling_loop, daemon=True)
        self._thread.start()
        print("[ARDUINO] Polling started")
    
    def stop_polling(self):
        """Stop background polling"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        print("[ARDUINO] Polling stopped")
    
    def _polling_loop(self):
        """Background loop for ADC polling"""
        # circular import olamsin diye fonksiyon icine alindi
        from src.app.routers.status import SYSTEM_STATE
        
        # baglanti durumu guncellemesi icin
        SYSTEM_STATE["connections"]["arduino_teststation"]["status"] = self._connected
        SYSTEM_STATE["connections"]["arduino_teststation"]["port"] = self.port if self._connected else None
        
        # demo: 
        adc_demo_value = 100
        
        while not self._stop_event.is_set():
            if self.demo_mode:
                # demo:
                adc_demo_value += 5
                if adc_demo_value > 800:
                    adc_demo_value = 100
                
                voltage = round(adc_demo_value * 5.0 / 1023.0, 2)
                
                SYSTEM_STATE["teststation"]["last_adc"] = adc_demo_value
                SYSTEM_STATE["teststation"]["last_voltage_v"] = voltage
                SYSTEM_STATE["teststation"]["last_result"] = "OK"
                SYSTEM_STATE["teststation"]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            else:
                # real:
                data = self.read_adc()
                
                SYSTEM_STATE["teststation"]["last_adc"] = data["adc"]
                SYSTEM_STATE["teststation"]["last_voltage_v"] = data["voltage"]
                SYSTEM_STATE["teststation"]["last_result"] = data["result"]
                SYSTEM_STATE["teststation"]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            
            time.sleep(self.interval_s)
        
        # durduguunda baglanti yok diye
        SYSTEM_STATE["connections"]["arduino_teststation"]["status"] = False
    

arduino_service = None

def init_arduino_service(demo_mode: bool, port: str = "/dev/ttyUSB0"):
    """Initialize Arduino service singleton"""
    global arduino_service
    arduino_service = ArduinoService(demo_mode=demo_mode, port=port)
    return arduino_service
