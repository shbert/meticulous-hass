"""Button platform for Meticulous."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MeticulousConfigEntry
from .const import DOMAIN
from .coordinator import MeticulousDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class MeticulousButtonEntityDescription(ButtonEntityDescription):
    """Describes Meticulous button entity."""

    action: str


BUTTONS: Final[tuple[MeticulousButtonEntityDescription, ...]] = (
    MeticulousButtonEntityDescription(
        key="start_brew",
        name="Start Brew",
        action="start_brew",
    ),
    MeticulousButtonEntityDescription(
        key="abort_brew",
        name="Abort Brew",
        action="abort_brew",
    ),
    MeticulousButtonEntityDescription(
        key="purge",
        name="Purge",
        action="purge",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Meticulous buttons from config entry."""
    config_entry = entry
    typed_entry: MeticulousConfigEntry = config_entry
    coordinator = typed_entry.runtime_data.coordinator

    async_add_entities(
        MeticulousButton(coordinator, typed_entry, description) for description in BUTTONS
    )


class MeticulousButton(CoordinatorEntity[MeticulousDataUpdateCoordinator], ButtonEntity):
    """Representation of a Meticulous action button."""

    entity_description: MeticulousButtonEntityDescription

    def __init__(
        self,
        coordinator: MeticulousDataUpdateCoordinator,
        entry: MeticulousConfigEntry,
        description: MeticulousButtonEntityDescription,
    ) -> None:
        """Initialize button entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_has_entity_name = True

        host = entry.data["host"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Meticulous ({host})",
            manufacturer="Meticulous",
            model="Espresso Machine",
        )

    async def async_press(self) -> None:
        """Press the button."""
        await self.coordinator.async_execute_action(self.entity_description.action)
        await self.coordinator.async_request_refresh()
