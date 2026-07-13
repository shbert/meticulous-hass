# ADR-0003: Gate dangerous machine actions behind an opt-in plus arming window

- **Status:** Accepted
- **Date:** 2026-03-07
- **Deciders:** Robert

## Context

Some entities can make the physical machine do things with real-world consequences: start a
brew, run auto purge, or load a different brew profile (which changes machine behavior on the
next shot). In Home Assistant these are one-tap buttons/switches/selects that can also be fired
by automations, so an accidental trigger — a mis-tap on a dashboard or a buggy automation —
could run the espresso machine unattended. The integration is explicitly marked untested, which
raises the cost of an unintended action.

## Decision

Treat `start brew`, `auto purge`, and profile selection as "dangerous actions" behind a
two-layer guard:

1. A single integration option `allow_dangerous_actions` (default off) must be enabled.
2. Even when enabled, the user must first press an `Arm Dangerous Actions` control, which opens
   a 30-second window (`DANGEROUS_ACTION_ARM_TIMEOUT_SECONDS`); dangerous actions executed
   outside the window raise `MeticulousDangerousActionError` and are blocked.

The dangerous entities are registered as config entities and disabled by default, a countdown
sensor exposes the remaining armed seconds, and profile creation/editing is deliberately not
exposed at all.

## Consequences

- Accidental brews from dashboards or automations require three deliberate steps (enable
  option, arm, act within 30s), which is the point.
- Automations that legitimately want to start a brew must script the arm step first — a
  usability cost that is accepted deliberately.
- Every new actuating entity must be classified safe or dangerous; profile selection was
  reclassified as dangerous shortly after being added (`ceb3e79`, `f85d1b3`), showing the model
  is enforced as scope grows.
- The arming state lives in the coordinator (`_armed_until`), so a single arm covers all
  dangerous entities of the entry and expires uniformly.

## Alternatives considered

- No guard (plain buttons like most HA integrations): rejected; an untested integration driving
  a heat-and-pressure appliance warrants friction.
- Confirmation dialogs only: HA has no native server-side confirm step for button presses;
  client-side confirms do not protect against automations.
- Exposing profile create/save as well: explicitly rejected and documented as out of scope —
  the integration only lists and loads existing profiles.
