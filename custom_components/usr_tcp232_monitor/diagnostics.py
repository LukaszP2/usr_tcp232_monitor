"""Diagnostics support for USR TCP232 Monitor."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import UsrCoordinator

TO_REDACT = {CONF_PASSWORD, "password", "mqttpassword", "userpwd"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: UsrCoordinator = (
        getattr(entry, "runtime_data", None)
        or hass.data.get(DOMAIN, {}).get(entry.entry_id)
    )

    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "data": async_redact_data(dict(coordinator.data or {}), TO_REDACT),
    }
