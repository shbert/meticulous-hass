"""Select platform for Meticulous."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MeticulousConfigEntry
from .const import ATTR_ACTIVE_PROFILE, ATTR_AVAILABLE_PROFILES, DOMAIN
from .coordinator import MeticulousDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Meticulous selects from config entry."""
    typed_entry: MeticulousConfigEntry = entry
    async_add_entities(
        [MeticulousProfileSelect(typed_entry.runtime_data.coordinator, typed_entry)]
    )


class MeticulousProfileSelect(CoordinatorEntity[MeticulousDataUpdateCoordinator], SelectEntity):
    """Select entity to load machine profiles."""

    _attr_has_entity_name = True
    _attr_name = "Profile"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: MeticulousDataUpdateCoordinator,
        entry: MeticulousConfigEntry,
    ) -> None:
        """Initialize select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_profile"

        host = entry.data["host"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Meticulous ({host})",
            manufacturer="Meticulous",
            model="Espresso Machine",
        )

    @property
    def options(self) -> list[str]:
        """Return available options."""
        values = self.coordinator.data.get(ATTR_AVAILABLE_PROFILES)
        if isinstance(values, list):
            return [str(item) for item in values]
        return []

    @property
    def current_option(self) -> str | None:
        """Return current selected option."""
        active_profile = self.coordinator.data.get(ATTR_ACTIVE_PROFILE)
        if not isinstance(active_profile, str) or not active_profile:
            return None

        if active_profile in self.options:
            return active_profile

        # Status usually exposes profile name while options include an ID suffix.
        for option in self.options:
            if option.startswith(f"{active_profile} ("):
                return option

        return None

    async def async_select_option(self, option: str) -> None:
        """Load selected profile on the machine."""
        await self.coordinator.async_load_profile_by_option(option)
        await self.coordinator.async_request_refresh()
