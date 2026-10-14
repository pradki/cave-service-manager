# tasks/buffer_top_redistribute.py
"""Wyciągnięte z heating-controller/heating.py:pump_boiler_ctrl() (powód #1) -
góra bufora grzeje się szybciej niż reszta, bo bez pompy to ona odbiera całe
ciepło z pieca jako pierwsza. Powyżej progu włączamy pompę, żeby rozprowadzić
ciepło na niższe warstwy zamiast przegrzewać tylko wierzch."""
from __future__ import annotations

NAME = "buffer_top_redistribute"
LABEL = "Bufor góra"
DESC = ("Gdy góra bufora przekroczy próg, włącza pompę pieca, żeby rozprowadzić "
       "ciepło na niższe warstwy zamiast grzać tylko górną partię.")

# (klucz, etykieta, typ, min, max, domyślna, jednostka, krok)
CONFIG = [
    ("threshold", "Próg", "float", 40.0, 90.0, 65.0, "°C", 1),
]


def check(sensors: dict, config: dict) -> tuple[bool, str]:
    """`sensors`: wartości z brokera (buff_top_temp...); `config`: aktualne
    wartości pól z CONFIG. Zwraca (czy_aktywne, powód) - czysta funkcja, bez
    I/O, żeby dało się przetestować bez brokera i bez asyncio."""
    buff_top = sensors.get("buff_top_temp")
    threshold = config["threshold"]
    if buff_top is None:
        return False, "brak odczytu bufora góra"
    triggered = buff_top > threshold
    cmp = ">" if triggered else "<="
    return triggered, f"bufor góra {buff_top:.1f}{cmp}{threshold:.1f}°C"
