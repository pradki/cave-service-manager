# tasks/cwu_reserve_protect.py
"""Górna część bufora (oba górne czujniki) to rezerwa, z której grzeje się
CWU - jeśli którykolwiek z nich spadnie poniżej nastawy CWU samego
heating-controllera (`cave/heating/setpoints/dhw_temp` - "minimalna wartość
wody użytkowej", nie osobny lokalny próg), a piec jest WŁĄCZONY
(`cave/heating/setpoints/furnace_enable` - stan włącznika, nie sama
temperatura pieca: piec może być zapalony, ale jeszcze nie rozgrzany, i
nadal jest czym w końcu dogrzać), włączamy pompę, żeby przenieść ciepło z
pieca do góry bufora. Piec wyłączony = nie ma czym dogrzać, więc task się
nie włącza niezależnie od tego, jak nisko spadła rezerwa.

Brak własnej konfiguracji (CONFIG puste) - oba progi to cudze nastawy
(heating-controller), nie coś, co ta usługa miałaby same ustawiać."""
from __future__ import annotations

NAME = "cwu_reserve_protect"
LABEL = "Rezerwa CWU"
DESC = ("Gdy który bądź z górnych czujników bufora spadnie poniżej nastawy CWU "
       "(cave/heating/setpoints/dhw_temp), a piec jest włączony, włącza pompę, "
       "żeby dogrzać górę bufora (rezerwę CWU).")

CONFIG = []


def check(sensors: dict, config: dict) -> tuple[bool, str]:
    furnace_enabled = sensors.get("furnace_enable")
    dhw_temp = sensors.get("dhw_temp")
    top = sensors.get("buff_top_temp")
    upmid = sensors.get("buff_upmid_temp")

    if top is None or upmid is None or dhw_temp is None:
        return False, "brak odczytu bufora albo nastawy CWU (dhw_temp)"

    if not furnace_enabled:
        return False, "piec wyłączony - nie ma czym dogrzać"

    low = []
    if top < dhw_temp:
        low.append(f"góra {top:.1f}")
    if upmid < dhw_temp:
        low.append(f"śr.góra {upmid:.1f}")
    if low:
        return True, (f"piec włączony, rezerwa niska: {', '.join(low)}"
                      f"<{dhw_temp:.1f}°C (nastawa CWU)")
    return False, f"rezerwa OK (góra {top:.1f}, śr.góra {upmid:.1f}>={dhw_temp:.1f}°C)"
