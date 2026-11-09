"""Config flow for USR TCP232 Monitor."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import UsrAuthError, async_validate_connection

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


def _clean_host(host_input: str) -> str:
    """Normalize user input host string."""
    host = host_input.strip().rstrip("/")
    if host.startswith("http://"):
        host = host[7:]
    elif host.startswith("https://"):
        host = host[8:]
    return host.split("/")[0]


async def validate_input(hass: HomeAssistant, user_input: dict[str, Any]) -> dict[str, Any]:
    """Validate host and credentials directly without background timers."""
    host = _clean_host(user_input[CONF_HOST])
    username = user_input[CONF_USERNAME]
    password = user_input[CONF_PASSWORD]

    try:
        data = await async_validate_connection(hass, host, username, password)
    except (UsrAuthError, ConfigEntryAuthFailed) as err:
        raise UsrAuthError from err
    except Exception as err:
        _LOGGER.debug("Failed to connect to USR device: %s", err)
        raise CannotConnect from err

    return data


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry: config_entries.ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle initial setup by user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = _clean_host(user_input[CONF_HOST])
            data = {
                CONF_HOST: host,
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            try:
                validated_data = await validate_input(self.hass, data)
            except UsrAuthError:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception in config flow user step")
                errors["base"] = "cannot_connect"
            else:
                mac = validated_data.get("mac")
                unique_id = mac if mac else host.lower()
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                devicename = (validated_data.get("identity") or {}).get("devicename")
                title = f"USR TCP232 ({devicename})" if devicename else f"USR TCP232 ({host})"
                return self.async_create_entry(title=title, data=data)

        data_schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_USERNAME, default="admin"): str,
            vol.Required(CONF_PASSWORD, default="admin"): str,
        })
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> config_entries.ConfigFlowResult:
        """Handle reauthentication upon auth failure."""
        entry_id = self.context.get("entry_id")
        if entry_id:
            self._reauth_entry = self.hass.config_entries.async_get_entry(entry_id)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}
        entry = (
            self._reauth_entry
            or (
                self._get_reauth_entry()
                if hasattr(self, "_get_reauth_entry")
                else self.hass.config_entries.async_get_entry(self.context.get("entry_id", ""))
            )
        )
        if not entry:
            return self.async_abort(reason="reauth_unsuccessful")

        if user_input is not None:
            data = {
                CONF_HOST: entry.data[CONF_HOST],
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            try:
                await validate_input(self.hass, data)
            except UsrAuthError:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception in reauth")
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(entry, data=data)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        default_username = entry.data.get(CONF_USERNAME, "admin")
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME, default=default_username): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
            description_placeholders={"host": entry.data.get(CONF_HOST, "")},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguring an existing integration."""
        errors: dict[str, str] = {}
        entry = (
            self._get_reconfigure_entry()
            if hasattr(self, "_get_reconfigure_entry")
            else self.hass.config_entries.async_get_entry(self.context.get("entry_id", ""))
        )
        if not entry:
            return self.async_abort(reason="reconfigure_unsuccessful")

        if user_input is not None:
            host = _clean_host(user_input[CONF_HOST])
            data = {
                CONF_HOST: host,
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            try:
                validated_data = await validate_input(self.hass, data)
            except UsrAuthError:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception in reconfigure")
                errors["base"] = "cannot_connect"
            else:
                mac = validated_data.get("mac")
                if mac and entry.unique_id and entry.unique_id not in (host.lower(), mac):
                    return self.async_abort(reason="different_device")

                self.hass.config_entries.async_update_entry(
                    entry,
                    data=data,
                    unique_id=mac or entry.unique_id,
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=entry.data.get(CONF_HOST, "")): str,
                vol.Required(CONF_USERNAME, default=entry.data.get(CONF_USERNAME, "admin")): str,
                vol.Required(CONF_PASSWORD, default=entry.data.get(CONF_PASSWORD, "")): str,
            }),
            errors=errors,
            description_placeholders={"host": entry.data.get(CONF_HOST, "")},
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for USR TCP232 Monitor."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=300)
                ),
            }),
        )
