# tests/test_params.py - Param: TTL skończone (czujniki) i nieskończone (nastawy)
#
#     python tests/test_params.py
from fakes import FakeClock, check, done

from params import Param

# --- TTL skończone - dla czujników, które milkną, gdy padają -----------------

clock = FakeClock()
p = Param("buff_top_temp", ttl=120.0, default=0.0, clock=clock)
check("nic nie przyszło -> niewalidowy", p.valid is False and p.value == 0.0)

p.update(68.2)
check("po update - walidowy, wartość aktualna", p.valid is True and p.value == 68.2)
clock.advance(120.1)
check("po TTL - z powrotem default (martwy czujnik, nie 'realne zero')",
      p.valid is False and p.value == 0.0)

# --- TTL nieskończone - dla nastaw wpisanych raz (progi zadań, enabled,
# furnace_temp_setpoint z heating-controller) --------------------------------
# Patrz comfort-controller/README "Setpoints" - realnie zaobserwowany bug:
# skończone TTL cichcem wraca do domyślnej z configu, mimo że nikt nic nie
# zmieniał.

clock = FakeClock()
p = Param("buffer_top_redistribute.threshold", ttl=float("inf"), default=65.0, clock=clock)
p.update(70.0)
clock.advance(1_000_000.0)
check("nieskończone TTL - nastawa trzyma się bez wygasania",
      p.valid is True and p.value == 70.0)

done()
