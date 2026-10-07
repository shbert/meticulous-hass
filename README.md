# Meticulous Home Assistant Integration

Custom integration for Home Assistant to connect to a Meticulous espresso machine using `pymeticulous`.

> [!NOTE]
> v0.2.0 is tested against a real machine (firmware 0.2.24) on Home Assistant 2026.9.
> It is still young; report issues on GitHub.

## Features

- Local API connection to a Meticulous machine (REST + socket.io push telemetry, auto-reconnect)
- Optional [MeticAI](https://github.com/hessius/MeticAI) bridge: last-shot sensors and an AI "Analyze Last Shot" button
- Config flow setup from Home Assistant UI
- Telemetry updates via `DataUpdateCoordinator` every 5 seconds
- Brew control buttons
- Brew state binary sensor
- Auto purge switch
- Safety guards for dangerous actions (`start brew`, `auto purge`, `profile selection`)

## Entities

### Sensors

- Machine State (`idle`, `preheating`, `brewing`, …)
- Active Profile (the profile loaded on the machine)
- Machine Temperature
- Machine Pressure
- Flow Rate
- Scale Weight
- Motor Load
- Total Saved Shots, Device Info (diagnostic)
- With MeticAI configured: Last Shot (timestamp), Last Shot Profile, Last Shot Weight,
  Last Shot Duration, Last Shot Analysis (summary in the state, full text in the
  `last_analysis` attribute), MeticAI Version (diagnostic)

### Binary Sensors

- Brew State

### Buttons

- Arm Dangerous Actions
- Start Brew (dangerous)
- Preheat (dangerous)
- Abort Brew
- Purge
- Tare Scale
- With MeticAI configured: Analyze Last Shot (runs in the background, 1–3 min; uses
  the LLM configured in MeticAI, so it costs tokens)

### Switches

- Auto Purge

### Selects

- Profile (list and load machine profiles)

## Requirements

- Home Assistant `2024.12+`
- Python `3.12+` (Home Assistant runtime)
- Network access from Home Assistant to the Meticulous machine

## Installation (HACS)

1. Ensure HACS is installed in Home Assistant.
2. In Home Assistant, open `HACS` -> `Integrations`.
3. Open the menu (top right) -> `Custom repositories`.
4. Add this repository URL and set category to `Integration`.
5. Search for `Meticulous` in HACS and install it.
6. Restart Home Assistant.
7. Go to `Settings` -> `Devices & Services` -> `Add Integration`.
8. Search for `Meticulous`.
9. Enter `host`, `port` (default `80`; older firmware used `8080`), and optional `token`.
10. Optional: in the integration options, set the MeticAI server URL.

## Configuration

The integration uses a UI config flow and supports reload from Home Assistant.

### Dangerous Actions Safety

- Dangerous actions are disabled by default in integration options.
- `Start Brew`, `Preheat`, `Auto Purge`, and profile selection are marked as config entities and disabled by default.
- To execute a dangerous action:
  1. Enable dangerous actions in integration options.
  2. Use `Arm Dangerous Actions`.
  3. Execute the dangerous action within 30 seconds.
- Profile creation and profile-save editing are not exposed in this integration.

## Notes

- Communication is local polling/socket-based through `pymeticulous`.
- Tokens are optional and are not logged by the integration.
- If your machine is unreachable, verify host/port and local network routing.
