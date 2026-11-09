"""Unit tests for USR TCP232 sensors."""
from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfInformation, UnitOfTime

from custom_components.usr_tcp232_monitor.coordinator import UsrCoordinator
from custom_components.usr_tcp232_monitor.sensor import (
    UsrCounterSensor,
    UsrRuntimeSensor,
    UsrTextSensor,
    async_setup_entry,
    parse_runtime,
)


def test_text_sensor_properties() -> None:
    """Test UsrTextSensor reads nested fields safely."""
    coord = MagicMock(spec=UsrCoordinator)
    coord.host = "192.168.1.100"
    coord.mac = "9c:f6:82:e0:78:86"
    coord.device_info = MagicMock()
    coord.data = {
        "status": {"runtime": "12 days, 04:12:30", "constatea": "Connected"},
        "identity": {"ver": "V1.0.0"},
    }

    sensor = UsrTextSensor(coord, "firmware", "Firmware", "identity", "ver")
    assert sensor.unique_id == "9c:f6:82:e0:78:86_firmware"
    assert sensor.entity_category == EntityCategory.DIAGNOSTIC
    assert sensor.native_value == "V1.0.0"

    # Test safe None handling
    coord.data = {"status": None}
    assert sensor.native_value is None

    coord.data = None
    assert sensor.native_value is None


def test_runtime_sensor_properties() -> None:
    """Test parse_runtime and UsrRuntimeSensor."""
    assert parse_runtime("10 days, 04:12:30") == 879150
    assert parse_runtime("0 days 01:23:45") == 5025
    assert parse_runtime("12345") == 12345
    assert parse_runtime("12345 s") == 12345
    assert parse_runtime(None) is None
    assert parse_runtime("") is None
    assert parse_runtime("invalid") is None

    coord = MagicMock(spec=UsrCoordinator)
    coord.host = "192.168.1.100"
    coord.mac = "9c:f6:82:e0:78:86"
    coord.device_info = MagicMock()
    coord.data = {"status": {"runtime": "10 days, 04:12:30"}}

    sensor = UsrRuntimeSensor(coord, "runtime", "Runtime", "status", "runtime")
    assert sensor.unique_id == "9c:f6:82:e0:78:86_runtime"
    assert sensor.device_class == SensorDeviceClass.DURATION
    assert sensor.native_unit_of_measurement == UnitOfTime.SECONDS
    assert sensor.entity_category == EntityCategory.DIAGNOSTIC
    assert sensor.native_value == 879150


def test_counter_sensor_properties() -> None:
    """Test UsrCounterSensor states and units."""
    coord = MagicMock(spec=UsrCoordinator)
    coord.host = "192.168.1.100"
    coord.mac = "9c:f6:82:e0:78:86"
    coord.device_info = MagicMock()
    coord.data = {"tx_a": 543210}

    counter = UsrCounterSensor(coord, "tx_a", "Port A TX", "tx_a")
    assert counter.unique_id == "9c:f6:82:e0:78:86_tx_a"
    assert counter.native_value == 543210
    assert counter.state_class == SensorStateClass.TOTAL_INCREASING
    assert counter.device_class == SensorDeviceClass.DATA_SIZE
    assert counter.native_unit_of_measurement == UnitOfInformation.BYTES
    assert counter.entity_category is None  # Primary telemetry entity


async def test_async_setup_entry_port_detection() -> None:
    """Test dynamic detection of Port B during setup."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "test_entry"

    coord = MagicMock(spec=UsrCoordinator)
    coord.host = "192.168.1.100"
    coord.mac = "9c:f6:82:e0:78:86"
    coord.device_info = MagicMock()
    coord.data = {
        "status": {"constatea": "Connected"},  # No port B
        "identity": {"devicename": "USR-TCP232-302"},
    }
    entry.runtime_data = coord

    entities_added = []

    def mock_add_entities(entities):
        entities_added.extend(entities)

    await async_setup_entry(hass, entry, mock_add_entities)

    keys = [e.key for e in entities_added]
    assert "port_a_status" in keys
    assert "tx_a" in keys
    assert "port_b_status" not in keys
    assert "tx_b" not in keys
