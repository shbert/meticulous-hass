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
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MeticulousConfigEntry
from .const import (
    ATTR_DEVICE_BATCH_NUMBER,
    ATTR_DEVICE_BUILD_DATE,
    ATTR_DEVICE_FIRMWARE,
    ATTR_DEVICE_HOSTNAME,
    ATTR_DEVICE_IMAGE_BUILD_CHANNEL,
    ATTR_DEVICE_IMAGE_VERSION,
    ATTR_DEVICE_MAIN_VOLTAGE,
    ATTR_DEVICE_MANUFACTURING,
    ATTR_DEVICE_NAME,
    ATTR_DEVICE_REPOSITORY_INFO,
    ATTR_DEVICE_SERIAL,
    ATTR_DEVICE_SOFTWARE_VERSION,
    ATTR_DEVICE_VERSION_HISTORY,
    ATTR_FLOW_RATE,
    ATTR_MOTOR_LOAD,
    ATTR_PRESSURE,
    ATTR_SCALE_WEIGHT,
    ATTR_STATS_BY_PROFILE,
    ATTR_STATS_TOTAL_SAVED_SHOTS,
    ATTR_TEMPERATURE,
    ATTR_WATER_TEMP,
    DOMAIN,
)
from .coordinator import MeticulousDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class MeticulousSensorEntityDescription(SensorEntityDescription):
    """Describes Meticulous sensor entity."""

    telemetry_key: str


@dataclass(frozen=True, kw_only=True)
class MeticulousInfoSensorDescription(SensorEntityDescription):
    """Describes Meticulous info sensor entity."""

    telemetry_key: str
    extra_attribute_keys: tuple[str, ...] = ()


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

INFO_SENSORS: Final[tuple[MeticulousInfoSensorDescription, ...]] = (
    MeticulousInfoSensorDescription(
        key="total_saved_shots",
        name="Total Saved Shots",
        telemetry_key=ATTR_STATS_TOTAL_SAVED_SHOTS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MeticulousInfoSensorDescription(
        key="device_info",
        name="Device Info",
        telemetry_key=ATTR_DEVICE_SOFTWARE_VERSION,
        entity_category=EntityCategory.DIAGNOSTIC,
        extra_attribute_keys=(
            ATTR_DEVICE_NAME,
            ATTR_DEVICE_HOSTNAME,
            ATTR_DEVICE_SERIAL,
            ATTR_DEVICE_BATCH_NUMBER,
            ATTR_DEVICE_BUILD_DATE,
            ATTR_DEVICE_FIRMWARE,
            ATTR_DEVICE_SOFTWARE_VERSION,
            ATTR_DEVICE_IMAGE_BUILD_CHANNEL,
            ATTR_DEVICE_IMAGE_VERSION,
            ATTR_DEVICE_MAIN_VOLTAGE,
            ATTR_DEVICE_MANUFACTURING,
            ATTR_DEVICE_VERSION_HISTORY,
            ATTR_DEVICE_REPOSITORY_INFO,
            ATTR_STATS_BY_PROFILE,
        ),
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
    async_add_entities(
        MeticulousInfoSensor(coordinator, typed_entry, description)
        for description in INFO_SENSORS
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


class MeticulousInfoSensor(CoordinatorEntity[MeticulousDataUpdateCoordinator], SensorEntity):
    """Representation of a Meticulous diagnostic sensor."""

    entity_description: MeticulousInfoSensorDescription

    def __init__(
        self,
        coordinator: MeticulousDataUpdateCoordinator,
        entry: MeticulousConfigEntry,
        description: MeticulousInfoSensorDescription,
    ) -> None:
        """Initialize info sensor entity."""
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

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return extra attributes for diagnostic sensor."""
        attributes: dict[str, object] = {}
        for key in self.entity_description.extra_attribute_keys:
            value = self.coordinator.data.get(key)
            if value is not None:
                attributes[key] = value
        return attributes
