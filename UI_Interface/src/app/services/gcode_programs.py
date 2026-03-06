"""
File Name       : gcode_programs.py
Author          : Eda
Description:
Single fixed Pick&Place program definition.
G-codes will be filled later by the team.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, List

# komponent ve pad eslestirmesi
# rahatca degisiklik yapılabilsin diye
PAD_BY_COMPONENT: Dict[str, str] = {
    "R1": "A",
    "R2": "C",
    "D1": "B",
    "D2": "D",
}

# vision
TARGET_BOX_BY_PAD: Dict[str, list[int]] = {
    "A": [150, 150, 210, 180],
    "B": [250, 150, 310, 180],
    "C": [150, 250, 210, 280],
    "D": [250, 250, 310, 280],
}

GCODE: Dict[str, str | List[str]] = {
    # "G90;G0 X.. Y.." veya ["G90","G0 X.. Y.."]
    "HOME": "",
    "VAC_ON": "",
    "VAC_OFF": "",

    "MOVE_TEST": "",
    "TEST_PRESS_DWELL": "",

    "R1_FEEDER_MOVE": "",
    "R1_PICK_Z": "",
    "R2_FEEDER_MOVE": "",
    "R2_PICK_Z": "",
    "D1_FEEDER_MOVE": "",
    "D1_PICK_Z": "",
    "D2_FEEDER_MOVE": "",
    "D2_PICK_Z": "",

    "MOVE_PCB_A": "",
    "MOVE_PCB_B": "",
    "MOVE_PCB_C": "",
    "MOVE_PCB_D": "",

    "PLACE_Z": "",  # Z ekseni VAC_OFF'dan ayri oalcaksa
}


# programin adim aciklamalari
@dataclass
class Step:
    id: str
    label: str # UI logs/task
    gcode: str | List[str] # "G91;G0 X50;G90" veya ["G91", "G0 X50", "G90"]
    marks_done_component: Optional[str] = None # yerlestirme tamamlaninca set edilliyor
    vacuum_expected: Optional[bool] = None # durum takibi icin


def _normalize_gcode(x: str | List[str]) -> List[str]:
    if isinstance(x, list):
        return [s.strip() for s in x if s and s.strip()]
    # noktali virgul ile satir ayirma
    return [s.strip() for s in x.split(";") if s.strip()]


def validate_required_gcodes() -> None:
    """
    It is called when the Start button is pressed.
    It checks if the required keys are filled in the GCODE table.
    It throws a ValueError if there are any empty or missing keys.
    """
    required = [
        "HOME",
        "VAC_ON",
        "VAC_OFF",
        "MOVE_TEST",
        "TEST_PRESS_DWELL",
        "MOVE_PCB_A",
        "MOVE_PCB_B",
        "MOVE_PCB_C",
        "MOVE_PCB_D",
        "R1_FEEDER_MOVE", "R1_PICK_Z",
        "R2_FEEDER_MOVE", "R2_PICK_Z",
        "D1_FEEDER_MOVE", "D1_PICK_Z",
        "D2_FEEDER_MOVE", "D2_PICK_Z",
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
    """
    Fixed program:
      For each component:
        - go feeder
        - vacuum on
        - go test station (press + dwell)
        - go pcb pad
        - place + vacuum off
    G-codes are placeholders to be replaced.
    """
    steps: List[Step] = []

    # --- global start / home
    steps.append(
        Step(
            id="HOME",
            label="Go to HOME (startup position)",
            gcode=GCODE["HOME"],    # TODO: fill
            vacuum_expected=False,
        )
    )

    # siralama buradan degistirilebilir
    order = ["R1", "R2", "D1", "D2"]
    # comp ile sira tutuluyor, akis ayni oldugundan tekrar etmemek icin
    for comp in order:
        pad = PAD_BY_COMPONENT[comp]

        steps += [
            Step( # komponent almaya gitme
                id=f"{comp}_PICK_MOVE",
                label=f"{comp}: Move to feeder",
                gcode=GCODE[f"{comp}_FEEDER_MOVE"],  # TODO
                # ornek: gcode=["G90", "G0 X210 Y80"] veya
                #        gcode="G90;G0 X210 Y80",
            ),
            Step( # komponent almak icin vakum acma
                id=f"{comp}_VAC_ON",
                label=f"{comp}: Vacuum ON",
                gcode=GCODE["VAC_ON"],                 # TODO
                vacuum_expected=True,
            ),
            Step( # almak icin z ekseni hareketi
                id=f"{comp}_PICK_Z",
                label=f"{comp}: Pick Z down/up",
                gcode=GCODE[f"{comp}_PICK_Z"],        # TODO
                vacuum_expected=True,
            ),
            Step( # test istasyonuna gitme
                id=f"{comp}_TO_TEST",
                label=f"{comp}: Move to test station",
                gcode=GCODE["MOVE_TEST"],              # TODO
                vacuum_expected=True,
            ),
            Step( # test istasyonunda temazsizlik olmasin diye baski uygulama
                id=f"{comp}_TEST_PRESS",
                label=f"{comp}: Test press + dwell",
                gcode=GCODE["TEST_PRESS_DWELL"],        # TODO
                vacuum_expected=True,
            ),
            Step( # pcb'ye gitme
                id=f"{comp}_TO_PCB",
                label=f"{comp}: Move to PCB pad {pad}",
                gcode=GCODE[f"MOVE_PCB_{pad}"],       # TODO
                vacuum_expected=True,
            ),
            Step(
                id=f"{comp}_PLACE",
                label=f"{comp}: Place on pad {pad} (Vacuum OFF)",
                gcode=GCODE["VAC_OFF"],           # TODO
                marks_done_component=comp,
                vacuum_expected=False,
            ),
        ]

    steps.append(
        Step(
            id="DONE",
            label="Program finished",
            gcode="",
            vacuum_expected=False,
        )
    )

    # normalize gcode types
    for s in steps:
        s.gcode = _normalize_gcode(s.gcode) if s.gcode else []

    return steps