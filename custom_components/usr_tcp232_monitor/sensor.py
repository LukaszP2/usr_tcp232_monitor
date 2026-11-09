"""Sensors for USR TCP232 Monitor."""
from __future__ import annotations

import re
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfInformation, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import UsrCoordinator


def parse_runtime(value: Any) -> int | None:
    """Parse USR runtime string into integer seconds."""
    if value is None:
        return None
    val_str = str(value).strip()
    if not val_str:
        return None

    # Format 1: Pure integer seconds e.g. "12345" or "12345 s"
    pure_digits = re.match(r"^(\d+)\s*(?:s|sec|seconds)?$", val_str, re.IGNORECASE)
    if pure_digits:
        return int(pure_digits.group(1))

    # Format 2: "X days, HH:MM:SS" or "X day HH:MM:SS"
    days_match = re.search(r"(\d+)\s*(?:days?|d)", val_str, re.IGNORECASE)
    days = int(days_match.group(1)) if days_match else 0
    time_match = re.search(r"(\d{1,2}):(\d{2}):(\d{2})", val_str)
    if time_match:
        hours = int(time_match.group(1))
        minutes = int(time_match.group(2))
        seconds = int(time_match.group(3))
        return days * 86400 + hours * 3600 + minutes * 60 + seconds

    return None


class UsrBaseSensor(CoordinatorEntity[UsrCoordinator], SensorEntity):
    """Base sensor for USR TCP232."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UsrCoordinator,
        key: str,
        name: str | None = None,
        unit: str | None = None,
        entity_category: EntityCategory | None = None,
    ) -> None:
        super().__init__(coordinator)
        self.key = key
        self._attr_translation_key = key
        if name:
            self._attr_name = name
        prefix = coordinator.mac or coordinator.host
        self._attr_unique_id = f"{prefix}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_entity_category = entity_category
        self._attr_device_info = coordinator.device_info


class UsrTextSensor(UsrBaseSensor):
    """Text-based sensor."""

    def __init__(
        self,
        coordinator: UsrCoordinator,
        key: str,
        name: str,
        source: str,
        field: str,
        entity_category: EntityCategory | None = EntityCategory.DIAGNOSTIC,
    ) -> None:
        super().__init__(coordinator, key, name, entity_category=entity_category)
        self.source = source
        self.field = field

    @property
    def native_value(self) -> Any:
        """Return raw text value safely."""
        if not self.coordinator.data:
            return None
        source_data = self.coordinator.data.get(self.source)
        if not isinstance(source_data, dict):
            return None
        return source_data.get(self.field)


class UsrRuntimeSensor(UsrBaseSensor):
    """Runtime duration sensor."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(
        self,
        coordinator: UsrCoordinator,
        key: str,
        name: str,
        source: str,
        field: str,
    ) -> None:
        super().__init__(
            coordinator,
            key,
            name,
            unit=UnitOfTime.SECONDS,
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        self.source = source
        self.field = field

    @property
    def native_value(self) -> int | None:
        """Return runtime in seconds."""
        if not self.coordinator.data:
            return None
        source_data = self.coordinator.data.get(self.source)
        if not isinstance(source_data, dict):
            return None
        return parse_runtime(source_data.get(self.field))


class UsrCounterSensor(UsrBaseSensor):
    """Byte counter telemetry sensor."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_device_class = SensorDeviceClass.DATA_SIZE

    def __init__(
        self,
        coordinator: UsrCoordinator,
        key: str,
        name: str,
        field: str,
        entity_category: EntityCategory | None = None,
    ) -> None:
        super().__init__(
            coordinator,
            key,
            name,
            unit=UnitOfInformation.BYTES,
            entity_category=entity_category,
        )
        self.field = field

    @property
    def native_value(self) -> int | None:
        """Return byte counter value."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.field)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up USR TCP232 sensors from a config entry."""
    coordinator: UsrCoordinator = getattr(entry, "runtime_data", None) or hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        # Diagnostic metadata
        UsrTextSensor(coordinator, "firmware", "Firmware", "identity", "ver"),
        UsrTextSensor(coordinator, "model", "Model", "identity", "devicename"),
        UsrTextSensor(coordinator, "hardware_type", "Hardware type", "identity", "devicetype"),
        UsrRuntimeSensor(coordinator, "runtime", "Runtime", "status", "runtime"),
        UsrTextSensor(coordinator, "ip_address", "IP address", "status", "curripcn"),
        UsrTextSensor(coordinator, "mac_address", "MAC address", "status", "usermac"),
        UsrTextSensor(coordinator, "gateway", "Default gateway", "status", "currgip"),
        UsrTextSensor(coordinator, "dns_primary", "Primary DNS", "status", "dnsmain"),
        UsrTextSensor(coordinator, "dns_secondary", "Secondary DNS", "status", "dnsspare"),
        UsrTextSensor(coordinator, "mqtt_connection_status", "MQTT connection status", "status", "mqttconns"),
        # Primary telemetry sensors (entity_category=None)
        UsrTextSensor(coordinator, "port_a_status", "Port A connection", "status", "constatea", entity_category=None),
        UsrCounterSensor(coordinator, "tx_a", "Port A TX", "tx_a", entity_category=None),
        UsrCounterSensor(coordinator, "rx_a", "Port A RX", "rx_a", entity_category=None),
    ]

    status = (coordinator.data.get("status") or {}) if coordinator.data else {}
    if status.get("constateb") is not None or status.get("txcountb") is not None:
        entities.extend([
            UsrTextSensor(coordinator, "port_b_status", "Port B connection", "status", "constateb", entity_category=None),
            UsrCounterSensor(coordinator, "tx_b", "Port B TX", "tx_b", entity_category=None),
            UsrCounterSensor(coordinator, "rx_b", "Port B RX", "rx_b", entity_category=None),
        ])

    async_add_entities(entities)
