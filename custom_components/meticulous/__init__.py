"""The Meticulous integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TypeAlias

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_TOKEN, DOMAIN, PLATFORMS
from .coordinator import MeticulousDataUpdateCoordinator, MeticulousError

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class MeticulousRuntimeData:
    """Runtime data stored for each config entry."""

    coordinator: MeticulousDataUpdateCoordinator


MeticulousConfigEntry: TypeAlias = ConfigEntry[MeticulousRuntimeData]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Meticulous component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MeticulousConfigEntry) -> bool:
    """Set up Meticulous from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    token = entry.data.get(CONF_TOKEN)

    coordinator = MeticulousDataUpdateCoordinator(hass, host=host, port=port, token=token)

    try:
        await coordinator.async_config_entry_first_refresh()
    except MeticulousError as err:
        raise ConfigEntryNotReady(f"Failed to initialize Meticulous API: {err}") from err

    entry.runtime_data = MeticulousRuntimeData(coordinator=coordinator)
    hass.data[DOMAIN][entry.entry_id] = entry.runtime_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Meticulous config entry %s initialized", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MeticulousConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.coordinator.async_disconnect()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: MeticulousConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
