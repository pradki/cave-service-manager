# main.py
import asyncio
import logging
import signal
from datetime import datetime

import config
import tasks
from params import Param
from relay_client import PumpRelay
from mqtt_client import MQTTClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
LOG = logging.getLogger("main")

# Prawdziwe czujniki (TTL skończone - milczenie realnie znaczy "martwy
# czujnik", patrz params.py). furnace_temp_setpoint NIE jest tu - to nastawa
# z innej usługi (heating-controller), czytana tak samo jak nastawy zadań
# poniżej (nieskończone TTL).
SENSOR_NAMES = ("buff_top_temp", "buff_upmid_temp", "furnace_temp")


class TaskRuntime:
    """Stan jednego zadania między tickami - moduł (patrz tasks/) plus jego
    Paramy (enabled + każde pole z CONFIG) i ostatni wynik `check()`."""

    def __init__(self, module, enabled, config_params):
        self.module = module
        self.enabled = enabled
        self.config_params = config_params
        self.triggered = False
        self.reason = ""

    def config_values(self) -> dict:
        return {key: p.value for key, p in self.config_params.items()}

    def status_topic(self, status_topic_root: str) -> str:
        return f"{status_topic_root}/tasks/{self.module.NAME}/status"

    def status_payload(self, now: datetime) -> dict:
        enabled = bool(self.enabled.value)
        return {
            "enabled": enabled,
            "triggered": self.triggered,
            "driving": enabled and self.triggered,
            "reason": self.reason,
            "config": self.config_values(),
            "updated_at": now.isoformat(timespec="seconds"),
        }


def read_inputs(sensors: dict) -> dict:
    """Wartości do `check()` - czujniki jako None, gdy nieważne (nie jako
    domyślne 0.0, co wyglądałoby jak realny odczyt zera - patrz params.py),
    nastawa pieca normalnie (jej `default` to świadomy wybór, nie "brak
    danych")."""
    values = {name: (sensors[name].value if sensors[name].valid else None)
             for name in SENSOR_NAMES}
    values["furnace_temp_setpoint"] = sensors["furnace_temp_setpoint"].value
    return values


def build_service(cfg=config):
    """Składa usługę z konfiguracji, nie dotykając sieci - `main()` tylko
    startuje wątek MQTT i pętlę. Rozdzielone, żeby dało się sprawdzić samo
    spięcie (topici, zadania, kompletność configu) bez brokera."""
    sensors = {name: Param(name, ttl=cfg.SENSOR_TTL) for name in SENSOR_NAMES}
    sensors["furnace_temp_setpoint"] = Param("furnace_temp_setpoint", ttl=cfg.SETPOINT_TTL)

    param_topics = {f"{cfg.SENSOR_TOPIC_ROOT}/{name}": sensors[name] for name in SENSOR_NAMES}
    param_topics[cfg.FURNACE_TEMP_SETPOINT_TOPIC] = sensors["furnace_temp_setpoint"]

    task_runtimes = []
    for mod in tasks.TASKS:
        for attr in tasks.REQUIRED_ATTRS:
            assert hasattr(mod, attr), f"{mod.__name__} brakuje {attr}"

        enabled = Param(f"{mod.NAME}.enabled", ttl=cfg.SETPOINT_TTL, default=True)
        param_topics[f"{cfg.STATUS_TOPIC_ROOT}/tasks/{mod.NAME}/setpoints/enabled"] = enabled

        config_params = {}
        for key, _label, _data_type, _min_v, _max_v, default, _unit, _step in mod.CONFIG:
            param = Param(f"{mod.NAME}.{key}", ttl=cfg.SETPOINT_TTL, default=default)
            config_params[key] = param
            param_topics[f"{cfg.STATUS_TOPIC_ROOT}/tasks/{mod.NAME}/setpoints/{key}"] = param

        task_runtimes.append(TaskRuntime(mod, enabled, config_params))

    mqtt_client = MQTTClient(
        host=cfg.MQTT_BROKER_HOST, port=cfg.MQTT_BROKER_PORT,
        client_id=cfg.MQTT_CLIENT_ID, param_topics=param_topics,
    )

    pump_relay = PumpRelay(
        publish=mqtt_client.publish, topic_root=cfg.RELAY_TOPIC_ROOT,
        module=cfg.RELAY_MODULE, service=cfg.SERVICE_NAME, alias=cfg.PUMP_ALIAS,
        priority=cfg.LEASE_PRIORITY, flash_duration=cfg.PUMP_FLASH_DURATION,
    )

    return mqtt_client, sensors, task_runtimes, pump_relay


def tick(sensors, task_runtimes, pump_relay, publish, cfg, now=None):
    """Jeden przebieg: każde zadanie ocenia swój `check()`, publikuje swój
    status, a jeśli choć jedno WŁĄCZONE zadanie jest aktywne - odnawia impuls
    pompy. Czysta logika wywołania wydzielona z `control_loop()` (async),
    żeby dało się ją przetestować bez event loopa. `publish` to goła funkcja
    (topic, payload, retain) - jak wszędzie indziej w cave, nie cały klient."""
    now = now or datetime.now()
    inputs = read_inputs(sensors)

    driving_names = []
    for rt in task_runtimes:
        rt.triggered, rt.reason = rt.module.check(inputs, rt.config_values())
        if bool(rt.enabled.value) and rt.triggered:
            driving_names.append(rt.module.NAME)
        publish(rt.status_topic(cfg.STATUS_TOPIC_ROOT), rt.status_payload(now), retain=True)

    if driving_names:
        pump_relay.ping()

    publish(f"{cfg.STATUS_TOPIC_ROOT}/status", {
        "pump_on": bool(driving_names),
        "driving_tasks": driving_names,
        "updated_at": now.isoformat(timespec="seconds"),
    }, retain=True)
    return driving_names


async def control_loop(sensors, task_runtimes, pump_relay, publish, cfg, interval):
    while True:
        await asyncio.sleep(interval)
        try:
            tick(sensors, task_runtimes, pump_relay, publish, cfg)
        except Exception:
            LOG.exception("Błąd w ticku sterowania")


async def main():
    mqtt_client, sensors, task_runtimes, pump_relay = build_service()

    loop = asyncio.get_running_loop()
    mqtt_client.bind_loop(loop)
    mqtt_client.start()

    LOG.info("Start: %d zadań (%s), pompa '%s', moduł '%s'", len(task_runtimes),
             ", ".join(rt.module.NAME for rt in task_runtimes),
             config.PUMP_ALIAS, config.RELAY_MODULE)

    stop_event = asyncio.Event()

    def _handle_stop():
        LOG.info("Sygnał zatrzymania")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handle_stop)
        except (NotImplementedError, AttributeError):
            pass  # Windows (dev) nie wspiera add_signal_handler dla wszystkich sygnałów

    task = asyncio.create_task(control_loop(
        sensors, task_runtimes, pump_relay, mqtt_client.publish, config, config.CHECK_INTERVAL))

    try:
        await stop_event.wait()
    finally:
        task.cancel()
        mqtt_client.stop()


if __name__ == "__main__":
    asyncio.run(main())
