"""The HomISmart integration."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import DOMAIN
from .coordinator import HomismartDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.COVER, Platform.SWITCH, Platform.LIGHT, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

# Service schemas
SERVICE_CONTROL_GROUP = vol.Schema({
    vol.Required("device_ids"): cv.ensure_list,
    vol.Required("action"): vol.In(["open", "close", "stop", "set_position", "turn_on", "turn_off"]),
    vol.Optional("position"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
})

SERVICE_ROOM_FILTER = vol.Schema({
    vol.Optional("room"): cv.string,
})

SERVICE_SET_POSITION = vol.Schema({
    vol.Required("position"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    vol.Optional("room"): cv.string,
})

SERVICE_CREATE_SCENE = vol.Schema({
    vol.Required("scene_name"): cv.string,
    vol.Optional("include_covers", default=True): cv.boolean,
    vol.Optional("include_lights", default=True): cv.boolean,
    vol.Optional("room_filter"): cv.string,
})

SERVICE_ACTIVATE_SCENE = vol.Schema({
    vol.Required("scene_name"): cv.string,
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HomISmart from a config entry."""
    
    _LOGGER.info("🏠 HomISmart integration starting setup...")
    _LOGGER.debug("Entry data: %s", entry.data)
    
    # Create the data update coordinator
    coordinator = HomismartDataUpdateCoordinator(hass, entry)
    
    # Test connection and fetch initial data
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as ex:
        _LOGGER.error("Unable to connect to HomISmart: %s", ex)
        raise ConfigEntryNotReady from ex

    # Store the coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward the setup to the platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    await _register_services(hass, coordinator)
    
    _LOGGER.info("✅ HomISmart integration setup completed successfully!")
    _LOGGER.info("📊 Found %d devices total", len(coordinator.data) if coordinator.data else 0)

    return True


