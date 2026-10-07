"""Coordinator for Meticulous machine telemetry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import partial
import asyncio
import logging
from threading import Lock
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from meticulous import APIError, Api
from meticulous.api import ApiOptions
from meticulous.api_types import (
    ActionType,
    DeviceInfo,
    HistoryStats,
    PartialProfile,
    PartialSettings,
    SensorsEvent,
    Settings,
    StatusData,
)

from .const import (
    ATTR_ACTIVE_PROFILE,
    ATTR_AUTO_PURGE,
    ATTR_AVAILABLE_PROFILES,
    ATTR_BREW_STATE,
    ATTR_DANGEROUS_ARMED_REMAINING,
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
    ATTR_ANALYSIS_RUNNING,
    ATTR_LAST_ANALYSIS,
    ATTR_LAST_ANALYSIS_AT,
    ATTR_LAST_ANALYSIS_SHOT,
    ATTR_LAST_ANALYSIS_SUMMARY,
    ATTR_LAST_SHOT_DATE,
    ATTR_LAST_SHOT_DURATION,
    ATTR_LAST_SHOT_FILENAME,
    ATTR_LAST_SHOT_PROFILE,
    ATTR_LAST_SHOT_TIME,
    ATTR_LAST_SHOT_WEIGHT,
    ATTR_MACHINE_STATE,
    ATTR_METICAI_AVAILABLE,
    ATTR_METICAI_UPDATE_AVAILABLE,
    ATTR_METICAI_VERSION,
    COORDINATOR_UPDATE_INTERVAL,
    DANGEROUS_ACTION_ARM_TIMEOUT_SECONDS,
    DOMAIN,
    METICAI_ANALYSIS_TIMEOUT_SECONDS,
    METICAI_REFRESH_INTERVAL,
    TELEMETRY_STALE_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


# Actions that move water or heat the machine need the opt-in + arming gate (ADR-0003).
DANGEROUS_ACTIONS = frozenset({"start_brew", "preheat"})


def _summarize(text: str, limit: int = 250) -> str:
    """Return a short state-sized summary of a markdown analysis."""
    for line in text.splitlines():
        cleaned = line.strip().lstrip("#*->").strip().replace("**", "")
        if len(cleaned) > 20:
            return cleaned[: limit - 1] + "…" if len(cleaned) > limit else cleaned
    flat = " ".join(text.split())
    return flat[: limit - 1] + "…" if len(flat) > limit else flat


class MeticulousError(HomeAssistantError):
    """Base Meticulous integration error."""


class MeticulousSetupError(MeticulousError):
    """Raised when client setup fails."""


class MeticulousAuthError(MeticulousError):
    """Raised when authentication fails."""


class MeticulousConnectionError(MeticulousError):
    """Raised when connection fails."""


class MeticulousDangerousActionError(MeticulousError):
    """Raised when a dangerous action is blocked by safety guards."""


class MeticulousDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Meticulous data."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        host: str,
        port: int,
        token: str | None,
        allow_dangerous_actions: bool,
        meticai_url: str | None = None,
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
        self._allow_dangerous_actions = allow_dangerous_actions

        self.client: Api | None = None
        self._telemetry: dict[str, Any] = {}
        self._telemetry_lock = Lock()
        self._last_event_at: datetime | None = None
        self._last_settings_refresh_at: datetime | None = None
        self._last_device_info_refresh_at: datetime | None = None
        self._last_stats_refresh_at: datetime | None = None
        self._armed_until: datetime | None = None
        self._profiles_by_option: dict[str, str] = {}
        self._last_profile_refresh_at: datetime | None = None
        self._connected_at: datetime | None = None
        self._meticai_url = meticai_url.rstrip("/") if meticai_url else None
        self._last_meticai_refresh_at: datetime | None = None
        self._analysis_task: asyncio.Task | None = None

    @property
    def meticai_enabled(self) -> bool:
        """Return True when an optional MeticAI server is configured."""
        return self._meticai_url is not None

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
                    ATTR_BREW_STATE: status_event.extracting,
                    ATTR_MACHINE_STATE: status_event.state,
                    # `profile` is the running stage ("idle" when idle); the profile that
                    # is loaded on the machine is `loaded_profile`.
                    ATTR_ACTIVE_PROFILE: status_event.loaded_profile
                    or status_event.profile,
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
        self._connected_at = datetime.now(tz=UTC)

    def _sync_reconnect(self) -> None:
        """Drop and re-open the socket.io connection."""
        assert self.client is not None
        try:
            self.client.disconnect_socket()
        except Exception as err:  # pragma: no cover - depends on socket state
            _LOGGER.debug("Ignoring socket disconnect error: %s", err)
        self.client.connect_to_socket(retries=2)

    async def _async_ensure_fresh_telemetry(self, last_event_at: datetime | None) -> None:
        """Reconnect when the socket stream went quiet; raise UpdateFailed if that fails."""
        now = datetime.now(tz=UTC)
        reference = last_event_at or self._connected_at
        if reference is None or now - reference <= timedelta(seconds=TELEMETRY_STALE_SECONDS):
            return
        _LOGGER.info("Meticulous telemetry stale since %s, reconnecting socket", reference)
        try:
            await self.hass.async_add_executor_job(self._sync_reconnect)
        except Exception as err:  # pragma: no cover - external socket errors
            raise UpdateFailed(f"Meticulous socket reconnect failed: {err}") from err
        self._connected_at = datetime.now(tz=UTC)
        with self._telemetry_lock:
            self._last_event_at = None

    async def _async_update_data(self) -> dict[str, Any]:
        """Return latest telemetry from the socket stream."""
        if self.client is None:
            await self._async_setup()

        with self._telemetry_lock:
            telemetry = dict(self._telemetry)
            last_event_at = self._last_event_at

        await self._async_ensure_fresh_telemetry(last_event_at)

        now = datetime.now(tz=UTC)
        if self._armed_until is None:
            telemetry[ATTR_DANGEROUS_ARMED_REMAINING] = 0
        else:
            remaining = int((self._armed_until - now).total_seconds())
            if remaining <= 0:
                self._armed_until = None
                telemetry[ATTR_DANGEROUS_ARMED_REMAINING] = 0
            else:
                telemetry[ATTR_DANGEROUS_ARMED_REMAINING] = remaining

        if self._last_settings_refresh_at is None or (
            now - self._last_settings_refresh_at
        ) > timedelta(seconds=60):
            try:
                auto_purge = await self.hass.async_add_executor_job(
                    self._sync_get_auto_purge
                )
            except Exception as err:  # pragma: no cover - external api errors
                _LOGGER.debug("Unable to refresh auto purge setting: %s", err)
            else:
                telemetry[ATTR_AUTO_PURGE] = auto_purge
                self._last_settings_refresh_at = now
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

        if self._last_profile_refresh_at is None or (
            now - self._last_profile_refresh_at
        ) > timedelta(minutes=5):
            try:
                profiles_payload = await self.hass.async_add_executor_job(
                    self._sync_get_profiles_payload
                )
            except Exception as err:  # pragma: no cover - external api errors
                _LOGGER.debug("Unable to refresh profiles: %s", err)
            else:
                telemetry.update(profiles_payload)
                self._last_profile_refresh_at = now

        if self._meticai_url and (
            self._last_meticai_refresh_at is None
            or now - self._last_meticai_refresh_at > METICAI_REFRESH_INTERVAL
        ):
            telemetry.update(await self._async_fetch_meticai())
            self._last_meticai_refresh_at = now

        with self._telemetry_lock:
            self._telemetry.update(telemetry)

        return telemetry

    # ---------------------------------------------------------------- MeticAI
    async def _async_meticai_get(self, path: str) -> Any:
        """GET a JSON document from the optional MeticAI server."""
        session = async_get_clientsession(self.hass)
        async with session.get(
            f"{self._meticai_url}{path}", timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def _async_fetch_meticai(self) -> dict[str, Any]:
        """Fetch last-shot metadata and server status from MeticAI (read-only)."""
        payload: dict[str, Any] = {}
        try:
            status = await self._async_meticai_get("/api/status")
            last_shot = await self._async_meticai_get("/api/last-shot")
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.debug("MeticAI not reachable: %s", err)
            payload[ATTR_METICAI_AVAILABLE] = False
            return payload

        payload[ATTR_METICAI_AVAILABLE] = True
        payload[ATTR_METICAI_VERSION] = status.get("current_version")
        payload[ATTR_METICAI_UPDATE_AVAILABLE] = bool(status.get("update_available"))
        if isinstance(last_shot, dict) and last_shot.get("filename"):
            timestamp = last_shot.get("timestamp")
            payload.update(
                {
                    ATTR_LAST_SHOT_PROFILE: last_shot.get("profile_name"),
                    ATTR_LAST_SHOT_WEIGHT: last_shot.get("final_weight"),
                    ATTR_LAST_SHOT_DURATION: last_shot.get("total_time"),
                    ATTR_LAST_SHOT_DATE: last_shot.get("date"),
                    ATTR_LAST_SHOT_FILENAME: last_shot.get("filename"),
                    ATTR_LAST_SHOT_TIME: dt_util.utc_from_timestamp(float(timestamp))
                    if timestamp is not None
                    else None,
                }
            )
        return payload

    async def async_analyze_last_shot(self) -> None:
        """Ask MeticAI for an AI analysis of the last shot (costs LLM tokens).

        Runs in the background: MeticAI's reasoning models take 1-3 minutes.
        """
        if not self._meticai_url:
            raise MeticulousError("MeticAI is not configured for this machine")
        if self._analysis_task is not None and not self._analysis_task.done():
            raise MeticulousError("An analysis is already running")
        data = self.data or {}
        filename = data.get(ATTR_LAST_SHOT_FILENAME)
        if not filename:
            raise MeticulousError("MeticAI has no last shot to analyse")
        shot = {
            "profile_name": data.get(ATTR_LAST_SHOT_PROFILE) or "Unknown",
            "shot_date": data.get(ATTR_LAST_SHOT_DATE) or "",
            "shot_filename": filename,
        }
        self._set_telemetry({ATTR_ANALYSIS_RUNNING: True})
        self.async_update_listeners()
        self._analysis_task = self.hass.async_create_background_task(
            self._async_run_analysis(shot), f"{DOMAIN}_analyze_last_shot"
        )

    async def _async_run_analysis(self, shot: dict[str, str]) -> None:
        """Background part of async_analyze_last_shot."""
        session = async_get_clientsession(self.hass)
        form = aiohttp.FormData()
        for key, value in shot.items():
            form.add_field(key, value)
        update: dict[str, Any] = {ATTR_ANALYSIS_RUNNING: False}
        try:
            async with session.post(
                f"{self._meticai_url}/api/shots/analyze-llm",
                data=form,
                timeout=aiohttp.ClientTimeout(total=METICAI_ANALYSIS_TIMEOUT_SECONDS),
            ) as resp:
                resp.raise_for_status()
                result = await resp.json()
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.warning("MeticAI shot analysis failed: %s", err)
            update[ATTR_LAST_ANALYSIS_SUMMARY] = f"Fehler: {err}"[:250]
        else:
            if result.get("status") == "success" and result.get("llm_analysis"):
                text = str(result["llm_analysis"])
                update.update(
                    {
                        ATTR_LAST_ANALYSIS: text,
                        ATTR_LAST_ANALYSIS_SUMMARY: _summarize(text),
                        ATTR_LAST_ANALYSIS_SHOT: shot["shot_filename"],
                        ATTR_LAST_ANALYSIS_AT: dt_util.utcnow(),
                    }
                )
            else:
                message = result.get("message") or "unknown error"
                _LOGGER.warning("MeticAI shot analysis returned an error: %s", message)
                update[ATTR_LAST_ANALYSIS_SUMMARY] = f"Fehler: {message}"[:250]
        self._set_telemetry(update)
        self.async_set_updated_data({**(self.data or {}), **update})

    def _set_telemetry(self, values: dict[str, Any]) -> None:
        with self._telemetry_lock:
            self._telemetry.update(values)

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
    def _profile_option(profile: PartialProfile) -> str:
        """Build display option label for a profile."""
        if profile.id:
            return f"{profile.name} ({profile.id[:8]})"
        return profile.name

    def _sync_get_profiles_payload(self) -> dict[str, Any]:
        """Fetch available profiles from the machine."""
        assert self.client is not None
        profiles = self.client.list_profiles()
        if isinstance(profiles, APIError):
            raise MeticulousError(profiles.error or "Unable to fetch profiles")

        profile_map: dict[str, str] = {}
        for profile in profiles:
            if not profile.id or not profile.name:
                continue
            profile_map[self._profile_option(profile)] = profile.id

        self._profiles_by_option = profile_map
        return {ATTR_AVAILABLE_PROFILES: list(profile_map.keys())}

    def _sync_load_profile(self, profile_id: str) -> PartialProfile:
        """Load profile by ID on the machine."""
        assert self.client is not None
        loaded = self.client.load_profile_by_id(profile_id)
        if isinstance(loaded, APIError):
            raise MeticulousError(loaded.error or "Unable to load profile")
        return loaded

    async def async_load_profile_by_option(self, option: str) -> None:
        """Load profile selected in HA by display option."""
        self._ensure_dangerous_action_allowed("select_profile")
        profile_id = self._profiles_by_option.get(option)
        if profile_id is None:
            raise MeticulousError(f"Unknown profile option: {option}")

        loaded = await self.hass.async_add_executor_job(
            partial(self._sync_load_profile, profile_id)
        )

        with self._telemetry_lock:
            self._telemetry[ATTR_ACTIVE_PROFILE] = loaded.name

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

    def _log_dangerous_action_attempt(
        self,
        *,
        action: str,
        allowed: bool,
        reason: str,
    ) -> None:
        """Log dangerous action attempts in a visible way."""
        if allowed:
            _LOGGER.warning("Dangerous action allowed: %s (%s)", action, reason)
            return
        _LOGGER.warning("Dangerous action blocked: %s (%s)", action, reason)

    def _ensure_dangerous_action_allowed(self, action: str) -> None:
        """Guard dangerous actions with opt-in and arming checks."""
        now = datetime.now(tz=UTC)

        if not self._allow_dangerous_actions:
            self._log_dangerous_action_attempt(
                action=action,
                allowed=False,
                reason="dangerous actions are disabled in integration options",
            )
            raise MeticulousDangerousActionError(
                "Dangerous actions are disabled. Enable them in integration options."
            )

        if self._armed_until is None or now > self._armed_until:
            self._armed_until = None
            self._log_dangerous_action_attempt(
                action=action,
                allowed=False,
                reason="arming required before execution",
            )
            raise MeticulousDangerousActionError(
                "Action requires arming. Press 'Arm Dangerous Actions' and retry within 30s."
            )

        self._armed_until = None
        with self._telemetry_lock:
            self._telemetry[ATTR_DANGEROUS_ARMED_REMAINING] = 0
        self._log_dangerous_action_attempt(
            action=action,
            allowed=True,
            reason="arming token accepted",
        )

    async def async_arm_dangerous_actions(self) -> None:
        """Arm dangerous actions for a short time window."""
        self._armed_until = datetime.now(tz=UTC) + timedelta(
            seconds=DANGEROUS_ACTION_ARM_TIMEOUT_SECONDS
        )
        with self._telemetry_lock:
            self._telemetry[ATTR_DANGEROUS_ARMED_REMAINING] = (
                DANGEROUS_ACTION_ARM_TIMEOUT_SECONDS
            )
        _LOGGER.warning(
            "Dangerous actions armed for %s seconds",
            DANGEROUS_ACTION_ARM_TIMEOUT_SECONDS,
        )

    async def async_execute_action(self, action: str) -> None:
        """Execute an action on the machine."""
        if self.client is None:
            await self._async_setup()

        action_map: dict[str, ActionType] = {
            "start_brew": ActionType.START,
            "abort_brew": ActionType.ABORT,
            "purge": ActionType.PURGE,
            "preheat": ActionType.PREHEAT,
            "tare": ActionType.TARE,
        }

        action_type = action_map.get(action)
        if action_type is None:
            raise MeticulousError(f"Unsupported Meticulous action: {action}")

        if action in DANGEROUS_ACTIONS:
            self._ensure_dangerous_action_allowed(action)

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
        self._ensure_dangerous_action_allowed("auto_purge")
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
