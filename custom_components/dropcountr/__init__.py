"""The dropcountr integration."""

from __future__ import annotations

from pydropcountr import DropCountrClient
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.selector import ConfigEntrySelector

from .const import DOMAIN, PLATFORMS
from .coordinator import (
    DropCountrConfigEntry,
    DropCountrUsageDataUpdateCoordinator,
    DropCountrRuntimeData,
)

SERVICE_LIST_USAGE = "list_usage"
CONF_CONFIG_ENTRY = "config_entry"
LIST_USAGE_SERVICE_SCHEMA = vol.All(
    {
        vol.Required(CONF_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
    },
)


def _setup_entry(hass: HomeAssistant, entry: DropCountrConfigEntry) -> DropCountrClient:
    """Config entry set up in executor."""
    config = entry.data

    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    try:
        client = DropCountrClient()
        if not client.login(username, password):
            raise ConfigEntryAuthFailed("Login failed")
        return client
    except RequestException as ex:
        raise ConfigEntryNotReady from ex
    except Exception as ex:
        raise ConfigEntryAuthFailed from ex


async def async_setup_entry(hass: HomeAssistant, entry: DropCountrConfigEntry) -> bool:
    """Set up dropcountr from a config entry."""

    client = await hass.async_add_executor_job(_setup_entry, hass, entry)
    usage_coordinator = DropCountrUsageDataUpdateCoordinator(
        hass=hass, config_entry=entry, client=client
    )

    entry.runtime_data = DropCountrRuntimeData(
        client=client,
        usage_coordinator=usage_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    setup_service(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DropCountrConfigEntry) -> bool:
    """Unload a config entry."""
    entry.runtime_data.client.logout()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def setup_service(hass: HomeAssistant) -> None:
    """Add the services for the dropcountr integration."""

    @callback
    def list_usage(call: ServiceCall) -> ServiceResponse:
        """Return the usage data."""
        entry_id: str = call.data[CONF_CONFIG_ENTRY]
        entry: DropCountrConfigEntry | None = hass.config_entries.async_get_entry(
            entry_id
        )
        if not entry:
            raise ValueError(f"Invalid config entry: {entry_id}")
        if not entry.state == ConfigEntryState.LOADED:
            raise ValueError(f"Config entry not loaded: {entry_id}")
        return {
            "usage_data": entry.runtime_data.usage_coordinator.usage_data  # type: ignore[dict-item]
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_USAGE,
        list_usage,
        schema=LIST_USAGE_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
