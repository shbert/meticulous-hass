"""Coordinator for Meticulous machine telemetry."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from functools import partial
import importlib
import inspect
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
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


def _mapping_from_state(state: Any) -> dict[str, Any]:
    """Normalize upstream telemetry object into a dictionary."""
    if isinstance(state, Mapping):
        return dict(state)

    output: dict[str, Any] = {}
    for key in (
        ATTR_TEMPERATURE,
        ATTR_PRESSURE,
        ATTR_FLOW_RATE,
        ATTR_SCALE_WEIGHT,
        ATTR_MOTOR_LOAD,
        ATTR_BREW_STATE,
        ATTR_WATER_TEMP,
    ):
        if hasattr(state, key):
            output[key] = getattr(state, key)
    return output


def _call_with_supported_parameters(
    func: Callable[..., Any],
    *,
    host: str,
    port: int,
    token: str | None,
) -> Any:
    """Invoke a constructor with only supported kwargs."""
    kwargs: dict[str, Any] = {}
    signature = inspect.signature(func)

    if "host" in signature.parameters:
        kwargs["host"] = host
    if "port" in signature.parameters:
        kwargs["port"] = port
    if "token" in signature.parameters and token is not None:
        kwargs["token"] = token
    if "api_key" in signature.parameters and token is not None:
        kwargs["api_key"] = token
    if "base_url" in signature.parameters:
        kwargs["base_url"] = f"http://{host}:{port}"

    try:
        return func(**kwargs)
    except TypeError:
        # Fallback for less introspectable callables.
        for args in ((host, port, token), (host, port), (host,)):
            try:
                return func(*args)
            except TypeError:
                continue
        return func()


def _build_client(*, host: str, port: int, token: str | None) -> Any:
    """Create a pyMeticulous client from known import paths."""
    candidates: tuple[tuple[str, str], ...] = (
        ("meticulous.api", "Api"),
        ("meticulous", "Api"),
        ("pymeticulous.client", "MeticulousClient"),
        ("pymeticulous", "MeticulousClient"),
        ("pyMeticulous", "MeticulousClient"),
    )

    import_errors: list[str] = []

    for module_name, class_name in candidates:
        try:
            module = importlib.import_module(module_name)
            client_cls = getattr(module, class_name)
        except (ImportError, AttributeError) as err:
            import_errors.append(f"{module_name}.{class_name}: {err}")
            continue

        try:
            return _call_with_supported_parameters(
                client_cls,
                host=host,
                port=port,
                token=token,
            )
        except Exception as err:  # pragma: no cover - depends on external lib
            raise MeticulousSetupError(str(err)) from err

    raise MeticulousSetupError(
        "Unable to import pyMeticulous client. Tried: " + "; ".join(import_errors)
    )


async def async_validate_connection(
    hass: HomeAssistant,
    *,
    host: str,
    port: int,
    token: str | None,
) -> None:
    """Validate connectivity for config flow."""
    client = await hass.async_add_executor_job(
        partial(_build_client, host=host, port=port, token=token)
    )

    ping_methods = (
        "async_test_connection",
        "test_connection",
        "async_ping",
        "ping",
        "async_get_state",
        "get_state",
        "async_get_status",
        "get_status",
    )

    last_error: Exception | None = None
    for method_name in ping_methods:
        method = getattr(client, method_name, None)
        if method is None:
            continue

        try:
            if inspect.iscoroutinefunction(method):
                await method()
            else:
                await hass.async_add_executor_job(method)
            return
        except Exception as err:  # pragma: no cover - depends on external lib
            last_error = err
            break

    if last_error is not None:
        message = str(last_error).lower()
        if "auth" in message or "token" in message or "credential" in message:
            raise MeticulousAuthError(str(last_error)) from last_error
        raise MeticulousConnectionError(str(last_error)) from last_error


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
        self.client: Any | None = None

    async def _async_setup(self) -> None:
        """Set up coordinator resources."""
        self.client = await self.hass.async_add_executor_job(
            partial(
                _build_client,
                host=self._host,
                port=self._port,
                token=self._token,
            )
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Meticulous machine."""
        if self.client is None:
            await self._async_setup()

        assert self.client is not None

        async_methods = (
            "async_get_telemetry",
            "async_get_status",
            "async_get_state",
        )
        sync_methods = (
            "get_telemetry",
            "get_status",
            "get_state",
            "fetch_telemetry",
        )

        try:
            for method_name in async_methods:
                method = getattr(self.client, method_name, None)
                if method is not None and inspect.iscoroutinefunction(method):
                    return _mapping_from_state(await method())

            for method_name in sync_methods:
                method = getattr(self.client, method_name, None)
                if method is not None:
                    data = await self.hass.async_add_executor_job(method)
                    return _mapping_from_state(data)
        except Exception as err:  # pragma: no cover - depends on external lib
            raise UpdateFailed(f"Error communicating with Meticulous machine: {err}") from err

        raise UpdateFailed("pyMeticulous client does not provide a supported telemetry method")

    async def async_execute_action(self, action: str) -> None:
        """Execute an action on the machine."""
        if self.client is None:
            await self._async_setup()

        assert self.client is not None

        explicit_action_methods: dict[str, tuple[str, str]] = {
            "start_brew": ("async_start_brew", "start_brew"),
            "abort_brew": ("async_abort_brew", "abort_brew"),
            "purge": ("async_purge", "purge"),
        }

        methods = explicit_action_methods.get(action)
        if methods:
            async_name, sync_name = methods
            async_method = getattr(self.client, async_name, None)
            if async_method is not None and inspect.iscoroutinefunction(async_method):
                await async_method()
                return

            sync_method = getattr(self.client, sync_name, None)
            if sync_method is not None:
                await self.hass.async_add_executor_job(sync_method)
                return

        generic_methods = ("async_execute_action", "execute_action", "async_action", "action")
        for method_name in generic_methods:
            method = getattr(self.client, method_name, None)
            if method is None:
                continue

            if inspect.iscoroutinefunction(method):
                await method(action)
            else:
                await self.hass.async_add_executor_job(method, action)
            return

        raise MeticulousError(f"Unsupported Meticulous action: {action}")
