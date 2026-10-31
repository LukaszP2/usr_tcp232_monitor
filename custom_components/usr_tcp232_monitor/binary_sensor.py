
"""Binary sensors for USR TCP232 Monitor."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import UsrCoordinator


class UsrOnlineBinarySensor(CoordinatorEntity[UsrCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Web interface reachable"
    _attr_device_class = "connectivity"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: UsrCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.host}_web_interface_reachable"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.host)},
            name="USR TCP232",
            manufacturer="USR IOT",
            model="TCP232 serial-to-Ethernet gateway",
            configuration_url=f"http://{coordinator.host}",
        )

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def available(self) -> bool:
        return True


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        UsrOnlineBinarySensor(coordinator),
        UsrMqttEnabledBinarySensor(coordinator),
    ])


class UsrMqttEnabledBinarySensor(CoordinatorEntity[UsrCoordinator], BinarySensorEntity):
    """Whether MQTT gateway is enabled in the USR configuration."""

    _attr_has_entity_name = True
    _attr_name = "MQTT gateway enabled"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: UsrCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.host}_mqtt_gateway_enabled"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.host)},
            name="USR TCP232",
            manufacturer="USR IOT",
            model="TCP232 serial-to-Ethernet gateway",
            configuration_url=f"http://{coordinator.host}",
        )

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("mqtt_enabled", False))

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success


