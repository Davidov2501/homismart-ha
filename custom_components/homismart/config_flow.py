"""Config flow for HomISmart integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HomISmart."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self._test_credentials(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="HomISmart", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def _test_credentials(self, username: str, password: str) -> None:
        """Validate the user input allows us to connect."""
        from homismart_client import HomismartClient

        client = None
        connect_task = None
        
        try:
            # Create client instance
            client = HomismartClient(username=username, password=password)
            
            # Create connection task and wait for it to complete
            connect_task = asyncio.create_task(client.connect())
            
            # Wait longer for connection to establish (HomISmart needs more time)
            await asyncio.sleep(5)
            
            # Try to get devices to validate connection
            devices = client.session.get_all_devices()
            _LOGGER.info("Successfully connected to HomISmart with %d devices", len(devices))
                    
        except Exception as ex:
            _LOGGER.error("Failed to connect to HomISmart: %s", ex)
            error_str = str(ex).lower()
            if any(keyword in error_str for keyword in ["auth", "login", "credential", "password", "username"]):
                raise InvalidAuth from ex
            elif any(keyword in error_str for keyword in ["connection", "network", "timeout", "websocket"]):
                raise CannotConnect from ex
            else:
                # Log the full error for debugging
                import traceback
                _LOGGER.error("Full error details: %s", traceback.format_exc())
                raise CannotConnect from ex
        finally:
            # Clean up resources
            if connect_task and not connect_task.done():
                connect_task.cancel()
            if client and hasattr(client, 'close'):
                try:
                    await client.close()
                except Exception:
                    pass  # Ignore cleanup errors


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth.""" 