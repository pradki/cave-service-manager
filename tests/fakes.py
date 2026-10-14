# tests/fakes.py - wspólne atrapy dla testów (bez brokera i bez sprzętu)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_failures = []


def check(name, cond):
    print(("OK  " if cond else "FAIL"), name)
    if not cond:
        _failures.append(name)


def done():
    if _failures:
        print(f"done - {len(_failures)} FAILED: {', '.join(_failures)}")
        sys.exit(1)
    print("done")


class FakeClock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class FakePublisher:
    """Zbiera to, co poszłoby na brokera - podpisem zgodne z
    mqtt_client.MQTTClient.publish (topic, payload: dict, retain=False)."""

    def __init__(self):
        self.messages = []

    def __call__(self, topic, payload, retain=False):
        self.messages.append((topic, payload, retain))
        return self

    def clear(self):
        self.messages = []

    def topics(self):
        return [m[0] for m in self.messages]

    def for_topic(self, topic):
        return [m for m in self.messages if m[0] == topic]

    def last(self, topic=None):
        msgs = self.messages if topic is None else self.for_topic(topic)
        return msgs[-1] if msgs else None


class ConstParam:
    """`.value` stały - gdzie test chce podmieniać tylko wartość, bez TTL/
    staleness prawdziwego Param (to osobno pokryte w test_params.py)."""

    def __init__(self, value):
        self.value = value