async def _register_services(hass: HomeAssistant, coordinator: HomismartDataUpdateCoordinator) -> None:
    """Register HomISmart services."""
    
    async def handle_control_group(call: ServiceCall) -> None:
        """Handle control group service call."""
        device_ids = call.data["device_ids"]
        action = call.data["action"]
        position = call.data.get("position")
        
        _LOGGER.info("🎮 Group control: %s for devices %s", action, device_ids)
        
        success_count = 0
        for device_id in device_ids:
            try:
                success = await _perform_device_action(coordinator, device_id, action, position)
                if success:
                    success_count += 1
            except Exception as ex:
                _LOGGER.error("Failed to control device %s: %s", device_id, ex)
        
        _LOGGER.info("✅ Group control completed: %d/%d devices successful", success_count, len(device_ids))

    async def handle_bulk_cover_action(call: ServiceCall) -> None:
        """Handle bulk cover actions (open/close/stop all)."""
        action = call.service  # Service name becomes the action
        room_filter = call.data.get("room")
        position = call.data.get("position")
        
        # Get all cover devices
        covers = [device for device in coordinator.data if device.get("type") in ["shutter", "cover", "curtain"]]
        
        # Apply room filter if specified
        if room_filter:
            covers = [device for device in covers if room_filter.lower() in device.get("label", "").lower()]
        
        _LOGGER.info("🏠 Bulk %s: %d covers%s", action, len(covers), f" in {room_filter}" if room_filter else "")
        
        success_count = 0
        for device in covers:
            try:
                device_id = device.get("id")
                success = await _perform_device_action(coordinator, device_id, action.replace("_all_covers", "").replace("covers_", ""), position)
                if success:
                    success_count += 1
            except Exception as ex:
                _LOGGER.error("Failed to control cover %s: %s", device.get("label"), ex)
        
        _LOGGER.info("✅ Bulk cover action completed: %d/%d covers successful", success_count, len(covers))

    async def handle_bulk_light_action(call: ServiceCall) -> None:
        """Handle bulk light actions (turn on/off all)."""
        action = "turn_on" if "on" in call.service else "turn_off"
        room_filter = call.data.get("room")
        
        # Get all light devices
        lights = [device for device in coordinator.data if device.get("type") in ["light", "dimmer", "switch"]]
        
        # Apply room filter if specified
        if room_filter:
            lights = [device for device in lights if room_filter.lower() in device.get("label", "").lower()]
        
        _LOGGER.info("💡 Bulk %s: %d lights%s", action, len(lights), f" in {room_filter}" if room_filter else "")
        
        success_count = 0
        for device in lights:
            try:
                device_id = device.get("id")
                success = await _perform_device_action(coordinator, device_id, action)
                if success:
                    success_count += 1
            except Exception as ex:
                _LOGGER.error("Failed to control light %s: %s", device.get("label"), ex)
        
        _LOGGER.info("✅ Bulk light action completed: %d/%d lights successful", success_count, len(lights))

    async def handle_create_scene(call: ServiceCall) -> None:
        """Handle create scene service call."""
        scene_name = call.data["scene_name"]
        include_covers = call.data["include_covers"]
        include_lights = call.data["include_lights"]
        room_filter = call.data.get("room_filter")
        
        scene_data = await _create_scene_from_current_state(
            coordinator, scene_name, include_covers, include_lights, room_filter
        )
        
        # Save scene to file
        scenes_file = hass.config.path(f"custom_components/{DOMAIN}/scenes.json")
        await _save_scene(scenes_file, scene_name, scene_data)
        
        _LOGGER.info("🎬 Scene '%s' created with %d devices", scene_name, len(scene_data.get("devices", [])))

    async def handle_activate_scene(call: ServiceCall) -> None:
        """Handle activate scene service call."""
        scene_name = call.data["scene_name"]
        
        # Load scene from file
        scenes_file = hass.config.path(f"custom_components/{DOMAIN}/scenes.json")
        scene_data = await _load_scene(scenes_file, scene_name)
        
        if not scene_data:
            raise ServiceValidationError(f"Scene '{scene_name}' not found")
        
        success_count = await _apply_scene(coordinator, scene_data)
        total_devices = len(scene_data.get("devices", []))
        
        _LOGGER.info("🎬 Scene '%s' activated: %d/%d devices successful", scene_name, success_count, total_devices)

    # Register all services
    hass.services.async_register(DOMAIN, "control_group", handle_control_group, schema=SERVICE_CONTROL_GROUP)
    hass.services.async_register(DOMAIN, "open_all_covers", handle_bulk_cover_action, schema=SERVICE_ROOM_FILTER)
    hass.services.async_register(DOMAIN, "close_all_covers", handle_bulk_cover_action, schema=SERVICE_ROOM_FILTER)
    hass.services.async_register(DOMAIN, "stop_all_covers", handle_bulk_cover_action, schema=SERVICE_ROOM_FILTER)
    hass.services.async_register(DOMAIN, "set_covers_position", handle_bulk_cover_action, schema=SERVICE_SET_POSITION)
    hass.services.async_register(DOMAIN, "turn_on_all_lights", handle_bulk_light_action, schema=SERVICE_ROOM_FILTER)
    hass.services.async_register(DOMAIN, "turn_off_all_lights", handle_bulk_light_action, schema=SERVICE_ROOM_FILTER)
    hass.services.async_register(DOMAIN, "create_scene", handle_create_scene, schema=SERVICE_CREATE_SCENE)
    hass.services.async_register(DOMAIN, "activate_scene", handle_activate_scene, schema=SERVICE_ACTIVATE_SCENE)
    
    _LOGGER.info("🛠️ HomISmart services registered successfully")


async def _perform_device_action(coordinator: HomismartDataUpdateCoordinator, device_id: str, action: str, position: int = None) -> bool:
    """Perform an action on a device."""
    try:
        if action == "open":
            return await coordinator.async_set_cover_position(device_id, 100)  # HA: 100=open
        elif action == "close":
            return await coordinator.async_set_cover_position(device_id, 0)    # HA: 0=closed
        elif action == "stop":
            return await coordinator.async_stop_cover(device_id)
        elif action == "set_position" and position is not None:
            return await coordinator.async_set_cover_position(device_id, position)
        elif action == "turn_on":
            return await coordinator.async_turn_on_device(device_id)
        elif action == "turn_off":
            return await coordinator.async_turn_off_device(device_id)
        else:
            _LOGGER.error("Unknown action: %s", action)
            return False
    except Exception as ex:
        _LOGGER.error("Action %s failed for device %s: %s", action, device_id, ex)
        return False


