# tests/test_main.py - tick(): spięcie zadań, publikacja statusu, ping pompy
#
#     python tests/test_main.py
import importlib.util
import sys
from pathlib import Path

from fakes import ConstParam, FakePublisher, check, done

# main.py samo robi `import config` - podstawiamy szablon (config.py jest
# gitignorowany, lokalny) tak samo jak test_wiring.py w cwu-controller.
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("config", ROOT / "config.example.py")
config = importlib.util.module_from_spec(spec)
sys.modules["config"] = config
spec.loader.exec_module(config)

from main import TaskRuntime, read_inputs, tick  # noqa: E402  (po podstawieniu configu)
from params import Param  # noqa: E402
from relay_client import PumpRelay  # noqa: E402
from tasks import buffer_top_redistribute, furnace_overheat_protect  # noqa: E402

SENSOR_NAMES = ("buff_top_temp", "buff_upmid_temp", "furnace_temp")


def build(buff_top=None, furnace=None, furnace_setpoint=None):
    sensors = {name: Param(name, ttl=120.0) for name in SENSOR_NAMES}
    sensors["furnace_temp_setpoint"] = Param("furnace_temp_setpoint", ttl=float("inf"))
    if buff_top is not None:
        sensors["buff_top_temp"].update(buff_top)
    if furnace is not None:
        sensors["furnace_temp"].update(furnace)
    if furnace_setpoint is not None:
        sensors["furnace_temp_setpoint"].update(furnace_setpoint)

    rt1 = TaskRuntime(buffer_top_redistribute, ConstParam(True),
                      {"threshold": ConstParam(65.0)})
    rt2 = TaskRuntime(furnace_overheat_protect, ConstParam(True),
                      {"margin": ConstParam(10.0)})
    task_runtimes = [rt1, rt2]

    pub = FakePublisher()
    pump = PumpRelay(publish=pub, topic_root=config.RELAY_TOPIC_ROOT, module=config.RELAY_MODULE,
                     service=config.SERVICE_NAME, alias=config.PUMP_ALIAS,
                     priority=config.LEASE_PRIORITY, flash_duration=config.PUMP_FLASH_DURATION)
    return sensors, task_runtimes, pump, pub


# --- read_inputs: czujniki None gdy nieważne, nastawa normalnie -------------

sensors, _, _, _ = build()
inputs = read_inputs(sensors)
check("świeże czujniki (nic nie przyszło) -> None, nie 0.0",
      all(inputs[name] is None for name in SENSOR_NAMES))
check("nastawa pieca -> jej default (0.0), to świadomy wybór, nie 'brak danych'",
      inputs["furnace_temp_setpoint"] == 0.0)

# --- tick: żadne zadanie nie aktywne -> pompa nie pingowana -----------------

sensors, task_runtimes, pump, pub = build(buff_top=40.0, furnace=50.0, furnace_setpoint=52.0)
driving = tick(sensors, task_runtimes, pump, pub, config)
check("nic nie aktywne -> brak jeżdżących zadań", driving == [])
check("pompa nie pingowana", pub.for_topic(pump._cmd_topic()) == [])
check("status każdego zadania opublikowany",
      len(pub.for_topic(f"{config.STATUS_TOPIC_ROOT}/tasks/buffer_top_redistribute/status")) == 1)
agg = pub.last(f"{config.STATUS_TOPIC_ROOT}/status")
check("status zbiorczy mówi, że pompa nie pracuje", agg[1]["pump_on"] is False)

# --- tick: jedno zadanie aktywne (bufor góra) -> pompa pingowana ------------

sensors, task_runtimes, pump, pub = build(buff_top=70.0, furnace=50.0, furnace_setpoint=52.0)
driving = tick(sensors, task_runtimes, pump, pub, config)
check("tylko bufor góra aktywny", driving == ["buffer_top_redistribute"])
check("pompa pingowana", len(pub.for_topic(pump._cmd_topic())) == 1)
status = pub.last(f"{config.STATUS_TOPIC_ROOT}/tasks/buffer_top_redistribute/status")
check("status zadania mówi triggered+driving", status[1]["triggered"] is True
      and status[1]["driving"] is True)
status2 = pub.last(f"{config.STATUS_TOPIC_ROOT}/tasks/furnace_overheat_protect/status")
check("drugie zadanie wciąż publikuje status, ale nieaktywne",
      status2[1]["triggered"] is False and status2[1]["driving"] is False)

# --- tick: zadanie aktywne, ale WYŁĄCZONE -> nie pinguje pompy --------------

sensors, task_runtimes, pump, pub = build(buff_top=70.0, furnace=50.0, furnace_setpoint=52.0)
task_runtimes[0].enabled.value = False
driving = tick(sensors, task_runtimes, pump, pub, config)
check("wyłączone zadanie nie liczy się do 'jeżdżących', mimo że triggered",
      driving == [] and task_runtimes[0].triggered is True)
check("pompa NIE pingowana - jedyne aktywne zadanie jest wyłączone",
      pub.for_topic(pump._cmd_topic()) == [])
status = pub.last(f"{config.STATUS_TOPIC_ROOT}/tasks/buffer_top_redistribute/status")
check("status i tak pokazuje triggered=True, enabled=False, driving=False",
      status[1]["triggered"] is True and status[1]["enabled"] is False
      and status[1]["driving"] is False)

# --- tick: dwa zadania aktywne naraz -> oba w driving_tasks -----------------

sensors, task_runtimes, pump, pub = build(buff_top=70.0, furnace=65.0, furnace_setpoint=52.0)
driving = tick(sensors, task_runtimes, pump, pub, config)
check("oba zadania aktywne naraz", set(driving) == {"buffer_top_redistribute", "furnace_overheat_protect"})
check("pompa pingowana tylko raz mimo dwóch powodów", len(pub.for_topic(pump._cmd_topic())) == 1)

done()
