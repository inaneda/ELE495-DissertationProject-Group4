"""
File Name       : arduino_service.py
Author          : Eda
Project         : ELE 496 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-04
Last Modified   : 2026-02-04

Description:
This service handles communication with the Arduino board via USB serial.
The Arduino is connected to the Raspberry Pi and provides sensor readings
(e.g., ADC, voltage, component test results).

In this stage, the service runs in demo mode.
Later, real serial communication will be enabled.
"""

import threading
import time

from src.app.routers.status import SYSTEM_STATE


class ArduinoService:
    def __init__(self, interval_s: float = 1.0):
        self.interval_s = interval_s
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._connected = False

    def start(self) -> None:
        """Start Arduino polling thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop Arduino polling thread."""
        self._stop_event.set()

    def _loop(self) -> None:
        """
        Background loop.
        In demo mode, fake Arduino data is generated.
        """
        # test icin arduino varmis gibi !!!!!!!!
        self._connected = True
        SYSTEM_STATE["connections"]["arduino"] = True
        adc_value = 100

        while not self._stop_event.is_set():
            # gercekte burada serial.read olacak !!!!!! sonra bak

            # test icin deger
            adc_value += 5
            if adc_value > 800:
                adc_value = 100

            voltage = round(adc_value * 5.0 / 1023.0, 2)

            SYSTEM_STATE["teststation"]["last_adc"] = adc_value
            SYSTEM_STATE["teststation"]["last_voltage_v"] = voltage
            SYSTEM_STATE["teststation"]["last_result"] = "OK"
            SYSTEM_STATE["teststation"]["last_updated"] = time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            time.sleep(self.interval_s)

        SYSTEM_STATE["connections"]["arduino"] = False


# tek instance
arduino_service = ArduinoService()
