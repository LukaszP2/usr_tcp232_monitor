"""Config flow for USR TCP232 Monitor."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import UsrAuthError, UsrCoordinator


async def validate_input(hass: HomeAssistant, user_input: dict) -> None:
    """Validate host and credentials by reading the device endpoints."""
    coordinator = UsrCoordinator(hass, user_input)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        # Home Assistant may wrap UpdateFailed in ConfigEntryNotReady; walk the
        # exception chain so an authentication rejection gets the right UI error.
        current: BaseException | None = err
        while current is not None:
            if isinstance(current, UsrAuthError):
                raise UsrAuthError from err
            current = current.__cause__
        raise


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip().rstrip("/")
            if host.startswith("http://"):
                host = host[7:]
            elif host.startswith("https://"):
                host = host[8:]
            host = host.split("/")[0]
            data = {
                CONF_HOST: host,
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            await self.async_set_unique_id(host.lower())
            self._abort_if_unique_id_configured()
            try:
                await validate_input(self.hass, data)
            except UsrAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=f"USR TCP232 ({host})", data=data)

        data_schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        })
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
