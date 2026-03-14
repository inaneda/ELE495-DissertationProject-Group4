from __future__ import annotations
import threading
import time
from datetime import datetime
from typing import Optional

from src.app.services.gcode_programs import GCODE, build_program, validate_required_gcodes


class GCodeRunner:
    def __init__(self):
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

        self._pause_event = threading.Event()
        self._stop_event = threading.Event()

        self.current_step_idx = 0
        self.vacuum_on: bool = False
        self.program = []

# ***
        self.last_measured_box: Optional[str] = None
        self.resolved_once: bool = False
# *** ^

        print("[GCODE_RUNNER] Initialized")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _log(self, msg: str) -> None:
        from src.app.routers.status import SYSTEM_STATE

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        SYSTEM_STATE["logs"].append(f"[{ts}] {msg}")

        if len(SYSTEM_STATE["logs"]) > 300:
            SYSTEM_STATE["logs"] = SYSTEM_STATE["logs"][-300:]

    def start(self) -> None:
        from src.app.routers.status import SYSTEM_STATE

        try:
            validate_required_gcodes()
        except Exception as e:
            self._log(f"GCodeRunner: START blocked - {e}")
            SYSTEM_STATE["robot"]["status"] = "error"
            SYSTEM_STATE["robot"]["current_task"] = "GCODE missing"
            SYSTEM_STATE["program"]["running"] = False
            SYSTEM_STATE["program"]["paused"] = False
            return

        with self._lock:
            self._pause_event.clear()
            self._stop_event.clear()

            if self.current_step_idx == 0 and not self.is_running():
                self.program = build_program()

                if not self.program:
                    self._log("Program build failed (empty)")
                    return

            if self.is_running():
                SYSTEM_STATE["program"]["paused"] = False
                SYSTEM_STATE["program"]["running"] = True
                SYSTEM_STATE["robot"]["status"] = "running"
                self._log("GCodeRunner: RESUME")
                return

            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

            SYSTEM_STATE["program"]["running"] = True
            SYSTEM_STATE["program"]["paused"] = False
            SYSTEM_STATE["robot"]["status"] = "running"

            self._log("GCodeRunner: START")

    def stop(self) -> None:
        self._pause_event.set()
        self._log("GCodeRunner: STOP (paused)")

        from src.app.routers.status import SYSTEM_STATE

        SYSTEM_STATE["robot"]["status"] = "stopped"
        SYSTEM_STATE["robot"]["current_task"] = "-"
        SYSTEM_STATE["program"]["paused"] = True
        SYSTEM_STATE["program"]["running"] = True

    def reset(self) -> None:
        with self._lock:
            self._pause_event.clear()
            self._stop_event.set()

        self._log("GCodeRunner: RESET requested")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

        self.current_step_idx = 0
        self.vacuum_on = False
        self.program = []

# ***
        self.last_measured_box = None
        self.resolved_once = False
# *** ^

        from src.app.routers.status import SYSTEM_STATE

        SYSTEM_STATE["robot"]["status"] = "idle"
        SYSTEM_STATE["robot"]["current_task"] = "-"

        SYSTEM_STATE["program"]["current_step"] = 0
        SYSTEM_STATE["program"]["total_steps"] = 0
        SYSTEM_STATE["program"]["current_label"] = "-"
        SYSTEM_STATE["program"]["vacuum_on"] = False

        SYSTEM_STATE["program"]["running"] = False
        SYSTEM_STATE["program"]["paused"] = False

        for k in SYSTEM_STATE["program"]["pcb_done"].keys():
            SYSTEM_STATE["program"]["pcb_done"][k] = False

        # !!! measurements
        for k in SYSTEM_STATE["measurements"].keys():
            SYSTEM_STATE["measurements"][k] = "-"
        for k in SYSTEM_STATE["measurement_ohm"].keys():
            SYSTEM_STATE["measurement_ohm"][k] = None

        SYSTEM_STATE["teststation"]["last_result"] = None
        SYSTEM_STATE["teststation"]["last_voltage_v"] = None
        SYSTEM_STATE["teststation"]["last_resistance_ohm"] = None
        SYSTEM_STATE["teststation"]["last_updated"] = None
        SYSTEM_STATE["teststation"]["mode"] = None
        SYSTEM_STATE["teststation"]["value_text"] = None
        SYSTEM_STATE["teststation"]["raw_text"] = None

        self._thread = None

        self._log("GCodeRunner: RESET done")

    def _wait_if_paused(self) -> bool:
        while self._pause_event.is_set():
            if self._stop_event.is_set():
                return False
            time.sleep(0.05)

        return not self._stop_event.is_set()

    def _send_many(self, robot, lines: list[str]) -> bool:
        from src.app.routers.status import SYSTEM_STATE

        if not lines:
            return True

        for line in lines:
            if not self._wait_if_paused():
                return False

            line = (line or "").strip()
            if not line:
                continue

            ok = robot.send_gcode(line)

            SYSTEM_STATE["grbl"]["last_line"] = line
            SYSTEM_STATE["grbl"]["last_ok"] = bool(ok)
            SYSTEM_STATE["grbl"]["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")

            if not ok:
                self._log(f"GCode error on: {line}")
                SYSTEM_STATE["robot"]["status"] = "error"
                SYSTEM_STATE["robot"]["current_task"] = "G-code error"
                SYSTEM_STATE["program"]["running"] = False
                SYSTEM_STATE["program"]["paused"] = False
                return False

        return True
    
