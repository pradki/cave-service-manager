# relay_client.py
"""Klient waveshare-mqtt-gateway dla pompy pieca (`co_pump_boiler`) - jedyny
aktuator, jakim dziś sterują zadania tej usługi (patrz tasks/). Ten sam
sprzętowy impuls (flash_on), odnawiany co CHECK_INTERVAL, co wszędzie indziej
w cave: usługa, która przestaje odnawiać impuls (bo żadne zadanie już go nie
chce, albo bo padła), zostawia pompę, która zgaśnie sama."""
import logging

LOG = logging.getLogger("relay")


class PumpRelay:
    def __init__(self, publish, topic_root, module, service, alias,
                 priority=10, flash_duration=180.0):
        self.publish = publish
        self.topic_root = topic_root
        self.module = module
        self.service = service
        self.alias = alias
        self.priority = priority
        self.flash_duration = flash_duration

    def _cmd_topic(self):
        return f"{self.topic_root}/{self.module}/{self.alias}/cmd/{self.service}"

    def ping(self):
        topic = self._cmd_topic()
        body = {"cmd": "flash_on", "duration": self.flash_duration, "priority": self.priority}
        info = self.publish(topic, body)
        rc = getattr(info, "rc", None)
        if rc not in (None, 0):
            LOG.warning("Komenda pompy pieca nieudana (rc=%s): %s %s", rc, topic, body)
        return info
