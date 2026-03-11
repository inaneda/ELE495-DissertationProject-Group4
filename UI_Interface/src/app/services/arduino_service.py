"""
File Name       : arduino_service.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-04
Last Modified   : 2026-03-10

Description:
Test station Arduino service with DEMO and REAL modes.

- DEMO mode:
  Simulates a measurement response.

- REAL mode:
  Connects to Arduino over serial.
  Measurement is triggered only when measure() is called.
  Background polling does NOT continuously trigger measurement.

Important:
- Arduino output is passed to the UI.
- Voltage and resistance are parsed separately from Arduino text.
- Resistance values like Ohm / kOhm / MOhm are converted to ohm.
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
        self.interval_s = 1.0
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._connected = False

        self.ser = None

        print(f"[ARDUINO] Initialized in {'DEMO' if demo_mode else 'REAL'} mode")
        print(f"[ARDUINO] Port={self.port}, Baudrate={self.baudrate}")

    def connect(self) -> bool:
        """Connect to Arduino (REAL mode only)."""
        if self.demo_mode:
            print("[ARDUINO] DEMO mode - no serial connection needed")
            self._connected = True
            return True

        try:
            import serial

            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)

            try:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
            except Exception:
                pass

            self._connected = True
            print(f"[ARDUINO] Connected to {self.port} @ {self.baudrate}")
            return True

        except Exception as e:
            print(f"[ARDUINO] Connection failed: {e}")
            self.ser = None
            self._connected = False
            return False

    def disconnect(self):
        """Disconnect from Arduino."""
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

        self._connected = False
        print("[ARDUINO] Disconnected")

    def measure(self) -> Dict[str, Any]:
        """
        Trigger one measurement on Arduino by sending 'b' and return
        Arduino text directly to the UI.

        Returns:
        {
            "mode": "resistor" | "diode" | "none",
            "value_text": "...",
            "voltage": float,
            "resistance_ohm": float | None,
            "result": "...",
            "raw_text": "...",
        }
        """
        if self.demo_mode:
            demo_line = "ADC=505.5  Vout=2.4707 V  R2=9.768 kOhm"
            return {
                "mode": "resistor",
                "value_text": demo_line,
                "voltage": 2.4707,
                "resistance_ohm": 9768.0,
                "result": "OK",
                "raw_text": demo_line,
            }

        if not self.ser or not self._connected:
            return {
                "mode": "none",
                "value_text": "NO_CONNECTION",
                "voltage": 0.0,
                "resistance_ohm": None,
                "result": "NO_CONNECTION",
                "raw_text": "",
            }

        try:
            try:
                self.ser.reset_input_buffer()
            except Exception:
                pass

            # Trigger measurement
            self.ser.write(b"b\n")
            self.ser.flush()
            time.sleep(0.05)

            deadline = time.time() + 10.0
            lines: list[str] = []

            while time.time() < deadline:
                raw = self.ser.readline()
                if not raw:
                    continue

                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                lines.append(line)

                if "Olcum bitti" in line:
                    break

                if "Diyot yonu TERS" in line:
                    break

                if "Diyot yonu DUZ" in line:
                    break

            text = "\n".join(lines)

            print("[ARDUINO RAW TEXT]")
            print(text)

            if not text:
                return {
                    "mode": "none",
                    "value_text": "TIMEOUT",
                    "voltage": 0.0,
                    "resistance_ohm": None,
                    "result": "TIMEOUT",
                    "raw_text": "",
                }

            # Voltage parse
            vout = 0.0
            m_v = re.search(r"Vout\s*=\s*([0-9]+(?:\.[0-9]+)?)", text, flags=re.IGNORECASE)
            if m_v:
                vout = float(m_v.group(1))

            # Resistance parse with unit support: Ohm / kOhm / MOhm
            resistance_ohm = None
            m_r = re.search(
                r"R2\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*([kKmM]?)\s*Ohm",
                text,
                flags=re.IGNORECASE
            )
            if m_r:
                value = float(m_r.group(1))
                prefix = (m_r.group(2) or "").lower()

                if prefix == "k":
                    resistance_ohm = value * 1000.0
                elif prefix == "m":
                    resistance_ohm = value * 1000000.0
                else:
                    resistance_ohm = value

            value_line = text.replace("\n", " | ")

            if "Diyot yonu TERS" in text:
                return {
                    "mode": "diode",
                    "value_text": value_line,
                    "voltage": vout,
                    "resistance_ohm": None,
                    "result": "DIODE_REVERSED",
                    "raw_text": text,
                }

            if "Diyot yonu DUZ" in text:
                return {
                    "mode": "diode",
                    "value_text": value_line,
                    "voltage": vout,
                    "resistance_ohm": None,
                    "result": "DIODE_FORWARD",
                    "raw_text": text,
                }

            if "Gecerli olcum alinamadi" in text:
                return {
                    "mode": "none",
                    "value_text": value_line,
                    "voltage": vout,
                    "resistance_ohm": resistance_ohm,
                    "result": "INVALID",
                    "raw_text": text,
                }

            return {
                "mode": "resistor",
                "value_text": value_line,
                "voltage": vout,
                "resistance_ohm": resistance_ohm,
                "result": "OK",
                "raw_text": text,
            }

        except Exception as e:
            print(f"[ARDUINO] Measurement error: {e}")
            return {
                "mode": "none",
                "value_text": "ERROR",
                "voltage": 0.0,
                "resistance_ohm": None,
                "result": "ERROR",
                "raw_text": "",
            }

    def start_polling(self):
        """Start background polling thread."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._polling_loop, daemon=True)
        self._thread.start()
        print("[ARDUINO] Polling started")

    def stop_polling(self):
        """Stop background polling thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        print("[ARDUINO] Polling stopped")

    def _polling_loop(self):
        """
        Background loop.

        DEMO mode updates fake values.
        REAL mode does NOT call measure() continuously.
        """
        from src.app.routers.status import SYSTEM_STATE

        SYSTEM_STATE["connections"]["arduino_teststation"]["status"] = self._connected
        SYSTEM_STATE["connections"]["arduino_teststation"]["port"] = self.port if self._connected else None

        adc_demo_value = 100

        while not self._stop_event.is_set():
            if self.demo_mode:
                adc_demo_value += 5
                if adc_demo_value > 800:
                    adc_demo_value = 100

                voltage = round(adc_demo_value * 5.0 / 1023.0, 2)
                demo_line = f"ADC={adc_demo_value}  Vout={voltage} V  R2=9.768 kOhm"

                SYSTEM_STATE["teststation"]["last_adc"] = adc_demo_value
                SYSTEM_STATE["teststation"]["last_voltage_v"] = voltage
                SYSTEM_STATE["teststation"]["last_resistance_ohm"] = 9768.0
                SYSTEM_STATE["teststation"]["last_result"] = "OK"
                SYSTEM_STATE["teststation"]["mode"] = "resistor"
                SYSTEM_STATE["teststation"]["value_text"] = demo_line
                SYSTEM_STATE["teststation"]["raw_text"] = demo_line
                SYSTEM_STATE["teststation"]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")

                if "measurements" in SYSTEM_STATE:
                    if "voltage" in SYSTEM_STATE["measurements"]:
                        SYSTEM_STATE["measurements"]["voltage"] = voltage
                    if "resistance_ohm" in SYSTEM_STATE["measurements"]:
                        SYSTEM_STATE["measurements"]["resistance_ohm"] = 9768.0
                    if "result" in SYSTEM_STATE["measurements"]:
                        SYSTEM_STATE["measurements"]["result"] = "OK"
                    if "value_text" in SYSTEM_STATE["measurements"]:
                        SYSTEM_STATE["measurements"]["value_text"] = demo_line
                    if "raw_text" in SYSTEM_STATE["measurements"]:
                        SYSTEM_STATE["measurements"]["raw_text"] = demo_line

            else:
                SYSTEM_STATE["connections"]["arduino_teststation"]["status"] = self._connected
                SYSTEM_STATE["connections"]["arduino_teststation"]["port"] = self.port if self._connected else None
                SYSTEM_STATE["teststation"]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")

            time.sleep(self.interval_s)

        SYSTEM_STATE["connections"]["arduino_teststation"]["status"] = False


arduino_service = None


def init_arduino_service(demo_mode: bool, port: str = "/dev/ttyUSB0", baudrate: int = 9600):
    """Initialize Arduino service singleton."""
    global arduino_service
    arduino_service = ArduinoService(
        demo_mode=demo_mode,
        port=port,
        baudrate=baudrate,
    )
    return arduino_service
