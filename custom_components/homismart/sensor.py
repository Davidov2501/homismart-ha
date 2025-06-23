"""Support for HomISmart sensors."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS

from .const import DOMAIN
from .coordinator import HomismartDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="battery",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery",
    ),
    SensorEntityDescription(
        key="position",
        name="Position",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:window-shutter",
    ),
    SensorEntityDescription(
        key="signal_strength",
        name="Signal Strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        icon="mdi:wifi",
    ),
    SensorEntityDescription(
        key="status",
        name="Status",
        icon="mdi:information",
    ),
    SensorEntityDescription(
        key="last_seen",
        name="Last Seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock",
    ),
    SensorEntityDescription(
        key="curtain_state",
        name="Curtain State",
        icon="mdi:curtains",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HomISmart sensors from a config entry."""
    coordinator: HomismartDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    
    if coordinator.data:
        for device in coordinator.data:
            device_type = device.get("type", "unknown")
            _LOGGER.debug("🔍 Setting up sensors for device: %s (type: %s)", device.get("label", "Unknown"), device_type)
            
            # Add relevant sensors based on device type and available data
            for description in SENSOR_TYPES:
                if _should_create_sensor(device, description):
                    entities.append(
                        HomismartSensor(
                            coordinator,
                            device,
                            description,
                            config_entry.entry_id,
                        )
                    )
    
    if entities:
        async_add_entities(entities)
        _LOGGER.info("📊 Added %d HomISmart sensors", len(entities))
    else:
        _LOGGER.warning("⚠️ No sensor entities created")


def _should_create_sensor(device: dict[str, Any], description: SensorEntityDescription) -> bool:
    """Determine if a sensor should be created for a device."""
    device_type = device.get("type", "")
    
    # Position sensor for covers/shutters
    if description.key == "position" and device_type in ["shutter", "cover", "curtain"]:
        return True
    
    # Battery sensor for battery-powered devices
    if description.key == "battery" and device.get("battery") is not None:
        return True
    
    # Signal strength for wireless devices
    if description.key == "signal_strength" and device.get("rssi") is not None:
        return True
    
    # Status sensor for all devices with online status
    if description.key == "status" and device.get("onLine") is not None:
        return True
    
    # Last seen for all devices
    if description.key == "last_seen":
        return True
    
    # Curtain state for shutters/covers
    if description.key == "curtain_state" and device_type in ["shutter", "cover", "curtain"]:
        return True
    
    return False


class HomismartSensor(CoordinatorEntity, SensorEntity):
    """Representation of a HomISmart sensor."""

    def __init__(
        self,
        coordinator: HomismartDataUpdateCoordinator,
        device: dict[str, Any],
        description: SensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device = device
        self._device_id = device.get("id")
        self._entry_id = entry_id
        
        device_name = device.get("label", f"Device {self._device_id}")
        self._attr_name = f"{device_name} {description.name}"
        self._attr_unique_id = f"{entry_id}_{self._device_id}_{description.key}"
        
        _LOGGER.debug("🔧 Created sensor: %s (ID: %s)", self._attr_name, self._attr_unique_id)

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device.get("label", f"Device {self._device_id}"),
            "manufacturer": "HomISmart",
            "model": self._device.get("type", "Unknown"),
            "via_device": (DOMAIN, self._entry_id),
        }

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
            
        # Find current device data
        current_device = None
        for device in self.coordinator.data:
            if device.get("id") == self._device_id:
                current_device = device
                break
        
        if not current_device:
            return None
        
        key = self.entity_description.key
        
        if key == "battery":
            return current_device.get("battery")
        elif key == "position":
            # Convert HomISmart position (0=open, 100=closed) to HA position (0=closed, 100=open)
            raw_position = current_device.get("current_level")
            if raw_position is not None:
                return 100 - raw_position
            return None
        elif key == "signal_strength":
            return current_device.get("rssi")
        elif key == "status":
            online = current_device.get("onLine")
            if online is True:
                return "Online"
            elif online is False:
                return "Offline"
            return "Unknown"
        elif key == "last_seen":
            # Create a timestamp for last update with timezone
            return datetime.now(timezone.utc)
        elif key == "curtain_state":
            state = current_device.get("curtainState")
            if state is not None:
                return state
            # Fallback to position-based state
            position = current_device.get("current_level", 0)
            if position <= 5:
                return "Open"
            elif position >= 95:
                return "Closed"
            else:
                return "Partially Open"
        
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self._device_id is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return {}
            
        # Find current device data
        current_device = None
        for device in self.coordinator.data:
            if device.get("id") == self._device_id:
                current_device = device
                break
        
        if not current_device:
            return {}
        
        attributes = {
            "device_id": self._device_id,
            "device_type": current_device.get("type"),
            "device_label": current_device.get("label"),
        }
        
        # Add sensor-specific attributes
        key = self.entity_description.key
        if key == "position":
            attributes["raw_position"] = current_device.get("current_level")
            attributes["target_position"] = current_device.get("target_level")
        elif key == "status":
            attributes["online"] = current_device.get("onLine")
            attributes["last_communication"] = current_device.get("lastCommunication")
        
        return attributes 