"""DataUpdateCoordinator for HomISmart."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL, EVENT_DEVICE_UPDATED

_LOGGER = logging.getLogger(__name__)


class HomismartDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the HomISmart API."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self.client = None
        self._connect_task = None
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Update data via library."""
        try:
            if not self.client:
                await self._setup_client()
            
            # Check if we have a valid session
            if not self.client.session:
                _LOGGER.warning("HomISmart client session not available, attempting reconnection")
                await self._setup_client()
            
            devices = self.client.session.get_all_devices()
            
            # Convert devices to a list format for easier processing
            device_list = []
            for device in devices:
                device_data = {
                    "id": device.name,  # Using name as ID for now
                    "label": device.name,
                    "type": self._get_device_type(device),
                    "device": device,
                    "onLine": getattr(device, 'onLine', True),
                    "current_level": getattr(device, 'current_level', 0),
                    "target_level": getattr(device, 'target_level', 0),
                    "curtainState": getattr(device, 'curtainState', None),
                    "state": getattr(device, 'is_on', False),
                    "battery": getattr(device, 'battery', None),
                    "rssi": getattr(device, 'rssi', None),
                    "lastCommunication": getattr(device, 'lastCommunication', None),
                }
                device_list.append(device_data)
            
            return device_list
            
        except Exception as ex:
            _LOGGER.error("Error communicating with HomISmart API: %s", ex)
            raise UpdateFailed(f"Error communicating with API: {ex}") from ex

    async def _setup_client(self) -> None:
        """Set up the HomISmart client."""
        from homismart_client import HomismartClient
        
        username = self.entry.data[CONF_USERNAME]
        password = self.entry.data[CONF_PASSWORD]
        
        self.client = HomismartClient(username=username, password=password)
        
        # Connect to the client
        self._connect_task = asyncio.create_task(self.client.connect())
        
        # Wait longer for connection to establish (HomISmart needs more time)
        await asyncio.sleep(3)
        
        # Register event listener for device updates
        self.client.session.register_event_listener(
            EVENT_DEVICE_UPDATED, self._on_device_updated
        )
        
        _LOGGER.info("HomISmart client setup completed")

    def _on_device_updated(self, device) -> None:
        """Handle device update events."""
        _LOGGER.debug("Device updated: %s", device.name)
        # Trigger a fresh data fetch when a device changes
        self.hass.async_create_task(self.async_request_refresh())

    def _get_device_type(self, device) -> str:
        """Determine the device type for Home Assistant platform mapping."""
        device_name = device.name.lower()
        
        # Check for cover devices (shutters, blinds, etc.)
        if any(keyword in device_name for keyword in ["shutter", "blind", "curtain", "shade"]):
            return "shutter"
        
        # Check for light devices
        if any(keyword in device_name for keyword in ["light", "lamp", "bulb"]):
            return "light"
        
        # Check if device has level control (could be cover or light)
        if hasattr(device, 'set_level'):
            if any(keyword in device_name for keyword in ["shutter", "blind", "curtain"]):
                return "shutter"
            else:
                return "light"
        
        # Check if device supports on/off (switch)
        if hasattr(device, 'turn_on') or hasattr(device, 'supports_on_off'):
            return "switch"
        
        # Default to switch
        return "switch"

    def _get_device_by_id(self, device_id: str):
        """Get device object by ID."""
        if not self.data:
            return None
        
        for device_data in self.data:
            if device_data.get("id") == device_id:
                return device_data.get("device")
        return None



    async def async_set_cover_position(self, device_id: str, position: int) -> bool:
        """Set cover position (0=closed, 100=open in HA format)."""
        try:
            device = self._get_device_by_id(device_id)
            if not device:
                _LOGGER.error("Device %s not found", device_id)
                return False
            
            # Convert HA position (0=closed, 100=open) to HomISmart (0=open, 100=closed)
            homismart_position = 100 - position
            
            # HomISmart devices require position values rounded to nearest multiple of 10
            homismart_position_rounded = round(homismart_position / 10) * 10
            
            _LOGGER.info("Setting cover %s to position %d (HomISmart: %d, Rounded: %d)", 
                        device_id, position, homismart_position, homismart_position_rounded)
            
            if hasattr(device, 'set_level'):
                await device.set_level(homismart_position_rounded)
                return True
            else:
                _LOGGER.error("Device %s does not support position control", device_id)
                return False
                
        except Exception as ex:
            _LOGGER.error("Failed to set cover position for %s: %s", device_id, ex)
            return False

    async def async_stop_cover(self, device_id: str) -> bool:
        """Stop cover movement."""
        try:
            device = self._get_device_by_id(device_id)
            if not device:
                _LOGGER.error("Device %s not found", device_id)
                return False
            
            _LOGGER.info("Stopping cover %s", device_id)
            
            if hasattr(device, 'stop'):
                await device.stop()
                return True
            else:
                _LOGGER.warning("Device %s does not support stop command", device_id)
                return False
                
        except Exception as ex:
            _LOGGER.error("Failed to stop cover %s: %s", device_id, ex)
            return False

    async def async_turn_on_device(self, device_id: str) -> bool:
        """Turn on a device (light/switch)."""
        try:
            device = self._get_device_by_id(device_id)
            if not device:
                _LOGGER.error("Device %s not found", device_id)
                return False
            
            _LOGGER.info("Turning on device %s", device_id)
            
            if hasattr(device, 'turn_on'):
                await device.turn_on()
            elif hasattr(device, 'set_level'):
                await device.set_level(100)  # Full brightness/on
            else:
                _LOGGER.error("Device %s does not support turn_on", device_id)
                return False
            
            return True
                
        except Exception as ex:
            _LOGGER.error("Failed to turn on device %s: %s", device_id, ex)
            return False

    async def async_turn_off_device(self, device_id: str) -> bool:
        """Turn off a device (light/switch)."""
        try:
            device = self._get_device_by_id(device_id)
            if not device:
                _LOGGER.error("Device %s not found", device_id)
                return False
            
            _LOGGER.info("Turning off device %s", device_id)
            
            if hasattr(device, 'turn_off'):
                await device.turn_off()
            elif hasattr(device, 'set_level'):
                await device.set_level(0)  # Off
            else:
                _LOGGER.error("Device %s does not support turn_off", device_id)
                return False
            
            return True
                
        except Exception as ex:
            _LOGGER.error("Failed to turn off device %s: %s", device_id, ex)
            return False

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        if self._connect_task:
            self._connect_task.cancel()
            
        if self.client:
            try:
                # Try to close the client if it has a close method
                if hasattr(self.client, 'close'):
                    await self.client.close()
            except Exception as ex:
                _LOGGER.warning("Error closing HomISmart client: %s", ex)
            finally:
                self.client = None
            
        _LOGGER.info("HomISmart coordinator shutdown completed") 