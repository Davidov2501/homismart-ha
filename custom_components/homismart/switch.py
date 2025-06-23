"""Switch platform for HomISmart integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HomismartDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HomISmart switch platform."""
    coordinator: HomismartDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    if coordinator.data:
        for device_data in coordinator.data:
            device_type = device_data.get("type", "")
            if device_type in ["switch", "socket", "outlet"]:
                device_id = device_data.get("id")
                device_label = device_data.get("label", device_id)
                _LOGGER.info("🔌 Adding switch entity: %s (ID: %s)", device_label, device_id)
                entities.append(HomismartSwitch(coordinator, device_data, config_entry.entry_id))

    _LOGGER.info("✅ Added %d switch entities", len(entities))
    async_add_entities(entities)


class HomismartSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a HomISmart switch."""

    def __init__(
        self,
        coordinator: HomismartDataUpdateCoordinator,
        device_data: dict[str, Any],
        entry_id: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._device_data = device_data
        self._device_id = device_data.get("id")
        self._device = device_data.get("device")
        self._entry_id = entry_id
        
        device_label = device_data.get("label", self._device_id)
        self._attr_name = device_label
        self._attr_unique_id = f"{entry_id}_{self._device_id}"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_data.get("label", self._device_id),
            "manufacturer": "HomISmart",
            "model": self._device_data.get("type", "Smart Switch"),
            "via_device": (DOMAIN, self._entry_id),
        }

    def _get_current_device_data(self) -> dict[str, Any] | None:
        """Get current device data from coordinator."""
        if not self.coordinator.data:
            return None
        
        for device_data in self.coordinator.data:
            if device_data.get("id") == self._device_id:
                return device_data
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        device_data = self._get_current_device_data()
        if not device_data:
            return False
        return device_data.get("onLine", True) and self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        device_data = self._get_current_device_data()
        if not device_data:
            return False
            
        # Check various state attributes
        state = device_data.get("state")
        if state is not None:
            return bool(state)
            
        # For switches with level control, check current level
        current_level = device_data.get("current_level")
        if current_level is not None:
            return current_level > 0
            
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            success = await self.coordinator.async_turn_on_device(self._device_id)
            if success:
                _LOGGER.info("Successfully turned on switch %s", self._attr_name)
            else:
                _LOGGER.error("Failed to turn on switch %s", self._attr_name)
        except Exception as ex:
            _LOGGER.error("Failed to turn on switch %s: %s", self._attr_name, ex)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            success = await self.coordinator.async_turn_off_device(self._device_id)
            if success:
                _LOGGER.info("Successfully turned off switch %s", self._attr_name)
            else:
                _LOGGER.error("Failed to turn off switch %s", self._attr_name)
        except Exception as ex:
            _LOGGER.error("Failed to turn off switch %s: %s", self._attr_name, ex) 