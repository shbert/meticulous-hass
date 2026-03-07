"""Binary sensor platform for Meticulous."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MeticulousConfigEntry
from .const import ATTR_BREW_STATE, DOMAIN
from .coordinator import MeticulousDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Meticulous binary sensors from config entry."""
    typed_entry: MeticulousConfigEntry = entry
    async_add_entities(
        [
            MeticulousBrewStateBinarySensor(
                typed_entry.runtime_data.coordinator,
                typed_entry,
            )
        ]
    )


class MeticulousBrewStateBinarySensor(
    CoordinatorEntity[MeticulousDataUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor for current brew activity."""

    _attr_has_entity_name = True
    _attr_name = "Brew State"

    def __init__(
        self,
        coordinator: MeticulousDataUpdateCoordinator,
        entry: MeticulousConfigEntry,
    ) -> None:
        """Initialize brew state binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_brew_state"

        host = entry.data["host"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Meticulous ({host})",
            manufacturer="Meticulous",
            model="Espresso Machine",
        )

    @property
    def is_on(self) -> bool:
        """Return true when machine is actively brewing."""
        return bool(self.coordinator.data.get(ATTR_BREW_STATE))
