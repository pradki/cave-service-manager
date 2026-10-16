# cave-service-manager

A small, growing collection of independent automation tasks for the cave installation, each one
watching a couple of sensors/setpoints over MQTT and driving a relay when its own condition is
met - running as a standalone service on a Raspberry Pi, same MQTT-only shape as
[cwu-controller](https://github.com/pradki/cwu-controller),
[heating-controller](https://github.com/pradki/heating-controller) and
[comfort-controller](https://github.com/pradki/comfort-controller).

It exists because three small, unrelated-looking rules all turned out to want the same actuator
(the boiler's circulation pump, `co_pump_boiler`) for three independent reasons, and two of them
were buried inside `heating-controller` where "add a fourth reason later" would have meant
touching that service's main control loop every time. Here, a new reason is a new file.

```
┌──────────────────────┐  buff_top_temp / buff_upmid_temp / furnace_temp
│ sensor bridge         │ ─────────────────────────────────────────────┐
└──────────────────────┘                                                │
┌──────────────────────┐  furnace_temp_setpoint                        ▼
│ heating-controller   │ ─────────────────────────────▶┌───────────────────────┐
└──────────────────────┘                                │ cave-service-manager  │
┌──────────────────────┐  enabled / config per task     │      (this repo)      │
│ caveweb (/automations)│ ───────────────────────────▶  │                       │
└──────────────────────┘           MQTT broker          └───────────┬───────────┘
                                                                      │ flash_on, any task active
                                                                      ▼
                                                     ┌───────────────────────┐  Modbus
                                                     │ waveshare-mqtt-gateway│ ─────▶ co_pump_boiler
                                                     └───────────────────────┘
```

## Tasks (today)

| Task | Condition | Why |
|------|-----------|-----|
| `buffer_top_redistribute` | `buff_top_temp > threshold` (65°C) | Without the pump, the furnace's heat only ever reaches the top of the buffer tank - this spreads it to the lower layers instead of just overheating the top. |
| `furnace_overheat_protect` | `furnace_temp > furnace_temp_setpoint + margin` (10°C) | Typically right after adding wood; moves the excess into the buffer before the furnace's own independent hard safety limit (`MAX_FURNACE_TEMP` in `heating-controller`) would have to. |
| `cwu_reserve_protect` | `furnace_enable` (from `heating-controller`) **and** (`buff_top_temp < dhw_temp` **or** `buff_upmid_temp < dhw_temp`), `dhw_temp` also from `heating-controller` | The top of the buffer is the reserve DHW draws from; if either sensor drops below `heating-controller`'s own DHW setpoint, push heat up from the furnace before the reserve actually runs short. Gated on the furnace being *switched on*, not on its current temperature - a furnace that's lit but still warming up has every reason to help even before it individually clears some arbitrary minimum; one that's off has nothing to give regardless of what the buffer reads. No config of its own - both thresholds are `heating-controller`'s, not this service's to duplicate. |
| `pump_always_on` | always `True` | An experiment, not a real condition: keep the furnace pump running continuously (no sensor involved at all) to see whether a steadier furnace temperature - instead of the usual rest-then-overshoot cycle - lowers coal consumption. Starts **disabled** (see below) - a real condition task naturally does nothing until it occurs, but this one's "condition" is permanently true, so defaulting it on would have driven the pump non-stop from the moment this shipped. |

The first two used to live in `heating-controller/heating.py`'s `pump_boiler_ctrl()` - moved here
unchanged in behaviour (same thresholds, same defaults), just split into their own files and made
individually configurable. `heating-controller` no longer runs that task at all
(`PUMP_BOILER_CTRL_ENABLED = False` in its `config.py`) - running both would mean two services
independently deciding when to pulse the same relay, each unaware of the other.

`cwu_reserve_protect` started out with its own `furnace_min`/`reserve_min` config, gating on
`furnace_temp >= furnace_min` instead of `furnace_enable` - corrected after the buffer actually
sat cold (top 38°C, upper-mid 33°C) with the furnace lit but not yet past that threshold, and the
task declined to help. The furnace's *on/off* state, not its momentary temperature, is what
actually answers "is there something to transfer" - and `heating-controller` already publishes
exactly that, plus its own DHW minimum, so there was no reason for this task to keep a second,
separately-configured copy of either number.

Each task is a plain module under `tasks/` with four constants and one pure function - no
class, no base type to subclass:

```python
NAME = "buffer_top_redistribute"
LABEL = "Bufor góra"
DESC = "..."
CONFIG = [("threshold", "Próg", "float", 40.0, 90.0, 65.0, "°C", 1)]  # (key, label, type, min, max, default, unit, step)

def check(sensors: dict, config: dict) -> tuple[bool, str]:
    ...  # (triggered, human-readable reason) - pure, no I/O, trivially unit-tested
```

Adding a new task is: write that file, add the module to `TASKS` in `tasks/__init__.py`. The
main loop (`main.tick()`) picks it up automatically - new `enabled`/config setpoints, new status
topic, included in the "does anything want the pump" decision, nothing else to wire.

A task's `enabled` setpoint defaults to `True` (`main.py:build_service()`) - reasonable for every
task above, since each only ever does something once its real condition actually occurs. A module
can override this with a module-level `DEFAULT_ENABLED = False` (see `pump_always_on.py`) when its
condition is unconditional - deploying it pre-enabled would mean it starts acting the moment the
service (re)starts, before anyone decided to turn the experiment on.

## Topics

| Topic | Field(s) | Direction |
|-------|----------|-----------|
| `cave/sensors/temperature/{buff_top_temp,buff_upmid_temp,furnace_temp}` | `value` | in - read-only |
| `cave/heating/setpoints/furnace_temp` | `value` | in, read-only - `heating-controller`'s own furnace setpoint |
| `cave/heating/setpoints/furnace_enable` | `value` (bool) | in, read-only - is the furnace switched on at all |
| `cave/heating/setpoints/dhw_temp` | `value` | in, read-only - `heating-controller`'s own DHW (CWU) minimum |
| `cave/service-manager/tasks/<task>/setpoints/enabled` | `value` (bool) | in, retained - **published** by caveweb's `/automations` |
| `cave/service-manager/tasks/<task>/setpoints/<config key>` | `value` | in, retained - ditto, one topic per `CONFIG` entry |
| `cave/service-manager/tasks/<task>/status` | `enabled`, `triggered`, `driving`, `reason`, `config`, `updated_at` | **out**, retained - this task's current state |
| `cave/service-manager/status` | `pump_on`, `driving_tasks`, `updated_at` | **out**, retained - the one decision that actually matters: is the pump running, and because of what |
| `cave/relay/relay_heating/co_pump_boiler/cmd/cave-service-manager` | `{"cmd": "flash_on", ...}` | **out** - the pump, renewed every `CHECK_INTERVAL` while any enabled task is triggered |

`driving` in a task's own status is `enabled and triggered` - a task can be `triggered: true` while
disabled (so caveweb can still show "this would be active" without implying it's doing anything),
but only a `driving: true` task counts toward the shared pump decision.

### Setpoints don't expire

`enabled` and every `CONFIG` field, plus the externally-owned `furnace_temp_setpoint`, use
`SETPOINT_TTL = float("inf")` (`params.Param`), not the normal finite TTL the three sensors use.
Already learned the hard way once, in `comfort-controller`: a value published once (retained) and
then left alone is not the same as a sensor gone silent, and a finite TTL meant for the latter
quietly reverts the former back to its config default a couple of minutes later, with nobody
having touched it. See that repo's README for the full story; this one just starts from the
lesson instead of re-learning it.

## Why one shared pump decision, not three independent ones

All three tasks want the same relay. If each task pinged it independently, nothing about that
would be wrong by itself, but it's simpler and more honest to compute it once: `main.tick()` asks
every enabled task for `(triggered, reason)`, and pings the pump exactly once per check if *any*
of them came back triggered. A task that only ever wants to turn something on (never explicitly
off) fits the same hands-off, self-expiring `flash_on` pattern used everywhere else in cave: stop
pinging (because no task wants it anymore, or because the service itself died) and the relay lets
go on its own.

## Running

```bash
pip install -r requirements.txt
cp config.example.py config.py   # edit MQTT_BROKER_HOST for your network
python main.py
```

## Service

```bash
sudo cp cave-service-manager.service /etc/systemd/system/
sudo systemctl enable --now cave-service-manager
journalctl -u cave-service-manager -f
```

## Tests

No framework, no live data, no network - each file is a plain script that prints `OK`/`FAIL` and
exits non-zero on failure:

```bash
python tests/test_params.py
python tests/test_tasks.py
python tests/test_relay_client.py
python tests/test_main.py
python tests/test_wiring.py
```

`test_tasks.py` covers every task's `check()` directly - no broker, no asyncio, just dicts in and
`(bool, str)` out. `test_params.py` covers `Param`'s two TTL regimes. `test_relay_client.py`
covers the pump command shape. `test_main.py` covers `tick()`: status published for every task
regardless of outcome, the pump pinged only when an *enabled* task is triggered (a triggered-but-
disabled task must not drive it), and two simultaneously triggered tasks still only ping once.
`test_wiring.py` covers `build_service()` against `config.example.py` - every task's topics
actually subscribed, every setpoint's TTL actually infinite, a safe no-op tick with no sensor data
yet. `test_main.py` and `test_wiring.py` need `paho-mqtt` installed (they exercise the real MQTT
client class and the full `build_service()` wiring) - if your dev machine doesn't have it, the
Raspberry Pi's venv does.

## License

MIT
