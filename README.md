# Meticulous Home Assistant Integration

Custom integration for Home Assistant to connect to a Meticulous espresso machine using `pymeticulous`.

## Features

- Local API connection to a Meticulous machine
- Config flow setup from Home Assistant UI
- Telemetry updates via `DataUpdateCoordinator` every 5 seconds
- Brew control buttons
- Brew state binary sensor
- Auto purge switch

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

## Requirements

- Home Assistant `2024.12+`
- Python `3.12+` (Home Assistant runtime)
- Network access from Home Assistant to the Meticulous machine

## Installation (Manual, Home Assistant Style)

1. Locate your Home Assistant config directory (the folder that contains `configuration.yaml`).
2. Create this path if it does not exist:
   - `custom_components/meticulous/`
3. Copy this repository's `custom_components/meticulous` folder into your Home Assistant config directory under `custom_components/`.
4. Restart Home Assistant.
5. Go to `Settings` -> `Devices & Services` -> `Add Integration`.
6. Search for `Meticulous`.
7. Enter:
   - `host`
   - `port` (default: `8080`)
   - `token` (optional)

## Configuration

The integration uses a UI config flow and supports reload from Home Assistant.

## Notes

- Communication is local polling/socket-based through `pymeticulous`.
- Tokens are optional and are not logged by the integration.
- If your machine is unreachable, verify host/port and local network routing.
