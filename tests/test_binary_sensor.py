"""Unit tests for USR TCP232 binary sensors."""
from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import EntityCategory

from custom_components.usr_tcp232_monitor.binary_sensor import (
    UsrMqttEnabledBinarySensor,
    UsrOnlineBinarySensor,
    async_setup_entry,
)
from custom_components.usr_tcp232_monitor.coordinator import UsrCoordinator


def test_online_binary_sensor() -> None:
    """Test web interface reachable binary sensor."""
    coord = MagicMock(spec=UsrCoordinator)
    coord.host = "192.168.1.100"
    coord.mac = "9c:f6:82:e0:78:86"
    coord.device_info = MagicMock()
    coord.last_update_success = True

    sensor = UsrOnlineBinarySensor(coord)
    assert sensor.unique_id == "9c:f6:82:e0:78:86_web_interface_reachable"
    assert sensor.device_class == BinarySensorDeviceClass.CONNECTIVITY
    assert sensor.entity_category is None
    assert sensor.is_on is True
    assert sensor.available is True  # Always available to reflect offline status

    coord.last_update_success = False
    assert sensor.is_on is False
    assert sensor.available is True


def test_mqtt_enabled_binary_sensor() -> None:
    """Test MQTT gateway enabled binary sensor."""
    coord = MagicMock(spec=UsrCoordinator)
    coord.host = "192.168.1.100"
    coord.mac = "9c:f6:82:e0:78:86"
    coord.device_info = MagicMock()
    coord.last_update_success = True
    coord.data = {"mqtt_enabled": True}

    sensor = UsrMqttEnabledBinarySensor(coord)
    assert sensor.unique_id == "9c:f6:82:e0:78:86_mqtt_gateway_enabled"
    assert sensor.entity_category == EntityCategory.DIAGNOSTIC
    assert sensor.is_on is True

    coord.data = {"mqtt_enabled": False}
    assert sensor.is_on is False

    coord.data = None
    assert sensor.is_on is False


async def test_binary_sensor_setup_entry() -> None:
    """Test setup of binary sensor platform."""
    hass = MagicMock()
    entry = MagicMock()
    coord = MagicMock(spec=UsrCoordinator)
    coord.host = "192.168.1.100"
    coord.mac = "9c:f6:82:e0:78:86"
    coord.device_info = MagicMock()
    entry.runtime_data = coord

    entities_added = []
    await async_setup_entry(hass, entry, lambda entities: entities_added.extend(entities))

    assert len(entities_added) == 2
    assert isinstance(entities_added[0], UsrOnlineBinarySensor)
    assert isinstance(entities_added[1], UsrMqttEnabledBinarySensor)
