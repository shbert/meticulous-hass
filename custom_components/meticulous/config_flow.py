"""Config flow for Meticulous integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_TOKEN, DEFAULT_PORT, DOMAIN
from .coordinator import (
    MeticulousAuthError,
    MeticulousConnectionError,
    MeticulousError,
    async_validate_connection,
)


class MeticulousConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Meticulous."""

    VERSION = 1

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