# ***
    # gcode_programs ile uyumlu hale getirmek icin
    def _measurement_box_from_step_id(self, step_id: str) -> Optional[str]:
        """
        Map test step id to the physical box name shown in the UI.
        BLOCK_1..BLOCK_6 => physical resistor boxes R1..R6
        BLOCK_3 and BLOCK_4 are currently used for diodes in the proven sequence,
        but the UI still wants the physical display names D1/D2 for diode boxes.
        """
        if step_id.startswith("BLOCK_1_"):
            return "R1"
        if step_id.startswith("BLOCK_2_"):
            return "R2"
        if step_id.startswith("BLOCK_3_"):
            return "D1"
        if step_id.startswith("BLOCK_4_"):
            return "D2"
        if step_id.startswith("BLOCK_5_"):
            return "R3"
        if step_id.startswith("BLOCK_6_"):
            return "R4"
        if step_id.startswith("BLOCK_7_"):
            return "R5"
        if step_id.startswith("BLOCK_8_"):
            return "R6"
        return None

    # direnc kodunu gercek direnc degerine cevirme
    def _target_code_to_ohm(self, code: str) -> Optional[float]:
        mapping = {
            "102": 1000.0,
            "472": 4700.0,
            "103": 10000.0,
            "333": 33000.0,
            "104": 100000.0,
        }
        return mapping.get(code)

    def _format_resistor_display(self, resistance_ohm: Optional[float]) -> str:
        if resistance_ohm is None:
            return "-"

        # arduino olcumune gore en yakin degeri bulabilmek icin
        code_map = {
            "102": 1000.0,
            "472": 4700.0,
            "103": 10000.0,
            "333": 33000.0,
            "104": 100000.0,
        }
        nearest_code = min(code_map.keys(), key=lambda c: abs(code_map[c] - resistance_ohm))
        if resistance_ohm >= 999: # kohm ohm ayrimi icin
            shown = f"{resistance_ohm / 1000.0:.2f} kΩ"
        else:
            shown = f"{resistance_ohm:.0f} Ω"
        return f"{nearest_code} ({shown})"

    def _format_diode_display(self, result: str) -> str:
        if result == "DIODE_FORWARD":
            return "NOT_OPEN"
        if result == "DIODE_REVERSED":
            return "OPEN"
        if result in ("INVALID", "TIMEOUT", "ERROR", "NO_CONNECTION", "NO_SERVICE"):
            return "OPEN"
        return "-"

    # olcum sonucunu MEASUREMENTS paneline yazar
    def _store_measurement_for_box(self, box_name: Optional[str], measurement: dict) -> None:
        from src.app.routers.status import SYSTEM_STATE

        if not box_name:
            return

        result = measurement.get("result")
        resistance_ohm = measurement.get("resistance_ohm")

        # resistor
        if box_name.startswith("R"):
            display = self._format_resistor_display(resistance_ohm)
            SYSTEM_STATE["measurements"][box_name] = self._format_resistor_display(resistance_ohm)
            SYSTEM_STATE["measurement_ohm"][box_name] = resistance_ohm       
            self._log(f"Measured {box_name} = {display}") # task history
        # diode
        elif box_name.startswith("D"):
            display = self._format_diode_display(str(result))
            SYSTEM_STATE["measurements"][box_name] = self._format_diode_display(str(result))
            self._log(f"Measured {box_name} = {display}") # task history

    # hangi fiziksel kutudaki direncin PCB'deki R1 ve R2 olmasi 
    # gerektigini seciyor !!! 
    # kullanici secimi: R1 = 4.7k
    # hedef eger 4.7k R3'te ise "PCB R1 selected physical : R3" diye arayuzu dolduracak
    # bu fonksiyon tum komponenetler olculduktan sonra calisir
    def _resolve_resistor_assignments(self) -> None:
        """
        Pick the nearest measured physical resistor boxes for PCB R1 and PCB R2.
        Uses physical resistor boxes only: R1, R2, R3, R4, R5, R6.
        """
        from src.app.routers.status import SYSTEM_STATE

        physical_boxes = ["R1", "R2", "R3", "R4", "R5", "R6"]
        targets = SYSTEM_STATE.get("resistor_targets", {})
        measurement_ohm = SYSTEM_STATE.get("measurement_ohm", {})

        ohm_by_box: dict[str, float] = {}

        for box in physical_boxes:
            value = measurement_ohm.get(box)
            if value is None:
                continue
            ohm_by_box[box] = float(value)

        used: set[str] = set() # ayni direnc iki kere secilmesin
        resolved: dict[str, Optional[str]] = {"R1": None, "R2": None} # bu fonksiyonu degiskeni
        # ORN: resolved = {"R1": "R3","R2": "R5"}

        for pcb_name in ("R1", "R2"):
            target_code = targets.get(pcb_name)
            target_ohm = self._target_code_to_ohm(str(target_code)) if target_code else None
            if target_ohm is None:
                continue

            candidates = [(box, ohm) for box, ohm in ohm_by_box.items() if box not in used]
            if not candidates:
                continue

            best_box, _best_ohm = min(candidates, key=lambda item: abs(item[1] - target_ohm))
            resolved[pcb_name] = best_box
            used.add(best_box)

        # fonksiyon icinde hesaplanan sonucu system_state'ine yaz
        SYSTEM_STATE["resolved_assignments"]["R1"] = resolved["R1"]
        SYSTEM_STATE["resolved_assignments"]["R2"] = resolved["R2"]

        self._log(
            f"Resolved assignments: PCB R1 -> {resolved['R1']}, PCB R2 -> {resolved['R2']}"
        )

    # program akisinin son kismi yani R1 ve R2'yi yerlestirmek icin
    # once secilen degere uygun olan direncin konumuna gidip aliyor ve bunu grbl'e atıyor
    # sonra pcb'deki R1 R2 konumlarindan hangisi icin calistiysa onun place konumunu grbl'e atiyor.
    def _run_selected_resistor_place(self, pcb_name: str, robot) -> bool:
        from src.app.routers.status import SYSTEM_STATE

        # R1 icin (pcb_name) cagrildiyse resolved assignment'tan R1: R? alir.
        # R? bu kullanicin sectigi direnc degerinin bulundugu konum
        resolved = SYSTEM_STATE["resolved_assignments"].get(pcb_name)

        if not resolved:
            self._log(f"No resolved resistor for {pcb_name}")
            return False

        block_map = {
            "R1":"BLOCK_1_PICK",
            "R2":"BLOCK_2_PICK",
            "R3":"BLOCK_5_PICK",
            "R4":"BLOCK_6_PICK",
            "R5":"BLOCK_7_PICK",
            "R6":"BLOCK_8_PICK",
        }

        pick_key = block_map.get(resolved)

        if not pick_key:
            self._log(f"Invalid resolved box {resolved}")
            return False

        pick_gcode = GCODE[pick_key]

        place_key = "BLOCK_1_PLACE" if pcb_name=="R1" else "BLOCK_2_PLACE"
        place_gcode = GCODE[place_key]

        # burada grbl'e atiyor, robot_service uzerinden tum gcode'lar arduino'ya (grbl) gonderiliyor
        # robot_service.send_gcode(line) gercekten grbl'e gonderme isini yapiyor.
        if not self._send_many(robot,pick_gcode):
            return False

        if not self._send_many(robot,place_gcode):
            return False

        return True
