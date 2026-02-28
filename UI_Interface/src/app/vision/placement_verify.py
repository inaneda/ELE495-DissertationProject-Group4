"""
File Name       : placement_verify.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-25
Last Modified   : 2026-02-27

Description:
Placement verification utilities.
Computes a placement quality metric by comparing the detected component bounding-box
(center point) with the expected pad center (in pixel coordinates).
Returns a structured result including distance, tolerance, and an accuracy score.
"""

# inference ayri bir dosya olarak calisiyor, oyle olmasin diye

from __future__ import annotations
import math
from typing import Dict, Tuple, Optional, List

# pad merkezleri (piksel) - simdilik placeholder
PAD_PIXEL_CENTER: Dict[str, Tuple[int, int]] = {
    # "A": (320, 240),
}

def bbox_center(box: list[int]) -> Tuple[int, int]:
    x1, y1, x2, y2 = box
    return int((x1 + x2) / 2), int((y1 + y2) / 2)

def verify_placement(
    pad_label: str,
    det_box: list[int],
    tolerance_px: int = 30,
) -> dict:
    pad_label = pad_label.upper()
    target = PAD_PIXEL_CENTER.get(pad_label)

    cx, cy = bbox_center(det_box)

    if target is None:
        return {
            "pad": pad_label,
            "status": "UNKNOWN_PAD",
            "accuracy": 0.0,
            "distance_px": None,
            "center": {"x": cx, "y": cy},
            "target": None,
            "tolerance_px": tolerance_px,
        }

    tx, ty = target
    dist = math.sqrt((cx - tx) ** 2 + (cy - ty) ** 2)

    # 0...100 skor: dist=0 -> 100, dist>=2*tolerance -> 0
    acc = max(0.0, 100.0 * (1.0 - (dist / (2.0 * tolerance_px))))

    status = "OK" if dist <= tolerance_px else "FAIL"
    return {
        "pad": pad_label,
        "status": status,
        "accuracy": round(acc, 2),
        "distance_px": round(dist, 2),
        "center": {"x": cx, "y": cy},
        "target": {"x": tx, "y": ty},
        "tolerance_px": tolerance_px,
    }