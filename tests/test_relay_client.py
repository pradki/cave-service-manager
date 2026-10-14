# tests/test_relay_client.py - kształt komendy do waveshare-mqtt-gateway
#
#     python tests/test_relay_client.py
from fakes import FakePublisher, check, done

from relay_client import PumpRelay

TOPIC_ROOT = "cave/relay"
MODULE = "relay_heating"
SERVICE = "cave-service-manager"

pub = FakePublisher()
pump = PumpRelay(publish=pub, topic_root=TOPIC_ROOT, module=MODULE, service=SERVICE,
                alias="co_pump_boiler", priority=10, flash_duration=180.0)
TOPIC = f"{TOPIC_ROOT}/{MODULE}/co_pump_boiler/cmd/{SERVICE}"

check("topic komendy w formacie gatewaya", pump._cmd_topic() == TOPIC)

pump.ping()
check("ping to flash_on z duration i priorytetem",
      pub.last(TOPIC) == (TOPIC, {"cmd": "flash_on", "duration": 180.0, "priority": 10}, False))

done()
