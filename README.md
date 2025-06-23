# HomISmart

A smart home automation system that interfaces with the HomISmart client to control and monitor your smart home devices.

## Installation

```bash
# Install the package and its dependencies
poetry install
```

## Configuration

You can set your HomISmart credentials using either environment variables or a .env file:

### Using environment variables:

```bash
export HOMISMART_USERNAME="your_email@example.com"
export HOMISMART_PASSWORD="your_password"
```

### Using a .env file:

Create a `.env` file in the project root with the following content:

```
HOMISMART_USERNAME="your_email@example.com"
HOMISMART_PASSWORD="your_password"
```

For convenience, you can copy the provided `.env.example` file:

```bash
cp .env.example .env
```

Then edit the `.env` file with your actual credentials.

## Usage

After installation, you can run the application using:

```bash
# Using poetry
poetry run homismart

# Or directly if you have the virtual environment activated
homismart
```

## Features

- Automatically connects to the HomISmart service using your credentials
- Lists all your connected devices with their status
- Monitors device status changes in real-time
- Provides event handling for device updates

## Example Code

Here's a simple example of how to use the HomISmart client in your own scripts:

```python
import asyncio
from homismart_client import HomismartClient

async def main():
    async with HomismartClient() as client:
        await client.login()
        devices = client.session.get_all_devices()
        for device in devices:
            print(f"{device.name} ({device.device_type}): {device.online}")
            if device.supports_on_off:
                await device.turn_on()

asyncio.run(main())
```

### Event Handling Example

You can register callbacks to respond to device changes:

```python
def on_update(device):
    print(f"{device.name} updated: {device}")

client.session.register_event_listener("device_updated", on_update)
