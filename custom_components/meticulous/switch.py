"""Switch platform for Meticulous."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MeticulousConfigEntry
from .const import ATTR_AUTO_PURGE, DOMAIN
from .coordinator import MeticulousDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Meticulous switches from config entry."""
    typed_entry: MeticulousConfigEntry = entry
    async_add_entities(
        [MeticulousAutoPurgeSwitch(typed_entry.runtime_data.coordinator, typed_entry)]
    )


class MeticulousAutoPurgeSwitch(
    CoordinatorEntity[MeticulousDataUpdateCoordinator], SwitchEntity
):
    """Switch for automatic purge after shot."""

    _attr_has_entity_name = True
    _attr_name = "Auto Purge"

    def __init__(
        self,
        coordinator: MeticulousDataUpdateCoordinator,
        entry: MeticulousConfigEntry,
    ) -> None:
        """Initialize switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_auto_purge"

        host = entry.data["host"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Meticulous ({host})",
            manufacturer="Meticulous",
            model="Espresso Machine",
        )

    @property
    def is_on(self) -> bool | None:
        """Return current state of auto purge switch."""
        value = self.coordinator.data.get(ATTR_AUTO_PURGE)
        if value is None:
            return None
        return bool(value)

    async def async_turn_on(self, **kwargs: object) -> None:
        """Turn auto purge on."""
        await self.coordinator.async_set_auto_purge(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: object) -> None:
        """Turn auto purge off."""
        await self.coordinator.async_set_auto_purge(False)
        await self.coordinator.async_request_refresh()
