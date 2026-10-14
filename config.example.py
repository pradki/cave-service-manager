# config.example.py - skopiuj do config.py i popraw adresy pod własną sieć.
import platform

# === MQTT ===
if platform.system() == "Linux":
    MQTT_BROKER_HOST = "localhost"
else:
    MQTT_BROKER_HOST = "192.168.1.10"

MQTT_BROKER_PORT = 1883
MQTT_CLIENT_ID = "cave-service-manager"

# === Wejścia: czujniki i nastawy innych usług (tylko odczyt) ===
SENSOR_TOPIC_ROOT = "cave/sensors/temperature"
FURNACE_TEMP_SETPOINT_TOPIC = "cave/heating/setpoints/furnace_temp"

# Czujniki republikują co kilkanaście sekund - zwykły, skończony TTL ma sens
# (martwy czujnik ma realnie "zgasnąć"). Nastawa (furnace_temp_setpoint) jest
# wpisywana raz i tak zostaje - nieskończone TTL, ten sam powód co w
# comfort-controller (patrz jego README "Setpoints" - realnie zaobserwowany
# bug, nie teoria: skończone TTL cichcem wraca do domyślnej z configu, mimo
# że nikt nic nie zmieniał).
SENSOR_TTL = 120.0
SETPOINT_TTL = float("inf")

# === Wyjście: status tej usługi i jej zadań ===
STATUS_TOPIC_ROOT = "cave/service-manager"

# === Wyjście: waveshare-mqtt-gateway ===
RELAY_TOPIC_ROOT = "cave/relay"
RELAY_MODULE = "relay_heating"
SERVICE_NAME = "cave-service-manager"
# Tyle samo, co heating-controller (zadania tutaj to właśnie to, co wcześniej
# siedziało w heating-controller/heating.py:pump_boiler_ctrl) - priorytet 10
# zostawia miejsce caveweb/furnace_boost.py (priorytet 20) na przejęcie
# pompy na czas "Wypalania", niezależnie od tego, co mówią zadania tutaj.
LEASE_PRIORITY = 10

PUMP_ALIAS = "co_pump_boiler"
PUMP_FLASH_DURATION = 180.0   # s - tyle samo, co PUMP_BOILER_FLASH_DURATION w heating-controller

# === Czasy ===
CHECK_INTERVAL = 10.0   # s - tyle samo, co PUMP_BOILER_CHECK_INTERVAL w heating-controller
