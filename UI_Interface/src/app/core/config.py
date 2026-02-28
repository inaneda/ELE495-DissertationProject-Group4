"""
File Name       : config.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-01
Last Modified   : 2026-02-25

Application configuration values.
These settings are used across the backend services.
"""

import os
from dotenv import load_dotenv
load_dotenv()


# WLAN / API security
API_KEY: str = os.environ.get("PNP_API_KEY", "dev-key-change-me")


# camera
CAMERA_DEVICE_INDEX: int = int(os.environ.get("PNP_CAMERA_INDEX", "0"))


# demo mode (set DEMO_MODE=false for real hardware)
DEMO_MODE: bool = os.environ.get("DEMO_MODE", "true").lower() == "true"

# serial ports (real)
ROBOT_PORT: str = os.environ.get("PNP_ROBOT_PORT", "/dev/ttyACM0")
TESTSTATION_PORT: str = os.environ.get("PNP_TESTSTATION_PORT", "/dev/ttyUSB0")

# baudrates sonra bak!!
ROBOT_BAUDRATE: int = int(os.environ.get("PNP_ROBOT_BAUD", "115200"))
TESTSTATION_BAUDRATE: int = int(os.environ.get("PNP_TESTSTATION_BAUD", "115200"))