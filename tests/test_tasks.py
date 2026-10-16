# tests/test_tasks.py - check() każdego zadania: czysta logika, bez brokera
#
#     python tests/test_tasks.py
from fakes import check, done

from tasks import buffer_top_redistribute, cwu_reserve_protect, furnace_overheat_protect, pump_always_on

# --- buffer_top_redistribute --------------------------------------------------

CFG1 = {"threshold": 65.0}

triggered, reason = buffer_top_redistribute.check({"buff_top_temp": 68.2}, CFG1)
check("bufor góra powyżej progu -> aktywne", triggered is True)
check("powód wspomina obie wartości", "68.2" in reason and "65.0" in reason)

triggered, reason = buffer_top_redistribute.check({"buff_top_temp": 65.0}, CFG1)
check("dokładnie na progu -> NIE aktywne (ścisłe >)", triggered is False)

triggered, reason = buffer_top_redistribute.check({"buff_top_temp": 40.0}, CFG1)
check("poniżej progu -> nieaktywne", triggered is False)

triggered, reason = buffer_top_redistribute.check({"buff_top_temp": None}, CFG1)
check("brak odczytu -> nieaktywne, nie wyjątek", triggered is False)
check("powód mówi o braku odczytu", "brak odczytu" in reason)

triggered, _ = buffer_top_redistribute.check({}, CFG1)
check("brak klucza w ogóle -> tak samo nieaktywne", triggered is False)

# --- furnace_overheat_protect --------------------------------------------------

CFG2 = {"margin": 10.0}

triggered, reason = furnace_overheat_protect.check(
    {"furnace_temp": 65.0, "furnace_temp_setpoint": 52.0}, CFG2)
check("piec > zadana+margines -> aktywne", triggered is True)
check("powód liczy limit poprawnie (52+10=62)", "62.0" in reason)

triggered, reason = furnace_overheat_protect.check(
    {"furnace_temp": 60.0, "furnace_temp_setpoint": 52.0}, CFG2)
check("piec w granicach (60<=62) -> nieaktywne", triggered is False)

triggered, reason = furnace_overheat_protect.check(
    {"furnace_temp": None, "furnace_temp_setpoint": 52.0}, CFG2)
check("brak odczytu pieca -> nieaktywne", triggered is False)

triggered, reason = furnace_overheat_protect.check(
    {"furnace_temp": 65.0, "furnace_temp_setpoint": None}, CFG2)
check("brak zadanej -> też nieaktywne (nie zgadujemy)", triggered is False)

# --- cwu_reserve_protect: dhw_temp i furnace_enable z heating-controller,
# nie lokalna konfiguracja (CONFIG tego zadania jest puste) ------------------

CFG3 = {}

triggered, reason = cwu_reserve_protect.check(
    {"furnace_enable": True, "dhw_temp": 55.0, "buff_top_temp": 40.0, "buff_upmid_temp": 60.0}, CFG3)
check("piec włączony, góra bufora poniżej nastawy CWU -> aktywne", triggered is True)
check("powód wymienia tylko niski czujnik (góra), nie oba", "góra" in reason and "śr.góra" not in reason)

triggered, reason = cwu_reserve_protect.check(
    {"furnace_enable": True, "dhw_temp": 55.0, "buff_top_temp": 40.0, "buff_upmid_temp": 42.0}, CFG3)
check("oba górne czujniki poniżej nastawy -> aktywne, oba wymienione w powodzie",
      triggered is True and "góra" in reason and "śr.góra" in reason)

triggered, reason = cwu_reserve_protect.check(
    {"furnace_enable": True, "dhw_temp": 55.0, "buff_top_temp": 60.0, "buff_upmid_temp": 60.0}, CFG3)
check("rezerwa OK (oba >= nastawy CWU) -> nieaktywne", triggered is False)
check("powód mówi 'OK'", "OK" in reason)

triggered, reason = cwu_reserve_protect.check(
    {"furnace_enable": False, "dhw_temp": 55.0, "buff_top_temp": 30.0, "buff_upmid_temp": 30.0}, CFG3)
check("piec WYŁĄCZONY -> NIE aktywne mimo niskiej rezerwy (nie ma czym dogrzać)",
      triggered is False)
check("powód mówi, że piec wyłączony", "wyłączony" in reason)

triggered, reason = cwu_reserve_protect.check(
    {"furnace_enable": True, "dhw_temp": 55.0, "buff_top_temp": None, "buff_upmid_temp": 30.0}, CFG3)
check("brak odczytu bufora -> nieaktywne, nie wyjątek", triggered is False)

triggered, reason = cwu_reserve_protect.check(
    {"furnace_enable": True, "dhw_temp": None, "buff_top_temp": 30.0, "buff_upmid_temp": 30.0}, CFG3)
check("brak nastawy CWU (dhw_temp) -> nieaktywne, nie zgadujemy progu", triggered is False)

# --- pump_always_on: bezwarunkowo aktywne, zero konfiguracji/czujników -------

triggered, reason = pump_always_on.check({}, {})
check("zawsze aktywne, nawet bez żadnych czujników/configu", triggered is True)
check("powód mówi, że to eksperyment", "eksperyment" in reason)

triggered, reason = pump_always_on.check(
    {"buff_top_temp": None, "furnace_temp": None}, {})
check("nic nie zmienia się nawet z (pustymi) czujnikami w argumencie", triggered is True)

check("domyślnie WYŁĄCZONE (inaczej od reszty zadań) - inaczej pompa ruszyłaby "
      "bez przerwy od razu po deployu, zanim ktoś świadomie włączy eksperyment",
      pump_always_on.DEFAULT_ENABLED is False)
check("bez własnej konfiguracji", pump_always_on.CONFIG == [])

done()
