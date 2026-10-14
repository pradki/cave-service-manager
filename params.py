# params.py
"""Wartości z brokera, z TTL - kopia cwu-controller/comfort-controller/params.py
(integracja tylko przez MQTT, każda usługa cave jest osobnym repo).

Dwa różne TTL dla dwóch różnych rzeczy (patrz config.py SENSOR_TTL/SETPOINT_TTL):
- czujniki (buff_top_temp, furnace_temp...) republikują co kilkanaście sekund -
  skończone TTL ma tu sens, bo milczenie realnie znaczy "czujnik padł".
- nastawy (progi zadań, enabled, furnace_temp_setpoint z heating-controller)
  są wpisywane raz i tak zostają - potrzebują NIESKOŃCZONEGO TTL, inaczej
  cichcem wracają do domyślnej z configu, mimo że nikt nic nie zmienił
  (dokładnie ten bug złapany w comfort-controller, patrz jego README)."""
import time


class Param:
    """Jedna wartość z brokera. Po przekroczeniu TTL `valid` jest False, a
    `value` zwraca `default` - "brak danych" musi wyglądać inaczej niż
    "wartość 0"."""

    def __init__(self, name, ttl=120.0, default=0.0, clock=time.monotonic):
        self.name = name
        self.ttl = ttl
        self.default = default
        self._clock = clock
        self._value = default
        self._updated = None  # None = nigdy nic nie przyszło

    def update(self, value):
        self._value = value
        self._updated = self._clock()

    @property
    def valid(self):
        if self._updated is None:
            return False
        return (self._clock() - self._updated) <= self.ttl

    @property
    def value(self):
        return self._value if self.valid else self.default

    @property
    def age(self):
        if self._updated is None:
            return None
        return self._clock() - self._updated
