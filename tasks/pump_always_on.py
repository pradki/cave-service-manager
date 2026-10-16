# tasks/pump_always_on.py
"""Eksperyment: trzymać pompę pieca włączoną bez przerwy, nie tylko gdy inne
zadania tego akurat chcą - żeby sprawdzić, czy stabilniejsza temperatura pieca
(bez cykli "piec stygnie 3-4h -> pompa rusza -> piec rozbujany, zanim się
wyciszy") obniża zużycie węgla. Zero sensorów, zero konfiguracji - samo
włączenie/wyłączenie tego zadania (`enabled`, wspólne dla każdego zadania w
tym serwisie) JEST przełącznikiem eksperymentu."""
from __future__ import annotations

NAME = "pump_always_on"
LABEL = "Pompa CO zawsze wł."
DESC = ("Eksperyment: trzyma pompę pieca włączoną bez przerwy, niezależnie od "
       "pozostałych zadań - sprawdzenie, czy stabilniejsza temperatura pieca "
       "(bez cykli odpoczynku i rozbujania) zmniejsza straty/zużycie węgla.")

CONFIG = []

# Każde inne zadanie w tym serwisie domyślnie startuje WŁĄCZONE (main.py:
# build_service() - "dopóki broker nic nie powiedział") - słusznie, bo każde
# z nich reaguje tylko na realny warunek (próg, alarm...), więc samo w sobie
# nic nie zmienia, dopóki ten warunek faktycznie nie wystąpi. To zadanie jest
# inne: jego "warunek" to zawsze `True` - gdyby wystartowało włączone,
# pompa ruszyłaby bez przerwy od razu po pierwszym deployu/restarcie usługi,
# zanim ktokolwiek świadomie zdecydował się na eksperyment. `False` tutaj,
# main.py czyta to przez `getattr(mod, "DEFAULT_ENABLED", True)` - zwykły
# task bez tego atrybutu dostaje normalne `True`.
DEFAULT_ENABLED = False


def check(sensors: dict, config: dict) -> tuple[bool, str]:
    """Zawsze aktywne, gdy samo zadanie jest włączone - nie patrzy na żaden
    czujnik. `sensors`/`config` przyjęte tylko dla jednolitej sygnatury z
    resztą zadań (main.py woła każde tak samo)."""
    return True, "zawsze włączona (eksperyment)"
