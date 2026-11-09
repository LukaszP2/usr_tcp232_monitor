"""Binary sensors for USR TCP232 Monitor."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import UsrCoordinator


class UsrOnlineBinarySensor(CoordinatorEntity[UsrCoordinator], BinarySensorEntity):
    """Connectivity binary sensor representing web interface reachability."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "web_interface_reachable"

    def __init__(self, coordinator: UsrCoordinator) -> None:
        super().__init__(coordinator)
        prefix = coordinator.mac or coordinator.host
        self._attr_unique_id = f"{prefix}_web_interface_reachable"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool:
        """Return true if coordinator successfully fetched data."""
        return self.coordinator.last_update_success

    @property
    def available(self) -> bool:
        """Keep binary sensor available so disconnected state is visible."""
        return True


class UsrMqttEnabledBinarySensor(CoordinatorEntity[UsrCoordinator], BinarySensorEntity):
    """Whether MQTT gateway is enabled in the USR configuration."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "mqtt_gateway_enabled"

    def __init__(self, coordinator: UsrCoordinator) -> None:
        super().__init__(coordinator)
        prefix = coordinator.mac or coordinator.host
        self._attr_unique_id = f"{prefix}_mqtt_gateway_enabled"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool:
        """Return true if MQTT is enabled."""
        if not self.coordinator.data:
            return False
        return bool(self.coordinator.data.get("mqtt_enabled", False))

    @property
    def available(self) -> bool:
        """Return true if coordinator update was successful."""
        return self.coordinator.last_update_success


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from config entry."""
    coordinator: UsrCoordinator = getattr(entry, "runtime_data", None) or hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        UsrOnlineBinarySensor(coordinator),
        UsrMqttEnabledBinarySensor(coordinator),
    ])
