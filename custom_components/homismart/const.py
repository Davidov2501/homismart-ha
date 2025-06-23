"""Constants for the HomISmart integration."""

DOMAIN = "homismart"

# Configuration constants
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Data update interval (30 seconds - relying on real-time events for immediate updates)
UPDATE_INTERVAL = 30

# Device types
DEVICE_TYPE_COVER = "cover"
DEVICE_TYPE_SWITCH = "switch"
DEVICE_TYPE_LIGHT = "light"

# Event types
EVENT_DEVICE_UPDATED = "device_updated" 