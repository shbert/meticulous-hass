# ADR-0001: Use pymeticulous socket telemetry cached behind a DataUpdateCoordinator

- **Status:** Accepted
- **Date:** 2026-03-07
- **Deciders:** Robert

## Context

The integration needs live telemetry (temperature, pressure, flow rate, scale weight, motor
load, brew state) from a Meticulous espresso machine on the local network. The machine exposes a
local HTTP/socket API, and the Python package `pymeticulous` already wraps it, including a
socket.io event stream that pushes `status` and `sensors` events at high frequency. Home
Assistant expects entities to read from a shared, event-loop-safe data source rather than each
entity talking to the device.

## Decision

Build the integration on `pymeticulous` (pinned in `manifest.json` as `pymeticulous==0.3.1`)
rather than reimplementing HTTP calls. Telemetry arrives via the library's socket event
callbacks (`onStatus`, `onSensors`, with library-side throttling at 0.25s) into an in-memory
dict guarded by a `threading.Lock`. A `MeticulousDataUpdateCoordinator` snapshots that dict
every 5 seconds (`COORDINATOR_UPDATE_INTERVAL`) and is the single data source for all entity
platforms. If no socket event has arrived for more than 30 seconds, the coordinator raises
`UpdateFailed` so entities go unavailable instead of showing stale values. Blocking client
calls run via `hass.async_add_executor_job`; the integration is declared `iot_class:
local_polling`.

## Consequences

- Entities never touch the device directly; all platforms (sensor, binary_sensor, button,
  switch, select) share one coordinator, which is the idiomatic HA pattern.
- The 5-second coordinator tick decouples HA state updates from the raw event rate, so the
  socket stream cannot flood the HA event loop; the trade-off is up to ~5s of latency on
  displayed telemetry.
- The 30-second staleness watchdog converts a silently dead socket into visible entity
  unavailability.
- The lock-guarded dict bridges the library's threaded callbacks and HA's async world; the
  executor-job wrapping is boilerplate we accept because `pymeticulous` is synchronous.
- Pinning `pymeticulous==0.3.1` means library API changes require an explicit manifest bump
  (one alignment fix was already needed: "fix: align coordinator with pymeticulous api").

## Alternatives considered

- Direct HTTP polling of the machine's REST endpoints per entity: rejected; duplicates what
  `pymeticulous` provides and violates the repo's own principle to prefer existing library
  calls (Agents.md).
- Pure pull-based polling without the socket stream: would miss the high-frequency brew
  telemetry the machine pushes; the socket stream with throttling gives fresher data at
  bounded cost.
- Pushing every socket event straight into HA state: rejected; would generate excessive state
  writes during a brew.
