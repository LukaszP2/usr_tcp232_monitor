"""Unit tests for USR TCP232 diagnostics."""
from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from custom_components.usr_tcp232_monitor.const import DOMAIN
from custom_components.usr_tcp232_monitor.coordinator import UsrCoordinator
from custom_components.usr_tcp232_monitor.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_redacts_password() -> None:
    """Test that passwords are redacted from diagnostics."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {
        CONF_HOST: "192.168.1.50",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "super_secret_password",
    }
    entry.options = {"scan_interval": 60}

    coord = MagicMock(spec=UsrCoordinator)
    coord.data = {
        "status": {"runtime": "5 days", "password": "leak"},
        "identity": {"devicename": "USR-TCP232-410S"},
    }
    entry.runtime_data = coord
    hass.data = {DOMAIN: {entry.entry_id: coord}}

    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert diag["entry"][CONF_HOST] == "192.168.1.50"
    assert diag["entry"][CONF_PASSWORD] == "**REDACTED**"
    assert diag["options"]["scan_interval"] == 60
    assert diag["data"]["status"]["password"] == "**REDACTED**"
