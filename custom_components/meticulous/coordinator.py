"""Coordinator for Meticulous machine telemetry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import partial
import logging
from threading import Lock
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from meticulous import APIError, Api
from meticulous.api import ApiOptions
from meticulous.api_types import (
    ActionType,
    DeviceInfo,
    HistoryStats,
    PartialSettings,
    SensorsEvent,
    Settings,
    StatusData,
)

from .const import (
    ATTR_AUTO_PURGE,
    ATTR_BREW_STATE,
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
    COORDINATOR_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class MeticulousError(HomeAssistantError):
    """Base Meticulous integration error."""


class MeticulousSetupError(MeticulousError):
    """Raised when client setup fails."""


class MeticulousAuthError(MeticulousError):
    """Raised when authentication fails."""


class MeticulousConnectionError(MeticulousError):
    """Raised when connection fails."""


class MeticulousDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Meticulous data."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        host: str,
        port: int,
        token: str | None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=COORDINATOR_UPDATE_INTERVAL,
        )
        self._host = host
        self._port = port
        self._token = token

        self.client: Api | None = None
        self._telemetry: dict[str, Any] = {}
        self._telemetry_lock = Lock()
        self._last_event_at: datetime | None = None
        self._last_settings_refresh_at: datetime | None = None
        self._last_device_info_refresh_at: datetime | None = None
        self._last_stats_refresh_at: datetime | None = None

    def _build_client(self) -> Api:
        """Build the API client."""
        options = ApiOptions(
            onStatus=self._handle_status_event,
            onSensors=self._handle_sensors_event,
            throttle={"status": 0.25, "sensors": 0.25},
        )
        client = Api(base_url=f"http://{self._host}:{self._port}", options=options)

        if self._token:
            # Token support is optional in pyMeticulous; keep it in request headers only.
            client.session.headers.update({"Authorization": f"Bearer {self._token}"})

        return client

    def _handle_status_event(self, status: StatusData | dict[str, Any]) -> None:
        """Handle status event from socket stream."""
        try:
            status_event = (
                status
                if isinstance(status, StatusData)
                else StatusData.model_validate(status)
            )
        except Exception as err:  # pragma: no cover - depends on upstream payloads
            _LOGGER.debug("Unable to parse status event payload: %s", err)
            return

        with self._telemetry_lock:
            self._telemetry.update(
                {
                    ATTR_PRESSURE: status_event.sensors.p,
                    ATTR_FLOW_RATE: status_event.sensors.f,
                    ATTR_SCALE_WEIGHT: status_event.sensors.w,
                    ATTR_TEMPERATURE: status_event.sensors.t,
                    ATTR_WATER_TEMP: status_event.sensors.t,
                    ATTR_BREW_STATE: status_event.extracting,
                }
            )
            self._last_event_at = datetime.now(tz=UTC)

    def _handle_sensors_event(self, sensors: SensorsEvent | dict[str, Any]) -> None:
        """Handle sensors event from socket stream."""
        try:
            sensor_event = (
                sensors
                if isinstance(sensors, SensorsEvent)
                else SensorsEvent.model_validate(sensors)
            )
        except Exception as err:  # pragma: no cover - depends on upstream payloads
            _LOGGER.debug("Unable to parse sensors event payload: %s", err)
            return

        with self._telemetry_lock:
            self._telemetry[ATTR_MOTOR_LOAD] = sensor_event.m_pwr
            self._last_event_at = datetime.now(tz=UTC)

    def _sync_connect_and_validate(self, client: Api) -> None:
        """Connect to socket and validate API reachability."""
        client.connect_to_socket(retries=2)

        device_info = client.get_device_info()
        if isinstance(device_info, APIError):
            if device_info.status in {"401", "403"}:
                raise MeticulousAuthError(device_info.error or "Authentication failed")
            raise MeticulousConnectionError(
                device_info.error or "Unable to reach machine"
            )

    async def _async_setup(self) -> None:
        """Set up coordinator resources."""
        self.client = await self.hass.async_add_executor_job(self._build_client)

        try:
            await self.hass.async_add_executor_job(
                partial(self._sync_connect_and_validate, self.client)
            )
        except MeticulousError:
            raise
        except Exception as err:  # pragma: no cover - external api errors
            raise MeticulousSetupError(str(err)) from err

    async def _async_update_data(self) -> dict[str, Any]:
        """Return latest telemetry from the socket stream."""
        if self.client is None:
            await self._async_setup()

        with self._telemetry_lock:
            telemetry = dict(self._telemetry)
            last_event_at = self._last_event_at

        if last_event_at is None:
            return telemetry

        age = datetime.now(tz=UTC) - last_event_at
        if age > timedelta(seconds=30):
            raise UpdateFailed("No telemetry received from Meticulous socket stream")

        if self._last_settings_refresh_at is None or (
            datetime.now(tz=UTC) - self._last_settings_refresh_at
        ) > timedelta(seconds=60):
            try:
                auto_purge = await self.hass.async_add_executor_job(
                    self._sync_get_auto_purge
                )
            except Exception as err:  # pragma: no cover - external api errors
                _LOGGER.debug("Unable to refresh auto purge setting: %s", err)
            else:
                telemetry[ATTR_AUTO_PURGE] = auto_purge
                self._last_settings_refresh_at = datetime.now(tz=UTC)

        now = datetime.now(tz=UTC)
        if self._last_device_info_refresh_at is None or (
            now - self._last_device_info_refresh_at
        ) > timedelta(minutes=15):
            try:
                device_info_payload = await self.hass.async_add_executor_job(
                    self._sync_get_device_info_payload
                )
            except Exception as err:  # pragma: no cover - external api errors
                _LOGGER.debug("Unable to refresh device info: %s", err)
            else:
                telemetry.update(device_info_payload)
                self._last_device_info_refresh_at = now

        if self._last_stats_refresh_at is None or (
            now - self._last_stats_refresh_at
        ) > timedelta(minutes=5):
            try:
                history_stats_payload = await self.hass.async_add_executor_job(
                    self._sync_get_history_stats_payload
                )
            except Exception as err:  # pragma: no cover - external api errors
                _LOGGER.debug("Unable to refresh history stats: %s", err)
            else:
                telemetry.update(history_stats_payload)
                self._last_stats_refresh_at = now

        with self._telemetry_lock:
            self._telemetry.update(telemetry)

        return telemetry

    def _sync_get_device_info_payload(self) -> dict[str, Any]:
        """Fetch and normalize device info."""
        assert self.client is not None
        device_info = self.client.get_device_info()
        if isinstance(device_info, APIError):
            raise MeticulousError(device_info.error or "Unable to fetch device info")

        return self._device_info_to_payload(device_info)

    @staticmethod
    def _device_info_to_payload(device_info: DeviceInfo) -> dict[str, Any]:
        """Convert device info model into coordinator payload keys."""
        return {
            ATTR_DEVICE_NAME: device_info.name,
            ATTR_DEVICE_HOSTNAME: device_info.hostname,
            ATTR_DEVICE_SERIAL: device_info.serial,
            ATTR_DEVICE_BATCH_NUMBER: device_info.batch_number,
            ATTR_DEVICE_BUILD_DATE: device_info.build_date,
            ATTR_DEVICE_FIRMWARE: device_info.firmware,
            ATTR_DEVICE_SOFTWARE_VERSION: device_info.software_version,
            ATTR_DEVICE_IMAGE_BUILD_CHANNEL: device_info.image_build_channel,
            ATTR_DEVICE_IMAGE_VERSION: device_info.image_version,
            ATTR_DEVICE_MAIN_VOLTAGE: device_info.mainVoltage,
            ATTR_DEVICE_MANUFACTURING: device_info.manufacturing,
            ATTR_DEVICE_VERSION_HISTORY: device_info.version_history,
            ATTR_DEVICE_REPOSITORY_INFO: device_info.repository_info,
        }

    def _sync_get_history_stats_payload(self) -> dict[str, Any]:
        """Fetch and normalize history statistics."""
        assert self.client is not None
        stats = self.client.get_history_statistics()
        if isinstance(stats, APIError):
            raise MeticulousError(stats.error or "Unable to fetch history statistics")

        return self._history_stats_to_payload(stats)

    @staticmethod
    def _history_stats_to_payload(stats: HistoryStats) -> dict[str, Any]:
        """Convert history statistics model into coordinator payload keys."""
        return {
            ATTR_STATS_TOTAL_SAVED_SHOTS: stats.totalSavedShots,
            ATTR_STATS_BY_PROFILE: [
                {
                    "name": item.name,
                    "count": item.count,
                    "profile_versions": item.profileVersions,
                }
                for item in stats.byProfile
            ],
        }

    def _sync_get_auto_purge(self) -> bool:
        """Fetch auto purge setting from machine settings."""
        assert self.client is not None
        settings = self.client.get_settings()
        if isinstance(settings, APIError):
            raise MeticulousError(settings.error or "Unable to fetch settings")
        return self._settings_auto_purge(settings)

    @staticmethod
    def _settings_auto_purge(settings: Settings) -> bool:
        """Extract auto purge from settings payload."""
        return bool(settings.auto_purge_after_shot)

    def _sync_execute_action(self, action: ActionType) -> None:
        """Execute an action through the HTTP API."""
        assert self.client is not None
        result = self.client.execute_action(action)
        if isinstance(result, APIError):
            raise MeticulousError(result.error or f"Action {action.value} failed")

    async def async_execute_action(self, action: str) -> None:
        """Execute an action on the machine."""
        if self.client is None:
            await self._async_setup()

        action_map: dict[str, ActionType] = {
            "start_brew": ActionType.START,
            "abort_brew": ActionType.ABORT,
            "purge": ActionType.PURGE,
        }

        action_type = action_map.get(action)
        if action_type is None:
            raise MeticulousError(f"Unsupported Meticulous action: {action}")

        await self.hass.async_add_executor_job(
            partial(self._sync_execute_action, action_type)
        )

    def _sync_set_auto_purge(self, enabled: bool) -> bool:
        """Set auto purge switch state."""
        assert self.client is not None
        payload = PartialSettings(auto_purge_after_shot=enabled)
        result = self.client.update_setting(payload)

        if isinstance(result, APIError):
            raise MeticulousError(result.error or "Failed updating auto purge setting")

        return self._settings_auto_purge(result)

    async def async_set_auto_purge(self, enabled: bool) -> None:
        """Set auto purge on the machine and update coordinator cache."""
        value = await self.hass.async_add_executor_job(
            partial(self._sync_set_auto_purge, enabled)
        )
        with self._telemetry_lock:
            self._telemetry[ATTR_AUTO_PURGE] = value
        self._last_settings_refresh_at = datetime.now(tz=UTC)

    async def async_disconnect(self) -> None:
        """Disconnect socket client."""
        if self.client is None:
            return
        await self.hass.async_add_executor_job(self.client.disconnect_socket)


async def async_validate_connection(
    hass: HomeAssistant,
    *,
    host: str,
    port: int,
    token: str | None,
) -> None:
    """Validate connectivity for config flow."""

    def _sync_validate() -> None:
        client = Api(base_url=f"http://{host}:{port}")
        if token:
            client.session.headers.update({"Authorization": f"Bearer {token}"})

        info = client.get_device_info()
        if isinstance(info, APIError):
            if info.status in {"401", "403"}:
                raise MeticulousAuthError(info.error or "Authentication failed")
            raise MeticulousConnectionError(info.error or "Unable to connect")

    try:
        await hass.async_add_executor_job(_sync_validate)
    except MeticulousError:
        raise
    except Exception as err:  # pragma: no cover - external api errors
        message = str(err).lower()
        if "401" in message or "403" in message or "auth" in message:
            raise MeticulousAuthError(str(err)) from err
        raise MeticulousConnectionError(str(err)) from err
