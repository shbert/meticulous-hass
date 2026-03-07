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
    PartialSettings,
    SensorsEvent,
    Settings,
    StatusData,
)

from .const import (
    ATTR_AUTO_PURGE,
    ATTR_BREW_STATE,
    ATTR_FLOW_RATE,
    ATTR_MOTOR_LOAD,
    ATTR_PRESSURE,
    ATTR_SCALE_WEIGHT,
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

    def _build_client(self) -> Api:
        """Build the API client."""
        options = ApiOptions(
            onStatus=self._handle_status_event,
            onSensors=self._handle_sensors_event,
        )
        client = Api(base_url=f"http://{self._host}:{self._port}", options=options)

        if self._token:
            # Token support is optional in pyMeticulous; keep it in request headers only.
            client.session.headers.update({"Authorization": f"Bearer {self._token}"})

        return client

    def _handle_status_event(self, status: StatusData) -> None:
        """Handle status event from socket stream."""
        with self._telemetry_lock:
            self._telemetry.update(
                {
                    ATTR_PRESSURE: status.sensors.p,
                    ATTR_FLOW_RATE: status.sensors.f,
                    ATTR_SCALE_WEIGHT: status.sensors.w,
                    ATTR_TEMPERATURE: status.sensors.t,
                    ATTR_WATER_TEMP: status.sensors.t,
                    ATTR_BREW_STATE: status.extracting,
                }
            )
            self._last_event_at = datetime.now(tz=UTC)

    def _handle_sensors_event(self, sensors: SensorsEvent) -> None:
        """Handle sensors event from socket stream."""
        with self._telemetry_lock:
            self._telemetry[ATTR_MOTOR_LOAD] = sensors.m_pwr
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

        return telemetry

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
