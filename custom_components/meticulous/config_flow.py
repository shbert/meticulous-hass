"""Config flow for Meticulous integration."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ALLOW_DANGEROUS_ACTIONS,
    CONF_METICAI_URL,
    CONF_TOKEN,
    DEFAULT_PORT,
    DOMAIN,
)
from .coordinator import (
    MeticulousAuthError,
    MeticulousConnectionError,
    MeticulousError,
    async_validate_connection,
)


class MeticulousConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Meticulous."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return MeticulousOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            token = user_input.get(CONF_TOKEN)

            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            try:
                await async_validate_connection(
                    self.hass,
                    host=host,
                    port=port,
                    token=token,
                )
            except MeticulousAuthError:
                errors["base"] = "invalid_auth"
            except MeticulousConnectionError:
                errors["base"] = "cannot_connect"
            except MeticulousError:
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Meticulous ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_TOKEN: token,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(CONF_TOKEN): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )


class MeticulousOptionsFlow(OptionsFlow):
    """Handle Meticulous options."""

    _LEGACY_ALLOW_DANGEROUS_ACTION_KEY = "allow_dangerous_action"

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage Meticulous options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            allow = bool(user_input.get(CONF_ALLOW_DANGEROUS_ACTIONS, False))
            meticai_url = (user_input.get(CONF_METICAI_URL) or "").strip().rstrip("/")
            if meticai_url and not await self._async_meticai_reachable(meticai_url):
                errors[CONF_METICAI_URL] = "meticai_unreachable"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_ALLOW_DANGEROUS_ACTIONS: allow,
                        CONF_METICAI_URL: meticai_url,
                    },
                )

        current_allow = bool(
            self._config_entry.options.get(
                CONF_ALLOW_DANGEROUS_ACTIONS,
                self._config_entry.options.get(
                    self._LEGACY_ALLOW_DANGEROUS_ACTION_KEY,
                    False,
                ),
            )
        )
        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_ALLOW_DANGEROUS_ACTIONS,
                    default=current_allow,
                ): bool,
                vol.Optional(
                    CONF_METICAI_URL,
                    default=self._config_entry.options.get(CONF_METICAI_URL, ""),
                ): str,
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=errors
        )

    async def _async_meticai_reachable(self, url: str) -> bool:
        """Return True when `url` answers like a MeticAI server (GET /health)."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                f"{url}/health", timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    return False
                body = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return False
        return isinstance(body, dict) and body.get("status") == "ok"
