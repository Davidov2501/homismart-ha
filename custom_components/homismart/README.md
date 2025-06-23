# HomISmart Home Assistant Integration

This is a custom Home Assistant integration for HomISmart smart home devices. It allows you to control and monitor your HomISmart devices directly from Home Assistant.

## Features

- **Automatic Device Discovery**: Automatically discovers all your connected HomISmart devices
- **Real-time Updates**: Receives real-time status updates via WebSocket connection
- **Multiple Device Types**: Supports covers (shutters/blinds), switches, and lights
- **Position Control**: Full position control for covers and brightness control for lights
- **Native Home Assistant Integration**: Works seamlessly with Home Assistant automations, scenes, and UI

## Supported Device Types

- **Covers**: Shutters, blinds, curtains with open/close and position control
- **Switches**: On/off devices
- **Lights**: Dimmable lights with brightness control

## Installation

### Method 1: Manual Installation

1. Copy the `custom_components/homismart` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Go to Configuration → Integrations
4. Click "+ Add Integration"
5. Search for "HomISmart" and select it
6. Enter your HomISmart username and password

### Method 2: HACS (Recommended)

1. Install HACS if you haven't already
2. Go to HACS → Integrations
3. Click "+" and search for "HomISmart"
4. Install the integration
5. Restart Home Assistant
6. Go to Configuration → Integrations
7. Click "+ Add Integration"
8. Search for "HomISmart" and select it
9. Enter your HomISmart username and password

## Configuration

The integration uses the same credentials as your HomISmart mobile app:

- **Username**: Your HomISmart account email
- **Password**: Your HomISmart account password

## Usage

Once configured, your HomISmart devices will appear in Home Assistant as:

- **Covers**: `cover.device_name` - Control shutters and blinds
- **Switches**: `switch.device_name` - Control on/off devices
- **Lights**: `light.device_name` - Control dimmable lights

### Example Automations

```yaml
# Open all shutters at sunrise
automation:
  - alias: "Open shutters at sunrise"
    trigger:
      platform: sun
      event: sunrise
    action:
      service: cover.open_cover
      target:
        entity_id: all
      data:
        entity_id:
          - cover.dining_room_shutter
          - cover.living_room_shutter

# Turn on lights when motion detected
automation:
  - alias: "Motion lights"
    trigger:
      platform: state
      entity_id: binary_sensor.motion_sensor
      to: 'on'
    action:
      service: light.turn_on
      target:
        entity_id: light.living_room_light
      data:
        brightness: 255
```

## Troubleshooting

### Connection Issues

If you're having trouble connecting:

1. Verify your credentials are correct
2. Check your internet connection
3. Ensure your HomISmart account is active
4. Check Home Assistant logs for detailed error messages

### Device Not Appearing

If devices aren't showing up:

1. Restart the integration (Configuration → Integrations → HomISmart → Restart)
2. Check that devices are online in the HomISmart mobile app
3. Verify devices are properly configured in your HomISmart account

### Logs

Enable debug logging to get more detailed information:

```yaml
logger:
  default: info
  logs:
    custom_components.homismart: debug
```

## Support

For issues and feature requests, please create an issue on the GitHub repository.

## Version History

- **1.0.0**: Initial release with support for covers, switches, and lights
