"""Unit tests for USR TCP232 ConfigFlow and OptionsFlow."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from custom_components.usr_tcp232_monitor import async_setup_entry
from custom_components.usr_tcp232_monitor.config_flow import (
    CannotConnect,
    ConfigFlow,
    OptionsFlowHandler,
    _clean_host,
    validate_input,
)
from custom_components.usr_tcp232_monitor.const import CONF_SCAN_INTERVAL, DOMAIN
from custom_components.usr_tcp232_monitor.coordinator import UsrAuthError


def test_clean_host() -> None:
    """Test host input normalization."""
    assert _clean_host("192.168.1.50") == "192.168.1.50"
    assert _clean_host("http://192.168.1.50/") == "192.168.1.50"
    assert _clean_host("https://192.168.1.50:8080/path") == "192.168.1.50:8080"
    assert _clean_host("  192.168.1.50/ ") == "192.168.1.50"


@pytest.mark.asyncio
async def test_validate_input_success() -> None:
    """Test validate_input returning data on success."""
    hass = MagicMock()
    mock_data = {"mac": "9c:f6:82:e0:78:86", "identity": {"devicename": "USR-TCP232-410S"}}
    with patch(
        "custom_components.usr_tcp232_monitor.config_flow.async_validate_connection",
        AsyncMock(return_value=mock_data),
    ):
        result = await validate_input(
            hass,
            {CONF_HOST: "192.168.1.50", CONF_USERNAME: "admin", CONF_PASSWORD: "password"},
        )
    assert result["mac"] == "9c:f6:82:e0:78:86"


@pytest.mark.asyncio
async def test_validate_input_auth_error() -> None:
    """Test validate_input raising UsrAuthError."""
    hass = MagicMock()
    with patch(
        "custom_components.usr_tcp232_monitor.config_flow.async_validate_connection",
        AsyncMock(side_effect=UsrAuthError("Rejected")),
    ), pytest.raises(UsrAuthError):
        await validate_input(
            hass,
            {CONF_HOST: "192.168.1.50", CONF_USERNAME: "admin", CONF_PASSWORD: "wrong"},
        )


@pytest.mark.asyncio
async def test_validate_input_cannot_connect() -> None:
    """Test validate_input raising CannotConnect."""
    hass = MagicMock()
    with (
        patch(
            "custom_components.usr_tcp232_monitor.config_flow.async_validate_connection",
            AsyncMock(side_effect=TimeoutError("Unreachable")),
        ),
        pytest.raises(CannotConnect),
    ):
        await validate_input(
            hass,
            {CONF_HOST: "192.168.1.50", CONF_USERNAME: "admin", CONF_PASSWORD: "password"},
        )


@pytest.mark.asyncio
async def test_config_flow_user_success() -> None:
    """Test full user step in ConfigFlow."""
    flow = ConfigFlow()
    flow.hass = MagicMock()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock()

    mock_validated = {
        "mac": "9c:f6:82:e0:78:86",
        "identity": {"devicename": "USR-TCP232-410S"},
    }

    with patch(
        "custom_components.usr_tcp232_monitor.config_flow.validate_input",
        AsyncMock(return_value=mock_validated),
    ):
        result = await flow.async_step_user({
            CONF_HOST: "192.168.1.50",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        })

    assert result["type"] == "create_entry"
    assert result["title"] == "USR TCP232 (USR-TCP232-410S)"
    assert result["data"][CONF_HOST] == "192.168.1.50"
    flow.async_set_unique_id.assert_called_once_with("9c:f6:82:e0:78:86")


@pytest.mark.asyncio
async def test_config_flow_user_invalid_auth() -> None:
    """Test invalid credentials error in user step."""
    flow = ConfigFlow()
    flow.hass = MagicMock()

    with patch(
        "custom_components.usr_tcp232_monitor.config_flow.validate_input",
        AsyncMock(side_effect=UsrAuthError),
    ):
        result = await flow.async_step_user({
            CONF_HOST: "192.168.1.50",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "wrong",
        })

    assert result["type"] == "form"
    assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
async def test_reauth_flow_success() -> None:
    """Test reauth confirmation step updating config entry."""
    flow = ConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config_entries.async_reload = AsyncMock()
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {
        CONF_HOST: "192.168.1.50",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "old",
    }
    flow._reauth_entry = entry

    with patch(
        "custom_components.usr_tcp232_monitor.config_flow.validate_input",
        AsyncMock(return_value={}),
    ):
        result = await flow.async_step_reauth_confirm({
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "new_password",
        })

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    flow.hass.config_entries.async_update_entry.assert_called_once()
    flow.hass.config_entries.async_reload.assert_called_once_with("test_entry")


@pytest.mark.asyncio
async def test_options_flow() -> None:
    """Test options flow for scan interval."""
    entry = MagicMock()
    entry.options = {CONF_SCAN_INTERVAL: 60}
    handler = OptionsFlowHandler(entry)

    # Show form
    form = await handler.async_step_init()
    assert form["type"] == "form"

    # Save form
    result = await handler.async_step_init({CONF_SCAN_INTERVAL: 120})
    assert result["type"] == "create_entry"
    assert result["data"][CONF_SCAN_INTERVAL] == 120


@pytest.mark.asyncio
async def test_async_setup_entry_unique_id_collision_prevention() -> None:
    """Test that existing unique_id collision is prevented without raising ValueError."""
    hass = MagicMock()
    hass.data = {}
    entry = MagicMock()
    entry.entry_id = "entry_1"
    entry.unique_id = None
    entry.data = {CONF_HOST: "192.168.1.50", CONF_USERNAME: "admin", CONF_PASSWORD: "pw"}
    entry.options = {}

    existing_entry = MagicMock()
    existing_entry.entry_id = "entry_2"
    existing_entry.unique_id = "9c:f6:82:e0:78:86"

    hass.config_entries.async_entry_for_domain_unique_id.return_value = existing_entry
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

    with patch("custom_components.usr_tcp232_monitor.UsrCoordinator") as mock_coord_cls:
        coord_instance = MagicMock()
        coord_instance.async_config_entry_first_refresh = AsyncMock()
        coord_instance.mac = "9c:f6:82:e0:78:86"
        mock_coord_cls.return_value = coord_instance

        result = await async_setup_entry(hass, entry)

    assert result is True
    # Should check collision and NOT call async_update_entry
    hass.config_entries.async_entry_for_domain_unique_id.assert_called_once_with(
        DOMAIN, "9c:f6:82:e0:78:86"
    )
    hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
async def test_async_setup_entry_unique_id_updated_when_no_collision() -> None:
    """Test that unique_id is updated when no collision exists."""
    hass = MagicMock()
    hass.data = {}
    entry = MagicMock()
    entry.entry_id = "entry_1"
    entry.unique_id = None
    entry.data = {CONF_HOST: "192.168.1.50", CONF_USERNAME: "admin", CONF_PASSWORD: "pw"}
    entry.options = {}

    hass.config_entries.async_entry_for_domain_unique_id.return_value = None
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

    with patch("custom_components.usr_tcp232_monitor.UsrCoordinator") as mock_coord_cls:
        coord_instance = MagicMock()
        coord_instance.async_config_entry_first_refresh = AsyncMock()
        coord_instance.mac = "9c:f6:82:e0:78:86"
        mock_coord_cls.return_value = coord_instance

        result = await async_setup_entry(hass, entry)

    assert result is True
    hass.config_entries.async_update_entry.assert_called_once_with(
        entry, unique_id="9c:f6:82:e0:78:86"
    )
