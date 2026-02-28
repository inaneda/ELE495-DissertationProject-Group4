"""
File Name       : arduino_service.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-04
Last Modified   : 2026-02-04

Description:
Test station Arduino service with DEMO and REAL modes.
- DEMO mode: Simulates ADC readings
- REAL mode: Reads from Arduino via USB serial
"""

import threading
import time
import re
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

    # def read_adc(self) -> Dict[str, Any]:
    #     """Read ADC value from Arduino or simulate"""
    #     if self.demo_mode:
    #         # demo:
    #         import random
    #         adc_value = random.randint(100, 800)
    #         voltage = round(adc_value * 5.0 / 1023.0, 2)
            
    #         return {
    #             "adc": adc_value,
    #             "voltage": voltage,
    #             "result": "OK" if voltage < 4.5 else "HIGH"
    #         }
        
    #     if not self.ser or not self._connected:
    #         return {"adc": 0, "voltage": 0.0, "result": "NO_CONNECTION"}
        
    #     try:
    #         # real:
    #         line = self.ser.readline().decode('utf-8').strip()
            
    #         if line.startswith("ADC:"):
    #             adc_value = int(line.split(":")[1])
    #             voltage = round(adc_value * 5.0 / 1023.0, 2)
                
    #             return {
    #                 "adc": adc_value,
    #                 "voltage": voltage,
    #                 "result": "OK"
    #             }
    #         else:
    #             return {"adc": 0, "voltage": 0.0, "result": "PARSE_ERROR"}
                
    #     except Exception as e:
    #         print(f"[ARDUINO] Read error: {e}")
    #         return {"adc": 0, "voltage": 0.0, "result": "ERROR"}

    def measure(self) -> Dict[str, Any]:
        """
        Trigger measurement on Arduino (send 'b') and parse returned text.
        Returns fields compatible with SYSTEM_STATE['teststation'].
        """
        if self.demo_mode:
            # demo
            return {
                "mode": "resistor",
                "value_text": "4.700 kOhm",
                "voltage": 0.0,
                "result": "OK",
            }

        if not self.ser or not self._connected:
            return {"mode": "none", "value_text": "-", "voltage": 0.0, "result": "NO_CONNECTION"}

        try:
            # giris buffer - temizleme 
            try:
                self.ser.reset_input_buffer()
            except Exception:
                pass

            # olcumu tetikleme
            self.ser.write(b"b")
            self.ser.flush()

            deadline = time.time() + 10.0  # servo ters diyotta 5sn bekliyor
            lines: list[str] = []

            while time.time() < deadline:
                raw = self.ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                lines.append(line)

                # erken cikis
                if "Olcum bitti" in line:
                    break

                # ters diyotta arduino return ediyor (servo hareketi yapip return)
                if "Diyot yonu TERS" in line:
                    break

            text = "\n".join(lines)

            # 1) ters diyot / open circuit
            if "Diyot yonu TERS" in text:
                return {
                    "mode": "diode",
                    "value_text": "OPEN",
                    "voltage": 0.0,
                    "result": "DIODE_REVERSED",
                }

            # 2) gecerli degil
            if "Gecerli olcum alinamadi" in text:
                return {"mode": "none", "value_text": "-", "voltage": 0.0, "result": "INVALID"}

            # 3) DUZ diyot veya direnc: ADC=... Vout=... R2=...
            # ornek: "ADC=123.4  Vout=0.1234 V  R2=456.7 Ohm   Diyot yonu DUZ"
            vout = 0.0
            m_v = re.search(r"Vout=([0-9]+(?:\.[0-9]+)?)", text)
            if m_v:
                vout = float(m_v.group(1))

            # R2 parse (Ohm / kOhm)
            value_text = "-"
            m_r_k = re.search(r"R2=([0-9]+(?:\.[0-9]+)?)\s*kOhm", text, flags=re.IGNORECASE)
            m_r_o = re.search(r"R2=([0-9]+(?:\.[0-9]+)?)\s*Ohm", text, flags=re.IGNORECASE)
            if m_r_k:
                value_text = f"{float(m_r_k.group(1)):.3f} kOhm"
            elif m_r_o:
                value_text = f"{float(m_r_o.group(1)):.1f} Ohm"

            if "Diyot yonu DUZ" in text:
                # acik devre degil
                return {
                    "mode": "diode",
                    "value_text": "NOT OPEN",
                    "voltage": vout,
                    "result": "DIODE_FORWARD",
                }

            # direnc durumunda
            return {
                "mode": "resistor",
                "value_text": value_text,
                "voltage": vout,
                "result": "RESISTOR_OK",
            }

        except Exception as e:
            print(f"[ARDUINO] Measure error: {e}")
            return {"mode": "none", "value_text": "-", "voltage": 0.0, "result": "ERROR"}


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
                SYSTEM_STATE["teststation"]["last_adc"] = data["adc"]
                SYSTEM_STATE["teststation"]["last_voltage_v"] = data["voltage"]
                SYSTEM_STATE["teststation"]["last_result"] = data["result"]
                SYSTEM_STATE["teststation"]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
                SYSTEM_STATE["connections"]["arduino_teststation"]["status"] = self._connected
                SYSTEM_STATE["connections"]["arduino_teststation"]["port"] = self.port if self._connected else None
            
            time.sleep(self.interval_s)
        
        # durduguunda baglanti yok diye
        SYSTEM_STATE["connections"]["arduino_teststation"]["status"] = False
    

arduino_service = None

def init_arduino_service(demo_mode: bool, port: str = "/dev/ttyUSB0", baudrate: int = 115200):
    """Initialize Arduino service singleton"""
    global arduino_service
    arduino_service = ArduinoService(demo_mode=demo_mode, port=port, baudrate=baudrate)
    return arduino_service
