"""
File Name       : robotService.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-22
Last Modified   : 2026-02-25

Description:
High-level robot motion and actuator actions for pick-and-place execution.
This module translates logical actions (PICK, PLACE, MOVE SAFE, GO TO TEST STATION)
into low-level G-code commands sent to the GRBL controller via RobotService.
Coordinate maps (feeder positions, pad positions, test station position) are
intentionally configurable and may be updated during calibration.
"""

import os
from typing import Tuple

# koordinat tablolari (mm)
FEEDER_POS = {
    # part -> (x,y,z)
    # ornek: "R1": (10, 20, -2)
    "R1": (50, 50, 0)
}

PAD_POS = {
    # padLabel -> (x,y,z)
    # ornek: "A": (100, 50, -1)
    "A": (100, 50, -1)
}

TEST_STATION_POS: Tuple[float, float, float] = (0.0, 0.0, 0.0)

# !!!!
SAFE_Z = float(os.environ.get("PNP_SAFE_Z", "5.0"))
PICK_Z = float(os.environ.get("PNP_PICK_Z", "-1.0"))
PLACE_Z = float(os.environ.get("PNP_PLACE_Z", "-1.0"))


def _g0(x: float | None = None, y: float | None = None, z: float | None = None, f: int | None = None) -> str:
    parts = ["G0"]
    if x is not None: parts.append(f"X{x:.3f}")
    if y is not None: parts.append(f"Y{y:.3f}")
    if z is not None: parts.append(f"Z{z:.3f}")
    if f is not None: parts.append(f"F{int(f)}")
    return " ".join(parts)


# def home(robot) -> bool:
#     # grbl home mu kullaniyoruz: $H
#     # mekanik sifir noktasi, koordinat sisteminin reseti, program basinda
#     return robot.send_gcode("$H")


def move_safe(robot) -> bool:
    return robot.send_gcode(_g0(z=SAFE_Z))


def move_to(robot, x: float, y: float, z: float | None = None) -> bool:
    return robot.send_gcode(_g0(x=x, y=y, z=z))


def vacuum(robot, on: bool) -> bool:
    # vakum
    # grbl'de M7/M8 gibi coolant pinleriyle kontrol edilebiliyor
    return robot.send_gcode("M8" if on else "M9")


def pick_part(robot, part: str) -> bool:
    part = part.upper()
    # komponent konumlari == feeder koordinatlari
    if part not in FEEDER_POS:
        #
        return True

    x, y, z = FEEDER_POS[part]
    if not move_safe(robot): return False
    if not move_to(robot, x, y): return False
    if not robot.send_gcode(_g0(z=PICK_Z)): return False
    if not vacuum(robot, True): return False
    if not move_safe(robot): return False
    return True


def goto_test_station(robot) -> bool:
    x, y, z = TEST_STATION_POS
    if not move_safe(robot): return False
    if not move_to(robot, x, y): return False
    return True


def place_part(robot, pad_label: str) -> bool:
    pad_label = pad_label.upper()
    if pad_label not in PAD_POS:
        return True

    x, y, z = PAD_POS[pad_label]
    if not move_safe(robot): return False
    if not move_to(robot, x, y): return False
    if not robot.send_gcode(_g0(z=PLACE_Z)): return False
    if not vacuum(robot, False): return False
    if not move_safe(robot): return False
    return True