# *** ^

# ***
    def _run_measurement(self, step_id: Optional[str] = None) -> None:
        from src.app.routers.status import SYSTEM_STATE
        from src.app.main import arduino_service
        # ***
        box_name = self._measurement_box_from_step_id(step_id or "") if step_id else None
        self.last_measured_box = box_name
        # *** ^
        if arduino_service is None:
            SYSTEM_STATE["teststation"]["last_result"] = "NO_SERVICE"
            SYSTEM_STATE["teststation"]["last_voltage_v"] = 0.0
            SYSTEM_STATE["teststation"]["last_resistance_ohm"] = None
            SYSTEM_STATE["teststation"]["mode"] = "none"
            SYSTEM_STATE["teststation"]["value_text"] = "-"
            SYSTEM_STATE["teststation"]["raw_text"] = ""
            SYSTEM_STATE["teststation"]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            # ***
            if box_name:
                SYSTEM_STATE["measurements"][box_name] = "-"
            return
            # *** ^
        try:
            measurement = arduino_service.measure()

            SYSTEM_STATE["teststation"]["last_result"] = measurement.get("result")
            SYSTEM_STATE["teststation"]["last_voltage_v"] = measurement.get("voltage", 0.0)
            SYSTEM_STATE["teststation"]["last_resistance_ohm"] = measurement.get("resistance_ohm")
            SYSTEM_STATE["teststation"]["mode"] = measurement.get("mode", "none")
            SYSTEM_STATE["teststation"]["value_text"] = measurement.get("value_text", "-")
            SYSTEM_STATE["teststation"]["raw_text"] = measurement.get("raw_text", "")
            SYSTEM_STATE["teststation"]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            # ***
            self._store_measurement_for_box(box_name, measurement)
            # *** ^
        except Exception as e:
            self._log(f"Measurement error: {e}")
            SYSTEM_STATE["teststation"]["last_result"] = "ERROR"
            SYSTEM_STATE["teststation"]["last_voltage_v"] = 0.0
            SYSTEM_STATE["teststation"]["last_resistance_ohm"] = None
            SYSTEM_STATE["teststation"]["mode"] = "none"
            SYSTEM_STATE["teststation"]["value_text"] = "-"
            SYSTEM_STATE["teststation"]["raw_text"] = ""
            SYSTEM_STATE["teststation"]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            # ***
            if box_name:
                SYSTEM_STATE["measurements"][box_name] = "-"
            return
            # *** ^
