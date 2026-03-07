"""Sensor platform for Meticulous."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfMass, UnitOfPressure, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MeticulousConfigEntry
from .const import (
    ATTR_FLOW_RATE,
    ATTR_MOTOR_LOAD,
    ATTR_PRESSURE,
    ATTR_SCALE_WEIGHT,
    ATTR_TEMPERATURE,
    ATTR_WATER_TEMP,
    DOMAIN,
)
from .coordinator import MeticulousDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class MeticulousSensorEntityDescription(SensorEntityDescription):
    """Describes Meticulous sensor entity."""

    telemetry_key: str


SENSORS: Final[tuple[MeticulousSensorEntityDescription, ...]] = (
    MeticulousSensorEntityDescription(
        key="temperature",
        name="Machine Temperature",
        telemetry_key=ATTR_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    MeticulousSensorEntityDescription(
        key="pressure",
        name="Machine Pressure",
        telemetry_key=ATTR_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MeticulousSensorEntityDescription(
        key="flow_rate",
        name="Flow Rate",
        telemetry_key=ATTR_FLOW_RATE,
    ),
    MeticulousSensorEntityDescription(
        key="scale_weight",
        name="Scale Weight",
        telemetry_key=ATTR_SCALE_WEIGHT,
        native_unit_of_measurement=UnitOfMass.GRAMS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MeticulousSensorEntityDescription(
        key="motor_load",
        name="Motor Load",
        telemetry_key=ATTR_MOTOR_LOAD,
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MeticulousSensorEntityDescription(
        key="water_temp",
        name="Water Temperature",
        telemetry_key=ATTR_WATER_TEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Meticulous sensors from config entry."""
    config_entry = entry
    typed_entry: MeticulousConfigEntry = config_entry
    coordinator = typed_entry.runtime_data.coordinator

    async_add_entities(
        MeticulousSensor(coordinator, typed_entry, description) for description in SENSORS
    )


class MeticulousSensor(CoordinatorEntity[MeticulousDataUpdateCoordinator], SensorEntity):
    """Representation of a Meticulous sensor."""

    entity_description: MeticulousSensorEntityDescription

    def __init__(
        self,
        coordinator: MeticulousDataUpdateCoordinator,
        entry: MeticulousConfigEntry,
        description: MeticulousSensorEntityDescription,
    ) -> None:
        """Initialize sensor entity."""
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

    @property
    def native_value(self) -> str | int | float | None:
        """Return sensor value."""
        value = self.coordinator.data.get(self.entity_description.telemetry_key)
        if value is None:
            return None

        if isinstance(value, (int, float, str)):
            return value

        return str(value)
