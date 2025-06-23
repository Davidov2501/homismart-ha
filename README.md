# HomISmart Home Assistant Integration - Installation Guide

## 🔧 Fixed Issue

The integration has been updated to fix the async context manager issue with `HomismartClient`.

## 📦 Quick Installation

1. **Copy Integration Files**

   ```
   Copy the entire `custom_components/homismart/` folder to:
   /config/custom_components/homismart/
   ```

2. **Restart Home Assistant**

3. **Add Integration**
   - Go to Settings → Devices & Services
   - Click "+ Add Integration"
   - Search for "HomISmart"
   - Enter your credentials (same as mobile app)

## ✅ What to Expect

After successful setup, your devices will appear as:

### 🏠 Covers (Shutters/Blinds)

- `cover.dining_room_shutter` - With position control 0-100%
- `cover.living_room_shutter`
- `cover.kitchen_shutter`
- `cover.parents_room_shutter`
- `cover.play_room_shutter`
- `cover.kids_room_shutter`

### 💡 Lights

- `light.office_light`
- `light.kids_room_light`
- `light.parents_room_light`
- `light.play_room_light`
- `light.hall_1`
- `light.entrance`

### 🔌 Switches & Sockets

- `switch.office_socket`
- `switch.parents_room_socket`
- `switch.kids_room_socket`
- `switch.play_room_socket`
- `switch.boiler`
- Various room lights and switches

## 🔍 Troubleshooting

If you still get connection errors:

1. **Check Credentials** - Use the same email/password as your HomISmart mobile app
2. **Restart Home Assistant** - Sometimes needed after installation
3. **Check Logs** - Look for HomISmart errors in the logs
4. **Network Connection** - Ensure HA can reach the internet

## 🎉 Success!

Once working, you'll have **27 devices** automatically discovered and ready to use in automations, scenes, and the Home Assistant UI!
