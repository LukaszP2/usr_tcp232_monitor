"""Unit tests for UsrCoordinator and HTTP Digest auth."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from custom_components.usr_tcp232_monitor.const import DOMAIN
from custom_components.usr_tcp232_monitor.coordinator import (
    UsrAuthError,
    UsrCoordinator,
    _bytes,
    _hash_digest,
    _parse_auth_params,
    _quote_auth,
    async_validate_connection,
)


def test_bytes_parser() -> None:
    """Test byte counter parsing."""
    assert _bytes(None) is None
    assert _bytes("") is None
    assert _bytes("invalid") is None
    assert _bytes("233226 bytes") == 233226
    assert _bytes("0 bytes") == 0
    assert _bytes(123456) == 123456


def test_parse_auth_params_basic() -> None:
    """Test parsing Basic authentication challenge."""
    scheme, params = _parse_auth_params('Basic realm="USR-TCP232"')
    assert scheme == "basic"
    assert params.get("realm") == "USR-TCP232"


def test_parse_auth_params_digest() -> None:
    """Test parsing Digest authentication challenge."""
    header = 'Digest realm="testrealm@host.com", qop="auth,auth-int", nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093", opaque="5ccc069c403ebaf9f0171e9517f40e41", algorithm=MD5'
    scheme, params = _parse_auth_params(header)
    assert scheme == "digest"
    assert params["realm"] == "testrealm@host.com"
    assert params["qop"] == "auth,auth-int"
    assert params["nonce"] == "dcd98b7102dd2f0e8b11d0f600bfb0c093"
    assert params["opaque"] == "5ccc069c403ebaf9f0171e9517f40e41"
    assert params["algorithm"] == "MD5"


def test_parse_auth_params_invalid() -> None:
    """Test parsing invalid challenge header."""
    scheme, params = _parse_auth_params("Bearer token123")
    assert scheme == ""
    assert params == {}


def test_hash_digest() -> None:
    """Test Digest hash calculation."""
    md5_hash = _hash_digest("admin:USR:admin", "MD5")
    assert len(md5_hash) == 32
    sha256_hash = _hash_digest("admin:USR:admin", "SHA-256")
    assert len(sha256_hash) == 64

    with pytest.raises(ValueError, match="Unsupported HTTP Digest algorithm"):
        _hash_digest("test", "UNSUPPORTED")


def test_quote_auth() -> None:
    """Test string quoting for Authorization header."""
    assert _quote_auth("simple") == '"simple"'
    assert _quote_auth('with"quote') == '"with\\"quote"'
    assert _quote_auth("with\\slash") == '"with\\\\slash"'


def test_digest_header_generation() -> None:
    """Test building Digest header."""
    hass = MagicMock()
    config = {CONF_HOST: "192.168.1.100", CONF_USERNAME: "admin", CONF_PASSWORD: "password"}
    coord = UsrCoordinator(hass, config)
    coord._digest_challenge = {
        "realm": "USR",
        "nonce": "12345678",
        "qop": "auth",
        "algorithm": "MD5",
    }
    header = coord._digest_header("GET", "http://192.168.1.100/temp_status.json")
    assert header.startswith("Digest ")
    assert 'username="admin"' in header
    assert 'realm="USR"' in header
    assert 'nonce="12345678"' in header
    assert 'uri="/temp_status.json"' in header
    assert "response=" in header


def test_digest_header_incomplete_challenge() -> None:
    """Test that incomplete digest challenge raises UsrAuthError."""
    hass = MagicMock()
    coord = UsrCoordinator(hass, {CONF_HOST: "192.168.1.100", CONF_USERNAME: "a", CONF_PASSWORD: "b"})
    coord._digest_challenge = {"realm": "USR"}  # missing nonce
    with pytest.raises(UsrAuthError, match="Incomplete HTTP Digest challenge"):
        coord._digest_header("GET", "http://192.168.1.100/temp_status.json")


@pytest.mark.asyncio
async def test_coordinator_update_data_success() -> None:
    """Test successful data update from endpoints."""
    hass = MagicMock()
    config = {CONF_HOST: "192.168.1.100", CONF_USERNAME: "admin", CONF_PASSWORD: "password"}
    coord = UsrCoordinator(hass, config)

    mock_status = {
        "runtime": "10 days",
        "curripcn": "192.168.1.100",
        "usermac": "9C-F6-82-E0-78-86",
        "txcounta": "1000",
        "rxcounta": "2000",
        "txcountb": "3000",
        "rxcountb": "4000",
        "constatea": "Connected",
        "constateb": "Disconnected",
    }
    mock_identity = {
        "ver": "V1.0.0",
        "devicename": "USR-TCP232-410S",
        "devicetype": "TCP232-410S",
        "usermac": "9C-F6-82-E0-78-86",
    }
    mock_mqtt = {"mqtten": "1"}

    async def mock_request_json(session, endpoint):
        if endpoint == "temp_status.json":
            return mock_status
        if endpoint == "define.json":
            return mock_identity
        if endpoint == "mqttbase.json":
            return mock_mqtt
        return {}

    with (
        patch("custom_components.usr_tcp232_monitor.coordinator.async_get_clientsession") as mock_session,
        patch.object(coord, "_request_json", side_effect=mock_request_json),
    ):
        mock_session.return_value = MagicMock()
        data = await coord._async_update_data()

    assert data["mac"] == "9c:f6:82:e0:78:86"
    assert data["tx_a"] == 1000
    assert data["rx_a"] == 2000
    assert data["tx_b"] == 3000
    assert data["rx_b"] == 4000
    assert data["mqtt_enabled"] is True

    # Test unified DeviceInfo
    coord.data = data
    device_info = coord.device_info
    assert (DOMAIN, "9c:f6:82:e0:78:86") in device_info["identifiers"]
    assert (CONNECTION_NETWORK_MAC, "9c:f6:82:e0:78:86") in device_info["connections"]
    assert device_info["name"] == "USR-TCP232-410S"
    assert device_info["model"] == "TCP232-410S"
    assert device_info["sw_version"] == "V1.0.0"


@pytest.mark.asyncio
async def test_coordinator_mqttbase_404_graceful_degradation() -> None:
    """Test that 404 on mqttbase.json sets mqtt_enabled=False without error."""
    hass = MagicMock()
    config = {CONF_HOST: "192.168.1.100", CONF_USERNAME: "admin", CONF_PASSWORD: "password"}
    coord = UsrCoordinator(hass, config)

    mock_status = {"curripcn": "192.168.1.100", "usermac": "9C-F6-82-E0-78-86"}
    mock_identity = {"ver": "V1.0.0", "devicename": "USR-TCP232-302"}

    async def mock_request_json(session, endpoint):
        if endpoint == "temp_status.json":
            return mock_status
        if endpoint == "define.json":
            return mock_identity
        if endpoint == "mqttbase.json":
            return None  # 404 response
        return {}

    with (
        patch("custom_components.usr_tcp232_monitor.coordinator.async_get_clientsession"),
        patch.object(coord, "_request_json", side_effect=mock_request_json),
    ):
        data = await coord._async_update_data()

    assert data["mqtt_enabled"] is False
    assert data["mac"] == "9c:f6:82:e0:78:86"


@pytest.mark.asyncio
async def test_coordinator_auth_failure_raises_config_entry_auth_failed() -> None:
    """Test that auth rejection raises ConfigEntryAuthFailed."""
    hass = MagicMock()
    config = {CONF_HOST: "192.168.1.100", CONF_USERNAME: "admin", CONF_PASSWORD: "wrong"}
    coord = UsrCoordinator(hass, config)

    with (
        patch("custom_components.usr_tcp232_monitor.coordinator.async_get_clientsession"),
        patch.object(coord, "_request_json", side_effect=UsrAuthError("Rejected")),
        pytest.raises(ConfigEntryAuthFailed, match="USR TCP232 authentication failed"),
    ):
        await coord._async_update_data()


@pytest.mark.asyncio
async def test_async_validate_connection_no_timer() -> None:
    """Test that async_validate_connection performs a fetch without scheduling a refresh timer."""
    hass = MagicMock()
    mock_data = {"mac": "9c:f6:82:e0:78:86", "identity": {"devicename": "USR-TCP232-410S"}}

    with patch.object(UsrCoordinator, "_async_update_data", AsyncMock(return_value=mock_data)):
        result = await async_validate_connection(hass, "192.168.1.100", "admin", "admin")

    assert result["mac"] == "9c:f6:82:e0:78:86"


@pytest.mark.asyncio
async def test_coordinator_define_json_cached_on_subsequent_updates() -> None:
    """Test that define.json is only fetched when identity data is missing."""
    hass = MagicMock()
    config = {CONF_HOST: "192.168.1.100", CONF_USERNAME: "admin", CONF_PASSWORD: "password"}
    coord = UsrCoordinator(hass, config)

    mock_status = {
        "curripcn": "192.168.1.100",
        "usermac": "9C-F6-82-E0-78-86",
        "txcounta": "100",
        "rxcounta": "200",
    }
    mock_identity = {
        "ver": "V1.0.0",
        "devicename": "USR-TCP232-410S",
    }
    mock_mqtt = {"mqtten": "1"}

    requested_endpoints: list[str] = []

    async def mock_request_json(session, endpoint):
        requested_endpoints.append(endpoint)
        if endpoint == "temp_status.json":
            return mock_status
        if endpoint == "define.json":
            return mock_identity
        if endpoint == "mqttbase.json":
            return mock_mqtt
        return {}

    with (
        patch("custom_components.usr_tcp232_monitor.coordinator.async_get_clientsession"),
        patch.object(coord, "_request_json", side_effect=mock_request_json),
    ):
        # First cycle: identity missing -> 3 requests
        data1 = await coord._async_update_data()
        assert requested_endpoints == ["temp_status.json", "define.json", "mqttbase.json"]
        assert data1["identity"]["devicename"] == "USR-TCP232-410S"

        # Second cycle: identity cached in coordinator memory -> 2 requests
        requested_endpoints.clear()
        data2 = await coord._async_update_data()
        assert requested_endpoints == ["temp_status.json", "mqttbase.json"]
        assert data2["identity"]["devicename"] == "USR-TCP232-410S"