async def _create_scene_from_current_state(
    coordinator: HomismartDataUpdateCoordinator, 
    scene_name: str, 
    include_covers: bool, 
    include_lights: bool, 
    room_filter: str = None
) -> dict[str, Any]:
    """Create a scene from current device states."""
    devices = []
    
    for device in coordinator.data:
        device_type = device.get("type", "")
        device_label = device.get("label", "")
        
        # Apply room filter
        if room_filter and room_filter.lower() not in device_label.lower():
            continue
        
        device_data = {
            "id": device.get("id"),
            "label": device_label,
            "type": device_type,
        }
        
        # Include covers
        if include_covers and device_type in ["shutter", "cover", "curtain"]:
            # Store HA position (0=closed, 100=open)
            raw_position = device.get("current_level", 0)
            ha_position = 100 - raw_position  # Convert to HA format
            device_data["position"] = ha_position
            devices.append(device_data)
        
        # Include lights/switches
        elif include_lights and device_type in ["light", "dimmer", "switch"]:
            device_data["state"] = device.get("state", False)
            if device_type == "dimmer":
                device_data["brightness"] = device.get("brightness", 0)
            devices.append(device_data)
    
            from datetime import datetime
        return {
            "name": scene_name,
            "created": datetime.now().isoformat(),
            "devices": devices,
        }


async def _save_scene(scenes_file: str, scene_name: str, scene_data: dict[str, Any]) -> None:
    """Save a scene to the scenes file."""
    scenes = {}
    
    # Load existing scenes
    if os.path.exists(scenes_file):
        try:
            with open(scenes_file, "r") as f:
                scenes = json.load(f)
        except Exception as ex:
            _LOGGER.error("Failed to load existing scenes: %s", ex)
    
    # Add new scene
    scenes[scene_name] = scene_data
    
    # Save scenes
    os.makedirs(os.path.dirname(scenes_file), exist_ok=True)
    with open(scenes_file, "w") as f:
        json.dump(scenes, f, indent=2)


async def _load_scene(scenes_file: str, scene_name: str) -> dict[str, Any] | None:
    """Load a scene from the scenes file."""
    if not os.path.exists(scenes_file):
        return None
    
    try:
        with open(scenes_file, "r") as f:
            scenes = json.load(f)
        return scenes.get(scene_name)
    except Exception as ex:
        _LOGGER.error("Failed to load scene %s: %s", scene_name, ex)
        return None


async def _apply_scene(coordinator: HomismartDataUpdateCoordinator, scene_data: dict[str, Any]) -> int:
    """Apply a scene to devices."""
    success_count = 0
    
    for device_config in scene_data.get("devices", []):
        device_id = device_config.get("id")
        device_type = device_config.get("type")
        
        try:
            if device_type in ["shutter", "cover", "curtain"]:
                position = device_config.get("position", 0)
                success = await coordinator.async_set_cover_position(device_id, position)
                if success:
                    success_count += 1
            
            elif device_type in ["light", "dimmer", "switch"]:
                state = device_config.get("state", False)
                if state:
                    success = await coordinator.async_turn_on_device(device_id)
                    if success and device_type == "dimmer":
                        brightness = device_config.get("brightness", 100)
                        # TODO: Implement brightness control
                else:
                    success = await coordinator.async_turn_off_device(device_id)
                
                if success:
                    success_count += 1
        
        except Exception as ex:
            _LOGGER.error("Failed to apply scene to device %s: %s", device_config.get("label"), ex)
    
    return success_count


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unregister services
    for service in [
        "control_group", "open_all_covers", "close_all_covers", "stop_all_covers",
        "set_covers_position", "turn_on_all_lights", "turn_off_all_lights", 
        "create_scene", "activate_scene"
    ]:
        hass.services.async_remove(DOMAIN, service)
    
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: HomismartDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_shutdown()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok 