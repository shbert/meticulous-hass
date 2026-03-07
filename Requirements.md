# Requirements.md

## Overview

Build a Home Assistant custom integration that connects to a Meticulous espresso machine via the Python package `pyMeticulous`.

The integration must allow Home Assistant to monitor machine state and trigger brewing actions.

---

# Functional Requirements

## Connection

The integration must:

- connect to the machine via the local API
- authenticate if required
- support reconnect logic

Configuration options:

host
port
token (optional)

---

# Telemetry

Expose the following machine data:

| Attribute | Entity Type |
|-----------|-------------|
temperature | sensor
pressure | sensor
flow_rate | sensor
scale_weight | sensor
motor_load | sensor
brew_state | binary_sensor
water_temp | sensor

Update interval:

5 seconds

Using a DataUpdateCoordinator.

---

# Device Info and Stats

Expose machine metadata from `api.get_device_info()` in Home Assistant.

The integration must make all available device info fields visible in HA, including:

- name
- hostname
- serial
- batch_number
- build_date
- firmware
- software_version
- image_build_channel
- image_version
- mainVoltage
- manufacturing
- version_history
- repository_info

Expose shot statistics from `api.get_history_statistics()`:

- totalSavedShots
- byProfile breakdown (name, count, profileVersions)

Implementation expectations:

- Use coordinator-managed refresh (no direct polling in entities)
- Surface device information and statistics as diagnostic entities/attributes
- Keep backward-compatible telemetry entities unchanged

---

# Control

Expose controls:

| Action | Entity |
|------|------|
start brew | button
abort brew | button
purge | button

---

# Safety for Dangerous Actions

Treat `start brew`, `auto purge`, and `profile selection/load` as dangerous actions.

Safety requirements:

- Dangerous actions are opt-in via integration options and disabled by default
- Dangerous entities are non-primary (`EntityCategory.CONFIG`)
- Dangerous entities are disabled by default in the entity registry
- Execution requires backend arming/confirmation step with short timeout
- Rejected and accepted dangerous-action attempts are warning-logged
- Backend guard must apply to UI and service/automation invocations equally

---

# Optional Controls

| Feature | Entity |
|------|------|
select profile | select
target weight | number

---

# Profile Handling

Integration must support profile handling using `pyMeticulous` profile APIs:

- show available profiles
- show currently active profile
- load/select a profile from Home Assistant

Scope constraints:

- creating new profiles is out of scope
- saving profile edits is out of scope

Profile loading/selection must be guarded as dangerous until firmware behavior is verified.

---

# Home Assistant Integration

Integration must support:

- config flow
- device registry
- entity registry
- diagnostics
- reload support

---

# Error Handling

Integration must handle:

- machine offline
- API timeout
- invalid credentials

---

# Performance

Polling interval:

5s

Use async calls.

---

# Security

Never log:

- tokens
- passwords

---

# Compatibility

Minimum Home Assistant version:

2024.12

Python version:

>=3.12


---

# Deliverables

Codex should generate:

custom_components/meticulous/

with all required files for a working HA integration.

---

# Definition of Done

Integration appears in Home Assistant UI and provides:

- machine telemetry
- brew start button
- purge button
- sensors updating every 5 seconds
- proper updated Readme.md in HomeAssistant style with installation instructions and basic documentation of this integration
