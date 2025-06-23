"""Light platform for HomISmart integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    LightEntity,
    LightEntityFeature,
    ColorMode,
)
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
    """Set up the HomISmart light platform."""
    coordinator: HomismartDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    if coordinator.data:
        for device_data in coordinator.data:
            device_type = device_data.get("type", "")
            if device_type in ["light", "dimmer"]:
                device_id = device_data.get("id")
                device_label = device_data.get("label", device_id)
                _LOGGER.info("💡 Adding light entity: %s (ID: %s)", device_label, device_id)
                entities.append(HomismartLight(coordinator, device_data, config_entry.entry_id))

    _LOGGER.info("✅ Added %d light entities", len(entities))
    async_add_entities(entities)


class HomismartLight(CoordinatorEntity, LightEntity):
    """Representation of a HomISmart light."""

    def __init__(
        self,
        coordinator: HomismartDataUpdateCoordinator,
        device_data: dict[str, Any],
        entry_id: str,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self._device_data = device_data
        self._device_id = device_data.get("id")
        self._device = device_data.get("device")
        self._entry_id = entry_id
        
        device_label = device_data.get("label", self._device_id)
        self._attr_name = device_label
        self._attr_unique_id = f"{entry_id}_{self._device_id}"
        
        # Set supported features and color modes
        if hasattr(self._device, 'set_level') or device_data.get("type") == "dimmer":
            self._attr_supported_features = LightEntityFeature.TRANSITION
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            self._attr_color_mode = ColorMode.ONOFF

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_data.get("label", self._device_id),
            "manufacturer": "HomISmart",
            "model": self._device_data.get("type", "Smart Light"),
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
        """Return true if light is on."""
        device_data = self._get_current_device_data()
        if not device_data:
            return False
            
        # Check various state attributes
        state = device_data.get("state")
        if state is not None:
            return bool(state)
            
        # For dimmers, check current level
        current_level = device_data.get("current_level")
        if current_level is not None:
            return current_level > 0
            
        return False

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        device_data = self._get_current_device_data()
        if not device_data:
            return None
            
        if self._attr_color_mode == ColorMode.BRIGHTNESS:
            current_level = device_data.get("current_level")
            if current_level is not None:
                # Convert from 0-100 to 0-255
                return int((current_level / 100) * 255)
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        try:
            brightness = kwargs.get("brightness")
            if brightness is not None and self._attr_color_mode == ColorMode.BRIGHTNESS:
                # Convert from 0-255 to 0-100 for position control
                level = int((brightness / 255) * 100)
                success = await self.coordinator.async_set_cover_position(self._device_id, level)
            else:
                success = await self.coordinator.async_turn_on_device(self._device_id)
            
            if success:
                _LOGGER.info("Successfully turned on light %s", self._attr_name)
            else:
                _LOGGER.error("Failed to turn on light %s", self._attr_name)
        except Exception as ex:
            _LOGGER.error("Failed to turn on light %s: %s", self._attr_name, ex)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        try:
            success = await self.coordinator.async_turn_off_device(self._device_id)
            if success:
                _LOGGER.info("Successfully turned off light %s", self._attr_name)
            else:
                _LOGGER.error("Failed to turn off light %s", self._attr_name)
        except Exception as ex:
            _LOGGER.error("Failed to turn off light %s: %s", self._attr_name, ex) 