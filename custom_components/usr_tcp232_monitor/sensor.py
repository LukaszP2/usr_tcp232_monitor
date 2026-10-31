
"""Sensors for USR TCP232 Monitor."""
from __future__ import annotations

from homeassistant.const import CONF_HOST, EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .coordinator import UsrCoordinator


def _device_info(coordinator: UsrCoordinator) -> DeviceInfo:
    identity = coordinator.data.get("identity", {}) if coordinator.data else {}
    mac = str(identity.get("usermac") or coordinator.data.get("status", {}).get("usermac", "")).replace("-", "").upper()
    identifiers = {(DOMAIN, coordinator.host)}
    return DeviceInfo(
        identifiers=identifiers,
        name=str(identity.get("devicename") or "USR TCP232"),
        manufacturer="USR IOT",
        model=str(identity.get("devicename") or "TCP232-410S"),
        sw_version=str(identity.get("ver") or ""),
        configuration_url=f"http://{coordinator.host}",
    )


class UsrBaseSensor(CoordinatorEntity[UsrCoordinator], SensorEntity):
    _attr_has_entity_name = True
    entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: UsrCoordinator, key: str, name: str, unit: str | None = None):
        super().__init__(coordinator)
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.host}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = _device_info(coordinator)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and super().available


class UsrTextSensor(UsrBaseSensor):
    def __init__(self, coordinator, key, name, source, field):
        super().__init__(coordinator, key, name)
        self.source = source
        self.field = field

    @property
    def native_value(self):
        return self.coordinator.data.get(self.source, {}).get(self.field)


class UsrCounterSensor(UsrBaseSensor):
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator, key, name, field):
        super().__init__(coordinator, key, name, "B")
        self.field = field

    @property
    def native_value(self):
        return self.coordinator.data.get(self.field)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        UsrTextSensor(coordinator, "firmware", "Firmware", "identity", "ver"),
        UsrTextSensor(coordinator, "model", "Model", "identity", "devicename"),
        UsrTextSensor(coordinator, "hardware_type", "Hardware type", "identity", "devicetype"),
        UsrTextSensor(coordinator, "runtime", "Runtime", "status", "runtime"),
        UsrTextSensor(coordinator, "ip_address", "IP address", "status", "curripcn"),
        UsrTextSensor(coordinator, "mac_address", "MAC address", "status", "usermac"),
        UsrTextSensor(coordinator, "gateway", "Default gateway", "status", "currgip"),
        UsrTextSensor(coordinator, "dns_primary", "Primary DNS", "status", "dnsmain"),
        UsrTextSensor(coordinator, "dns_secondary", "Secondary DNS", "status", "dnsspare"),
        UsrTextSensor(coordinator, "port_a_status", "Port A connection", "status", "constatea"),
        UsrTextSensor(coordinator, "port_b_status", "Port B connection", "status", "constateb"),
        UsrCounterSensor(coordinator, "tx_a", "Port A TX", "tx_a"),
        UsrCounterSensor(coordinator, "rx_a", "Port A RX", "rx_a"),
        UsrCounterSensor(coordinator, "tx_b", "Port B TX", "tx_b"),
        UsrCounterSensor(coordinator, "rx_b", "Port B RX", "rx_b"),
        UsrTextSensor(coordinator, "mqtt_connection_status", "MQTT connection status", "status", "mqttconns"),
    ]
    async_add_entities(entities)
