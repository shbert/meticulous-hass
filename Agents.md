# Agents.md

## Purpose
This repository implements a Home Assistant custom integration for the Meticulous espresso machine using the Python library `pyMeticulous`.

The integration exposes machine telemetry, sensors, and controls to Home Assistant.

Codex acts as the primary development agent and must follow these guidelines.

---

# Development Principles

1. Follow Home Assistant Custom Integration standards.
2. Use async Python whenever possible.
3. Avoid blocking IO in Home Assistant event loop.
4. Prefer existing `pyMeticulous` API calls instead of reimplementing HTTP calls.
5. Keep the integration minimal and idiomatic.

---

# Architecture

Integration domain: `meticulous`

Expected folder structure:

custom_components/meticulous/
init.py
manifest.json
config_flow.py
const.py
coordinator.py
sensor.py
button.py
switch.py
services.yaml
strings.json
translations/
en.json

Optional platforms:

binary_sensor.py
number.py
select.py

---

# Git Workflow Rules

Codex must:

1. Make small logical commits.
2. Use descriptive commit messages.
3. Stage only modified files.

Commit message format:

feat: add coordinator for machine telemetry
fix: handle connection timeout
refactor: simplify sensor creation
docs: update README


Never commit generated files or secrets.

---

# Coding Rules

### Python
- Python >= 3.11
- Use type hints everywhere.
- Use `asyncio`.

### Home Assistant Requirements
- Use `DataUpdateCoordinator`
- Do not poll directly in sensors
- Respect HA logging

### Logging

_LOGGER = logging.getLogger(name)


---

# Data Model

Coordinator fetches:

- machine status
- temperature
- pressure
- flow rate
- shot state
- scale weight
- active profile

---

# Entities

Sensors:

| Sensor | Type |
|------|------|
machine_temperature | sensor
machine_pressure | sensor
flow_rate | sensor
scale_weight | sensor
active_profile | sensor
shot_state | binary_sensor

Buttons:

| Button | Action |
|------|------|
start_shot | start brew
abort_shot | stop brew
purge | purge water

Switches:

| Switch | Action |
|------|------|
auto_purge | enable auto purge

---

# Codex Tasks

Codex should implement tasks in this order:

1. Create manifest.json
2. Implement integration setup
3. Implement config_flow
4. Implement coordinator
5. Implement sensor entities
6. Implement buttons
7. Add services
8. Add diagnostics

---

# Testing

Before committing:

ruff
pytest
homeassistant --script check_config

---

# Out of Scope

Do NOT implement:

- espresso profile editing
- firmware updates
- machine calibration

These are future enhancements.

---

# Future Enhancements

- shot history
- brew automation
- profile management
- energy monitoring