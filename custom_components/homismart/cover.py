"""Cover platform for HomISmart integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
    CoverDeviceClass,
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
    """Set up the HomISmart cover platform."""
    _LOGGER.info("🏠 Setting up HomISmart cover platform...")
    
    coordinator: HomismartDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    if coordinator.data:
        for device_data in coordinator.data:
            device_type = device_data.get("type", "")
            if device_type in ["shutter", "cover", "curtain"]:
                device_id = device_data.get("id")
                device_label = device_data.get("label", device_id)
                _LOGGER.info("📋 Adding cover entity: %s (ID: %s)", device_label, device_id)
                entities.append(HomismartCover(coordinator, device_data, config_entry.entry_id))

    _LOGGER.info("✅ Added %d cover entities", len(entities))
    async_add_entities(entities)


class HomismartCover(CoordinatorEntity, CoverEntity):
    """Representation of a HomISmart cover."""

    def __init__(
        self,
        coordinator: HomismartDataUpdateCoordinator,
        device_data: dict[str, Any],
        entry_id: str,
    ) -> None:
        """Initialize the cover."""
        super().__init__(coordinator)
        self._device_data = device_data
        self._device_id = device_data.get("id")
        self._device = device_data.get("device")
        self._entry_id = entry_id
        
        device_label = device_data.get("label", self._device_id)
        self._attr_name = device_label
        self._attr_unique_id = f"{entry_id}_{self._device_id}"
        self._attr_device_class = CoverDeviceClass.SHUTTER

        # Set supported features based on device capabilities
        self._attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        
        if hasattr(self._device, 'set_level'):
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_data.get("label", self._device_id),
            "manufacturer": "HomISmart",
            "model": self._device_data.get("type", "Smart Cover"),
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
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        device_data = self._get_current_device_data()
        if not device_data:
            return None
            
        # HomISmart: 0=open, 100=closed
        current_level = device_data.get("current_level")
        if current_level is not None:
            return current_level >= 95  # Consider 95%+ as closed
        return None

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover (0=closed, 100=open for HA)."""
        device_data = self._get_current_device_data()
        if not device_data:
            return None
            
        # HomISmart: 0=open, 100=closed, so invert for HA (100-value)
        current_level = device_data.get("current_level")
        if current_level is not None:
            return 100 - current_level
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        device_data = self._get_current_device_data()
        if not device_data:
            return False
        return device_data.get("onLine", True) and self.coordinator.last_update_success

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover (HomISmart: 0=open, so send 0)."""
        try:
            success = await self.coordinator.async_set_cover_position(self._device_id, 100)  # HA: 100=open
            if success:
                _LOGGER.info("Successfully opened cover %s", self._attr_name)
            else:
                _LOGGER.error("Failed to open cover %s", self._attr_name)
        except Exception as ex:
            _LOGGER.error("Failed to open cover %s: %s", self._attr_name, ex)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover (HomISmart: 100=closed, so send 100)."""
        try:
            success = await self.coordinator.async_set_cover_position(self._device_id, 0)  # HA: 0=closed
            if success:
                _LOGGER.info("Successfully closed cover %s", self._attr_name)
            else:
                _LOGGER.error("Failed to close cover %s", self._attr_name)
        except Exception as ex:
            _LOGGER.error("Failed to close cover %s: %s", self._attr_name, ex)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs.get("position")
        if position is None:
            return

        try:
            success = await self.coordinator.async_set_cover_position(self._device_id, position)
            if success:
                _LOGGER.info("Successfully set cover %s position to %s%%", self._attr_name, position)
            else:
                _LOGGER.error("Failed to set cover %s position to %s%%", self._attr_name, position)
        except Exception as ex:
            _LOGGER.error("Failed to set cover %s position to %s%%: %s", self._attr_name, position, ex)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        try:
            success = await self.coordinator.async_stop_cover(self._device_id)
            if success:
                _LOGGER.info("Successfully stopped cover %s", self._attr_name)
            else:
                _LOGGER.error("Failed to stop cover %s", self._attr_name)
        except Exception as ex:
            _LOGGER.error("Failed to stop cover %s: %s", self._attr_name, ex) 