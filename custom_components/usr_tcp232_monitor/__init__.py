"""USR TCP232-410S diagnostic integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import UsrCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up USR TCP232 Monitor from a config entry."""
    coordinator = UsrCoordinator(hass, dict(entry.data), dict(entry.options))
    await coordinator.async_config_entry_first_refresh()

    if coordinator.mac and entry.unique_id != coordinator.mac:
        existing_entry = hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, coordinator.mac
        )
        if existing_entry and existing_entry.entry_id != entry.entry_id:
            _LOGGER.warning(
                "Cannot update unique_id for %s to %s; another entry (%s) already uses this MAC",
                entry.entry_id,
                coordinator.mac,
                existing_entry.entry_id,
            )
        else:
            try:
                hass.config_entries.async_update_entry(entry, unique_id=coordinator.mac)
            except ValueError as err:
                _LOGGER.warning(
                    "Failed to set unique_id %s for %s: %s",
                    coordinator.mac,
                    entry.entry_id,
                    err,
                )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: UsrCoordinator | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if coordinator:
            await coordinator.async_shutdown()
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry after options change."""
    await hass.config_entries.async_reload(entry.entry_id)