# *** ^
    def _loop(self) -> None:
        from src.app.routers.status import SYSTEM_STATE
        from src.app.main import robot_service

        try:
            if robot_service is None:
                self._log("Robot service not initialized")
                SYSTEM_STATE["robot"]["status"] = "error"
                SYSTEM_STATE["program"]["running"] = False
                return

            SYSTEM_STATE["robot"]["status"] = "running"
            SYSTEM_STATE["program"]["running"] = True
            SYSTEM_STATE["program"]["paused"] = False

            total = len(self.program)
            SYSTEM_STATE["program"]["total_steps"] = total

            if total == 0:
                self._log("Program empty")
                return

            while self.current_step_idx < total:
                if self._stop_event.is_set():
                    break

                step = self.program[self.current_step_idx]

                SYSTEM_STATE["program"]["current_step"] = self.current_step_idx + 1
                SYSTEM_STATE["program"]["current_label"] = step.label
                SYSTEM_STATE["program"]["vacuum_on"] = self.vacuum_on

                SYSTEM_STATE["robot"]["status"] = "running"
                SYSTEM_STATE["robot"]["current_task"] = step.label

                self._log(f"STEP {self.current_step_idx + 1}/{total}: {step.label}")

# ***
                if step.id == "PLACE_SELECTED_R1":
                    if not self._run_selected_resistor_place("R1",robot_service):
                        return
                    
                    if step.marks_done_component:
                        if step.marks_done_component in SYSTEM_STATE["program"]["pcb_done"]:
                            SYSTEM_STATE["program"]["pcb_done"][step.marks_done_component] = True

                    self.current_step_idx += 1
                    continue

                if step.id == "PLACE_SELECTED_R2":
                    if not self._run_selected_resistor_place("R2",robot_service):
                        return
                    
                    if step.marks_done_component:
                        if step.marks_done_component in SYSTEM_STATE["program"]["pcb_done"]:
                            SYSTEM_STATE["program"]["pcb_done"][step.marks_done_component] = True
                            
                    self.current_step_idx += 1
                    continue
# *** ^
#                 
                ok = self._send_many(robot_service, step.gcode)
                if not ok:
                    return

                if step.vacuum_expected is not None:
                    self.vacuum_on = bool(step.vacuum_expected)
                    SYSTEM_STATE["program"]["vacuum_on"] = self.vacuum_on

                # if step.trigger_measurement:
                #     self._run_measurement()
# ***
                if step.trigger_measurement:
                    self._run_measurement(step.id)

                    # tum fiziksel kutudaki komponentlerin olcumu BLOCK_8_TEST ile tamamlanmis oluyor
                    if step.id == "BLOCK_8_TEST" and not self.resolved_once:
                        self._resolve_resistor_assignments()
                        self.resolved_once = True
# *** ^

                if step.marks_done_component:
                    if step.marks_done_component in SYSTEM_STATE["program"]["pcb_done"]:
                        SYSTEM_STATE["program"]["pcb_done"][step.marks_done_component] = True

                self.current_step_idx += 1

            SYSTEM_STATE["robot"]["status"] = "idle"
            SYSTEM_STATE["robot"]["current_task"] = "done"
            SYSTEM_STATE["program"]["running"] = False
            SYSTEM_STATE["program"]["paused"] = False
            SYSTEM_STATE["program"]["current_label"] = "done"

            self._log("GCodeRunner: finished")

        except Exception as e:
            self._log(f"GCodeRunner crashed: {e}")
            SYSTEM_STATE["robot"]["status"] = "error"
            SYSTEM_STATE["program"]["running"] = False


gcode_runner = None


def init_gcode_runner():
    global gcode_runner
    gcode_runner = GCodeRunner()
    return gcode_runner
