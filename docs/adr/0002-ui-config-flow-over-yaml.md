# ADR-0002: Configure via UI config flow instead of YAML

- **Status:** Accepted
- **Date:** 2026-03-07
- **Deciders:** Robert

## Context

The integration needs connection settings (host, port, optional bearer token) and a runtime
policy toggle (allow dangerous actions). Home Assistant supports two configuration styles for
custom integrations: YAML in `configuration.yaml` or a UI config flow backed by config entries.
The integration is distributed through HACS as a custom repository, where config-entry-based
integrations are the norm and give users reload/options support without restarts.

## Decision

Use a UI config flow exclusively (`config_flow: true` in `manifest.json`). `MeticulousConfigFlow`
collects host, port (default 8080), and optional token, validates the connection live
(`async_validate_connection`) before creating the entry, and uses the host as the unique ID to
prevent duplicate entries. Mutable settings — currently the single `allow_dangerous_actions`
option — live in an `OptionsFlow`; option changes are applied by reloading the config entry
rather than by in-place mutation.

## Consequences

- Setup happens entirely in Settings -> Devices & Services; no `configuration.yaml` editing and
  no restart needed to add or reconfigure a machine.
- Live connection validation at setup surfaces auth failures (`invalid_auth`) and unreachable
  hosts (`cannot_connect`) before an entry is created.
- Unique-ID-by-host means one entry per machine; changing a machine's IP requires removing and
  re-adding the entry (no reconfigure-host step yet).
- Applying option changes via entry reload keeps the coordinator construction simple (options
  are read once at setup) at the cost of a brief entity flap on each options save; two fixes
  were needed to keep the options flow compatible with current HA (`ef1ec5a`, `3fc0bce`).

## Alternatives considered

- YAML configuration: rejected; HA has deprecated YAML for new device integrations, it cannot
  offer live validation, and it would not support the options-based dangerous-actions toggle.
- Zeroconf/DHCP discovery: not implemented; the machine's discoverability was not established,
  so manual host entry is the pragmatic MVP path.
