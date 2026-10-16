# tasks/__init__.py
"""Rejestr zadań - zbiorcze dane, które main.py (wiring) i caveweb (kopia
metadanych, patrz jego README) czytają zamiast odkrywać coś dynamicznie.
Nowe zadanie = nowy moduł tutaj (NAME/LABEL/DESC/CONFIG/check(), patrz
buffer_top_redistribute.py jako wzór) + jeden wpis w TASKS poniżej - nic
więcej nie trzeba zmieniać, żeby main.py zaczęło je odpytywać i publikować
jego status."""
from . import buffer_top_redistribute, cwu_reserve_protect, furnace_overheat_protect, pump_always_on

TASKS = [buffer_top_redistribute, furnace_overheat_protect, cwu_reserve_protect, pump_always_on]

# Każdy moduł w TASKS musi mieć te atrybuty - main.py i testy na to liczą.
REQUIRED_ATTRS = ("NAME", "LABEL", "DESC", "CONFIG", "check")
