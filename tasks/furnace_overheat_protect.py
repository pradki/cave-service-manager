# tasks/furnace_overheat_protect.py
"""Wyciągnięte z heating-controller/heating.py:pump_boiler_ctrl() (powód #2) -
typowo zaraz po dorzuceniu drewna piec chwilowo przekracza zadaną. Pompa
odprowadza nadmiar do bufora, zanim zadziała twardy, niezależny limit
bezpieczeństwa (MAX_FURNACE_TEMP w heating-controller - ten task go nie
zastępuje, tylko reaguje wcześniej, łagodniej)."""
from __future__ import annotations

NAME = "furnace_overheat_protect"
LABEL = "Przegrzanie pieca"
DESC = ("Gdy piec przekroczy zadaną o margines (typowo zaraz po dorzuceniu drewna), "
       "włącza pompę, żeby odprowadzić nadmiar do bufora.")

CONFIG = [
    ("margin", "Margines", "float", 0.0, 30.0, 10.0, "°C", 1),
]


def check(sensors: dict, config: dict) -> tuple[bool, str]:
    furnace = sensors.get("furnace_temp")
    setpoint = sensors.get("furnace_temp_setpoint")
    margin = config["margin"]
    if furnace is None or setpoint is None:
        return False, "brak odczytu pieca albo jego zadanej"
    limit = setpoint + margin
    triggered = furnace > limit
    cmp = ">" if triggered else "<="
    return triggered, f"piec {furnace:.1f}{cmp}zadana+{margin:.1f}={limit:.1f}°C"
