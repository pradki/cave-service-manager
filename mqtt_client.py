# mqtt_client.py
"""Cienki klient MQTT (wzorzec jak w cwu-controller/comfort-controller -
kopia, nie import - osobne repo, integracja tylko przez MQTT)."""
import json
import logging
import threading

import paho.mqtt.client as mqtt

LOG = logging.getLogger("mqtt")


def parse_value(payload):
    """Wyciąga pole "value" z ładunku `{"value": ...}` - goła liczba na
    topicu też przechodzi."""
    text = payload.decode("utf-8", errors="ignore").strip() if isinstance(payload, (bytes, bytearray)) else str(payload).strip()
    if not text:
        return None
    if text.startswith("{") or text.startswith("["):
        data = json.loads(text)
        if isinstance(data, dict):
            value = data.get("value")
            return None if value is None else value
        return None
    try:
        return float(text)
    except ValueError:
        return text


class MQTTClient:
    """Wątek paho. Wartości z brokera wędrują do Paramów przez
    `call_soon_threadsafe`, więc pętla sterowania nigdy nie czyta w połowie
    aktualizacji."""

    def __init__(self, host, port, client_id, param_topics=None):
        self.host = host
        self.port = port
        self.loop = None
        # topic -> Param (wartość z pola "value", liczba albo bool)
        self.param_topics = dict(param_topics or {})

        self.cnt_connects = 0
        self.cnt_disconnects = 0

        self.client = mqtt.Client(
            client_id=client_id,
            protocol=mqtt.MQTTv311,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)

    def bind_loop(self, loop):
        self.loop = loop

    def get_stats(self):
        return {
            "mqtt_connects": self.cnt_connects,
            "mqtt_disconnects": self.cnt_disconnects,
            "connected": self.client.is_connected(),
        }

    # ---------------- callbacks (wątek MQTT) ----------------
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.cnt_connects += 1
            for topic in self.param_topics:
                client.subscribe(topic)
            LOG.info("Connected (#%d), subscribed %d topics",
                     self.cnt_connects, len(self.param_topics))
        else:
            LOG.warning("Connect failed rc=%s", rc)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        self.cnt_disconnects += 1
        LOG.warning("Disconnected (#%d) rc=%s", self.cnt_disconnects, reason_code)

    def _on_message(self, client, userdata, message, properties=None):
        topic = message.topic
        param = self.param_topics.get(topic)
        if param is None:
            LOG.debug("Nieoczekiwany topic: %s", topic)
            return
        try:
            value = parse_value(message.payload)
        except Exception:
            LOG.warning("Nieparsowalny ładunek na %s: %r", topic, message.payload)
            return
        if value is None:
            return
        self._dispatch(param.update, value)

    def _dispatch(self, fn, arg):
        if self.loop is None:
            fn(arg)  # przed startem event loopa (albo w testach) - wprost
            return
        self.loop.call_soon_threadsafe(fn, arg)

    # ---------------- publikacja ----------------
    def publish(self, topic, payload, retain=False):
        try:
            self.client.publish(topic, json.dumps(payload), retain=retain)
        except Exception:
            LOG.exception("Publish error na %s", topic)

    # ---------------- lifecycle ----------------
    def start(self):
        if not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()
        try:
            self.client.disconnect()
            self.client.loop_stop()
        except Exception:
            pass

    def _run_loop(self):
        LOG.info("Connecting to MQTT %s:%s", self.host, self.port)
        try:
            # connect_async(), nie connect() - connect() próbuje się połączyć
            # OD RAZU i rzuca wyjątkiem, gdy broker jeszcze nie przyjmuje
            # połączeń (typowe zaraz po reboocie Pi, jeśli mosquitto wstaje
            # choć chwilę wolniej niż ta usługa) - wyjątek nieobsłużony w tym
            # wątku po cichu go zabija, bez żadnego śladu w systemd (proces
            # główny i tak żyje dalej). connect_async() odkłada pierwszą
            # próbę do loop_forever(), które z retry_first_connection=True
            # faktycznie ponawia - to właśnie ten retry miał obsłużyć ten
            # przypadek, ale nigdy nie dostawał szansy.
            self.client.connect_async(self.host, self.port, keepalive=30)
            self.client.loop_forever(retry_first_connection=True)
        except Exception:
            LOG.exception("MQTT loop error")
