# tasks/cwu_reserve_protect.py
"""Nowe zadanie - górna część bufora (oba górne czujniki) to rezerwa, z
której m.in. grzeje się CWU. Jeśli ta rezerwa spadnie poniżej minimum, a piec
wciąż ma z czego dogrzać (nie jest zimny), włączamy pompę, żeby przenieść
ciepło z pieca do góry bufora - zanim rezerwa spadnie tak nisko, że CWU
zacznie na tym cierpieć. Gdy piec sam jest za zimny (poniżej `furnace_min`),
pompa nic by nie dała - przenosiłaby zimną wodę zamiast grzać, więc wtedy
task się nie włącza, niezależnie od stanu rezerwy."""
from __future__ import annotations

NAME = "cwu_reserve_protect"
LABEL = "Rezerwa CWU"
DESC = ("Gdy oba górne czujniki bufora spadną poniżej minimum, a piec ma jeszcze "
       "czym grzać, włącza pompę, żeby dogrzać górę bufora (rezerwę CWU).")

CONFIG = [
    ("furnace_min", "Piec min.", "float", 30.0, 80.0, 55.0, "°C", 1),
    ("reserve_min", "Rezerwa min.", "float", 30.0, 70.0, 45.0, "°C", 1),
]


def check(sensors: dict, config: dict) -> tuple[bool, str]:
    furnace = sensors.get("furnace_temp")
    top = sensors.get("buff_top_temp")
    upmid = sensors.get("buff_upmid_temp")
    furnace_min = config["furnace_min"]
    reserve_min = config["reserve_min"]

    if furnace is None or top is None or upmid is None:
        return False, "brak odczytu pieca albo bufora"

    if furnace < furnace_min:
        return False, f"piec {furnace:.1f}<{furnace_min:.1f}°C - za zimno, by przekazać ciepło"

    low = []
    if top < reserve_min:
        low.append(f"góra {top:.1f}")
    if upmid < reserve_min:
        low.append(f"śr.góra {upmid:.1f}")
    if low:
        return True, (f"piec {furnace:.1f}>={furnace_min:.1f}°C, rezerwa niska: "
                      f"{', '.join(low)}<{reserve_min:.1f}°C")
    return False, f"rezerwa OK (góra {top:.1f}, śr.góra {upmid:.1f}>={reserve_min:.1f}°C)"
