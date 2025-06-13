"""Config flow for dropcountr integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pydropcountr import DropCountrClient
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> DropCountrClient:
    """Validate in the executor."""
    client = DropCountrClient()
    if not client.login(data[CONF_USERNAME], data[CONF_PASSWORD]):
        raise InvalidAuth("Login failed")

    # Verify we can get service connections
    service_connections = client.list_service_connections()
    if service_connections is None:
        raise CannotConnect("Failed to get service connections")

    return client


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    try:
        client = await hass.async_add_executor_job(_validate_input, hass, data)
        # Clean up the client after validation
        if hasattr(client, 'logout'):
            client.logout()
    except RequestException as err:
        raise CannotConnect from err
    except InvalidAuth:
        raise
    except Exception as err:
        _LOGGER.exception("Unexpected error during validation")
        raise UnknownError from err

    # Return info that you want to store in the config entry.
    return {"title": data[CONF_USERNAME]}


class DropCountrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for dropcountr."""

    VERSION = 1

    def __init__(self) -> None:
        """Init dropcountr config flow."""
        self._reauth_unique_id: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors[CONF_PASSWORD] = "invalid_auth"
            except UnknownError:
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth."""
        self._reauth_unique_id = self.context["unique_id"]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth input."""
        errors: dict[str, str] = {}
        existing_entry = await self.async_set_unique_id(self._reauth_unique_id)
        assert existing_entry
        if user_input is not None:
            new_data = {**existing_entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            try:
                await validate_input(self.hass, new_data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors[CONF_PASSWORD] = "invalid_auth"
            except UnknownError:
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    existing_entry, data=new_data
                )
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            description_placeholders={
                CONF_USERNAME: existing_entry.data[CONF_USERNAME]
            },
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class UnknownError(HomeAssistantError):
    """Error to indicate unknown error occurred."""
