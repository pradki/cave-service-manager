# tests/test_wiring.py - spięcie całej usługi na config.example.py, bez brokera.
# Testujemy szablon, a nie lokalny config.py (ten jest gitignorowany), więc brak
# nowego klucza w szablonie wychodzi tutaj, a nie na Pi po deployu.
import importlib.util
import sys
from pathlib import Path

from fakes import FakePublisher, check, done

ROOT = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location("config", ROOT / "config.example.py")
cfg = importlib.util.module_from_spec(spec)
sys.modules["config"] = cfg
spec.loader.exec_module(cfg)

import main  # noqa: E402  (dopiero po podstawieniu configu z szablonu)
import tasks  # noqa: E402

mqtt_client, sensors, task_runtimes, pump_relay = main.build_service(cfg)

check("jedno zadanie na moduł w tasks.TASKS", len(task_runtimes) == len(tasks.TASKS)
      and [rt.module for rt in task_runtimes] == tasks.TASKS)
check("nazwy zadań unikalne", len({rt.module.NAME for rt in task_runtimes}) == len(task_runtimes))

check("subskrybujemy trzy czujniki i nastawę pieca z heating-controller",
      set(mqtt_client.param_topics) >= {
          f"{cfg.SENSOR_TOPIC_ROOT}/buff_top_temp",
          f"{cfg.SENSOR_TOPIC_ROOT}/buff_upmid_temp",
          f"{cfg.SENSOR_TOPIC_ROOT}/furnace_temp",
          cfg.FURNACE_TEMP_SETPOINT_TOPIC,
      })

for rt in task_runtimes:
    enabled_topic = f"{cfg.STATUS_TOPIC_ROOT}/tasks/{rt.module.NAME}/setpoints/enabled"
    check(f"{rt.module.NAME}: subskrybujemy jego 'enabled'", enabled_topic in mqtt_client.param_topics)
    check(f"{rt.module.NAME}: enabled domyślnie włączone, dopóki broker nic nie powiedział",
          rt.enabled.value is True)
    for key, _label, _data_type, _min_v, _max_v, default, _unit, _step in rt.module.CONFIG:
        topic = f"{cfg.STATUS_TOPIC_ROOT}/tasks/{rt.module.NAME}/setpoints/{key}"
        check(f"{rt.module.NAME}.{key}: subskrybowana nastawa", topic in mqtt_client.param_topics)
        check(f"{rt.module.NAME}.{key}: domyślna z CONFIG, dopóki broker nic nie powiedział",
              rt.config_params[key].value == default)
    check(f"{rt.module.NAME}: nastawy mają nieskończone TTL (patrz test_params.py)",
          rt.enabled.ttl == float("inf")
          and all(p.ttl == float("inf") for p in rt.config_params.values()))

check("pompa adresuje alias i priorytet z configu",
      pump_relay.alias == cfg.PUMP_ALIAS and pump_relay.priority == cfg.LEASE_PRIORITY
      and pump_relay.flash_duration == cfg.PUMP_FLASH_DURATION)

check("czujniki mają skończone TTL (martwy czujnik ma realnie zgasnąć)",
      all(sensors[name].ttl == cfg.SENSOR_TTL for name in main.SENSOR_NAMES))
check("nastawa pieca (z innej usługi) ma nieskończone TTL",
      sensors["furnace_temp_setpoint"].ttl == float("inf"))

# Tick bez żadnych danych z czujników (nic jeszcze nie przyszło) musi się
# zachować bezpiecznie - żadne zadanie nie aktywne, pompa nie pingowana.
pub = FakePublisher()
driving = main.tick(sensors, task_runtimes, pump_relay, pub, cfg)
check("na starcie, bez danych z czujników -> żadne zadanie nie jeździ", driving == [])
check("pompa nie pingowana", pub.for_topic(pump_relay._cmd_topic()) == [])
check("status zbiorczy opublikowany mimo braku danych",
      pub.last(f"{cfg.STATUS_TOPIC_ROOT}/status")[1]["pump_on"] is False)

done()
