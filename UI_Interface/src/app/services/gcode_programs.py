"""
File Name       : gcode_programs.py
Author          : Eda
Description:
Fixed Pick&Place program definition.
Runs the exact proven Baboli sequence in the same order.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, List


@dataclass
class Step:
    id: str
    label: str
    gcode: str | List[str]
    marks_done_component: Optional[str] = None
    vacuum_expected: Optional[bool] = None
    trigger_measurement: bool = False


def _normalize_gcode(x: str | List[str]) -> List[str]:
    if isinstance(x, list):
        return [s.strip() for s in x if s and s.strip()]
    return [s.strip() for s in x.split(";") if s.strip()]


GCODE: Dict[str, str | List[str]] = {
    # ------------------------------------------------
    # BASLANGIC VE Z PROBE
    # ------------------------------------------------
    "HOME": [
        "G92 X0 Y0",
        "G0 X10 Y10",
        "G38.2 Z-60 F60",
        "G92 Z0",
    ],

    # ------------------------------------------------
    # 1. BLOK
    # ------------------------------------------------
    "BLOCK_1_PICK": [
        "G0 X15 Y62",
        "G1 Z26 F200",
        "M8",
        "G0 Z15",
    ],
    "BLOCK_1_TEST": [
        "G0 X263.997 Y100.000",
        "G1 Z26 F200",
        "G4 P3",
        "G0 Z15",
    ],
    "BLOCK_1_PLACE": [
        "G0 X592.218 Y365.000",
        "G1 Z24.5 F200",
        "M9",
        "G0 Z15",
    ],

    # ------------------------------------------------
    # 2. BLOK
    # ------------------------------------------------
    "BLOCK_2_PICK": [
        "G0 X15 Y87.5",
        "G1 Z19 F200",
        "M8",
        "G0 Z15",
    ],
    "BLOCK_2_TEST": [
        "G0 X263.997 Y100.000",
        "G1 Z19 F200",
        "G4 P3",
        "G0 Z15",
    ],
    "BLOCK_2_PLACE": [
        "G0 X592.218 Y410.000",
        "G1 Z19 F200",
        "M9",
        "G0 Z15",
    ],

    # ------------------------------------------------
    # 3. BLOK
    # ------------------------------------------------
    "BLOCK_3_PICK": [
        "G0 X15 Y112.5",
        "G1 Z19 F200",
        "M8",
        "G0 Z15",
    ],
    "BLOCK_3_TEST": [
        "G0 X263.997 Y100.000",
        "G1 Z19 F200",
        "G4 P3",
        "G0 Z15",
    ],
    "BLOCK_3_PLACE": [
        "G0 X638.000 Y371.591",
        "G1 Z19 F200",
        "M9",
        "G0 Z15",
    ],

    # ------------------------------------------------
    # 4. BLOK
    # ------------------------------------------------
    "BLOCK_4_PICK": [
        "G0 X15 Y137.5",
        "G1 Z19 F200",
        "M8",
        "G0 Z15",
    ],
    "BLOCK_4_TEST": [
        "G0 X263.997 Y100.000",
        "G1 Z19 F200",
        "G4 P3",
        "M9",
        "G0 Z15",
        "G4 P5",
        "G1 Z19 F200",
        "M8",
        "G0 Z15",
    ],
    "BLOCK_4_PLACE": [
        "G0 X638.000 Y410.000",
        "G1 Z19 F200",
        "M9",
        "G0 Z15",
    ],

    # ------------------------------------------------
    # 5. BLOK
    # ------------------------------------------------
    "BLOCK_5_PICK": [
        "G0 X15 Y162.5",
        "G1 Z19 F200",
        "M8",
        "G0 Z15",
    ],
    "BLOCK_5_TEST": [
        "G0 X263.997 Y100.000",
        "G1 Z19 F200",
        "G4 P3",
        "G0 Z15",
    ],
    "BLOCK_5_RETURN": [
        "G0 X15 Y162.5",
        "G1 Z19 F200",
        "M9",
        "G0 Z15",
    ],

    # ------------------------------------------------
    # 6. BLOK
    # ------------------------------------------------
    "BLOCK_6_PICK": [
        "G0 X15 Y187.5",
        "G1 Z19 F200",
        "M8",
        "G0 Z15",
    ],
    "BLOCK_6_TEST": [
        "G0 X263.997 Y100.000",
        "G1 Z19 F200",
        "G4 P3",
        "G0 Z15",
    ],
    "BLOCK_6_RETURN": [
        "G0 X15 Y187.5",
        "G1 Z19 F200",
        "M9",
        "G0 Z15",
    ],

    # ------------------------------------------------
    # 7. KONUM
    # ------------------------------------------------
    "BLOCK_7_PICK": [
        "G0 X15 Y212.5",
        "G1 Z19 F200",
        "M8",
        "G0 Z15",
    ],
    "BLOCK_7_TEST": [
        "G0 X263.997 Y100.000",
        "G1 Z19 F200",
        "G4 P3",
        "G0 Z15",
    ],
    "BLOCK_7_RETURN": [
        "G0 X15 Y212.5",
        "G1 Z19 F200",
        "M9",
        "G0 Z15",
    ],

    # ------------------------------------------------
    # 8. KONUM
    # ------------------------------------------------
    "BLOCK_8_PICK": [
        "G0 X15 Y237.5",
        "G1 Z19 F200",
        "M8",
        "G0 Z15",
    ],
    "BLOCK_8_TEST": [
        "G0 X263.997 Y100.000",
        "G1 Z19 F200",
        "G4 P3",
        "G0 Z15",
    ],
    "BLOCK_8_RETURN": [
        "G0 X15 Y237.5",
        "G1 Z19 F200",
        "M9",
        "G0 Z15",
    ],
}


def validate_required_gcodes() -> None:
    required = [
        "HOME",

        "BLOCK_1_PICK", "BLOCK_1_TEST", "BLOCK_1_PLACE",
        "BLOCK_2_PICK", "BLOCK_2_TEST", "BLOCK_2_PLACE",
        "BLOCK_3_PICK", "BLOCK_3_TEST", "BLOCK_3_PLACE",
        "BLOCK_4_PICK", "BLOCK_4_TEST", "BLOCK_4_PLACE",
        "BLOCK_5_PICK", "BLOCK_5_TEST", "BLOCK_5_RETURN",
        "BLOCK_6_PICK", "BLOCK_6_TEST", "BLOCK_6_RETURN",
        "BLOCK_7_PICK", "BLOCK_7_TEST", "BLOCK_7_RETURN",
        "BLOCK_8_PICK", "BLOCK_8_TEST", "BLOCK_8_RETURN",
    ]

    missing = []
    for k in required:
        if k not in GCODE:
            missing.append(f"{k} (missing key)")
            continue

        v = GCODE[k]
        if isinstance(v, list):
            ok = any((s or "").strip() for s in v)
        else:
            ok = bool((v or "").strip())

        if not ok:
            missing.append(k)

    if missing:
        raise ValueError(
            "GCODE table has empty/missing entries:\n- " + "\n- ".join(missing)
        )


def build_program() -> List[Step]:
    steps: List[Step] = [
        Step(
            id="HOME",
            label="Go to HOME (startup position)",
            gcode=GCODE["HOME"],
            vacuum_expected=False,
            trigger_measurement=False,
        ),

        Step("BLOCK_1_PICK", "1. BLOK PICK", GCODE["BLOCK_1_PICK"], vacuum_expected=True),
        Step("BLOCK_1_TEST", "1. BLOK TEST", GCODE["BLOCK_1_TEST"], vacuum_expected=True, trigger_measurement=True),
        Step("BLOCK_1_PLACE", "1. BLOK PLACE", GCODE["BLOCK_1_PLACE"], vacuum_expected=False, marks_done_component="R1"),

        Step("BLOCK_2_PICK", "2. BLOK PICK", GCODE["BLOCK_2_PICK"], vacuum_expected=True),
        Step("BLOCK_2_TEST", "2. BLOK TEST", GCODE["BLOCK_2_TEST"], vacuum_expected=True, trigger_measurement=True),
        Step("BLOCK_2_PLACE", "2. BLOK PLACE", GCODE["BLOCK_2_PLACE"], vacuum_expected=False, marks_done_component="R2"),

        Step("BLOCK_3_PICK", "3. BLOK PICK", GCODE["BLOCK_3_PICK"], vacuum_expected=True),
        Step("BLOCK_3_TEST", "3. BLOK TEST", GCODE["BLOCK_3_TEST"], vacuum_expected=True, trigger_measurement=True),
        Step("BLOCK_3_PLACE", "3. BLOK PLACE", GCODE["BLOCK_3_PLACE"], vacuum_expected=False, marks_done_component="D1"),

        Step("BLOCK_4_PICK", "4. BLOK PICK", GCODE["BLOCK_4_PICK"], vacuum_expected=True),
        Step("BLOCK_4_TEST", "4. BLOK TEST", GCODE["BLOCK_4_TEST"], vacuum_expected=True, trigger_measurement=True),
        Step("BLOCK_4_PLACE", "4. BLOK PLACE", GCODE["BLOCK_4_PLACE"], vacuum_expected=False, marks_done_component="D2"),

        Step("BLOCK_5_PICK", "5. BLOK PICK", GCODE["BLOCK_5_PICK"], vacuum_expected=True),
        Step("BLOCK_5_TEST", "5. BLOK TEST", GCODE["BLOCK_5_TEST"], vacuum_expected=True, trigger_measurement=True),
        Step("BLOCK_5_RETURN", "5. BLOK RETURN", GCODE["BLOCK_5_RETURN"], vacuum_expected=False),

        Step("BLOCK_6_PICK", "6. BLOK PICK", GCODE["BLOCK_6_PICK"], vacuum_expected=True),
        Step("BLOCK_6_TEST", "6. BLOK TEST", GCODE["BLOCK_6_TEST"], vacuum_expected=True, trigger_measurement=True),
        Step("BLOCK_6_RETURN", "6. BLOK RETURN", GCODE["BLOCK_6_RETURN"], vacuum_expected=False),

        Step("BLOCK_7_PICK", "7. KONUM PICK", GCODE["BLOCK_7_PICK"], vacuum_expected=True),
        Step("BLOCK_7_TEST", "7. KONUM TEST", GCODE["BLOCK_7_TEST"], vacuum_expected=True, trigger_measurement=True),
        Step("BLOCK_7_RETURN", "7. KONUM RETURN", GCODE["BLOCK_7_RETURN"], vacuum_expected=False),

        Step("BLOCK_8_PICK", "8. KONUM PICK", GCODE["BLOCK_8_PICK"], vacuum_expected=True),
        Step("BLOCK_8_TEST", "8. KONUM TEST", GCODE["BLOCK_8_TEST"], vacuum_expected=True, trigger_measurement=True),
        Step("BLOCK_8_RETURN", "8. KONUM RETURN", GCODE["BLOCK_8_RETURN"], vacuum_expected=False),
    ]

    for s in steps:
        s.gcode = _normalize_gcode(s.gcode) if s.gcode else []

    return steps
