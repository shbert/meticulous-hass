# Meticulous Home Assistant Integration

Custom integration for Home Assistant to connect to a Meticulous espresso machine using `pymeticulous`.

> [!WARNING]
> This integration is currently **untested** and **not yet finished**. Use it as a work in progress.

## Features

- Local API connection to a Meticulous machine
- Config flow setup from Home Assistant UI
- Telemetry updates via `DataUpdateCoordinator` every 5 seconds
- Brew control buttons
- Brew state binary sensor
- Auto purge switch
- Safety guards for dangerous actions (`start brew`, `auto purge`)

## Entities

### Sensors

- Machine Temperature
- Machine Pressure
- Flow Rate
- Scale Weight
- Motor Load
- Water Temperature

### Binary Sensors

- Brew State

### Buttons

- Start Brew
- Abort Brew
- Purge

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
9. Enter `host`, `port` (default `8080`), and optional `token`.

## Configuration

The integration uses a UI config flow and supports reload from Home Assistant.

### Dangerous Actions Safety

- Dangerous actions are disabled by default in integration options.
- `Start Brew` and `Auto Purge` are marked as config entities and disabled by default.
- To execute a dangerous action:
  1. Enable dangerous actions in integration options.
  2. Use `Arm Dangerous Actions`.
  3. Execute the dangerous action within 30 seconds.
- Profile creation and profile-save editing are not exposed in this integration.

## Notes

- Communication is local polling/socket-based through `pymeticulous`.
- Tokens are optional and are not logged by the integration.
- If your machine is unreachable, verify host/port and local network routing.
