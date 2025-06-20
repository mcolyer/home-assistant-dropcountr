"""The dropcountr integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import time

from pydropcountr import DropCountrClient
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.selector import ConfigEntrySelector

from .const import _LOGGER, DOMAIN, PLATFORMS
from .coordinator import (
    DropCountrConfigEntry,
    DropCountrRuntimeData,
    DropCountrUsageDataUpdateCoordinator,
)

SERVICE_LIST_USAGE = "list_usage"
SERVICE_GET_SERVICE_CONNECTION = "get_service_connection"
SERVICE_GET_HOURLY_USAGE = "get_hourly_usage"

CONF_CONFIG_ENTRY = "config_entry"
CONF_SERVICE_CONNECTION_ID = "service_connection_id"
CONF_START_DATE = "start_date"
CONF_END_DATE = "end_date"

LIST_USAGE_SERVICE_SCHEMA = vol.All(
    {
        vol.Required(CONF_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
    },
)

GET_SERVICE_CONNECTION_SCHEMA = vol.All(
    {
        vol.Required(CONF_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Required(CONF_SERVICE_CONNECTION_ID): int,
    },
)

GET_HOURLY_USAGE_SCHEMA = vol.All(
    {
        vol.Required(CONF_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Required(CONF_SERVICE_CONNECTION_ID): int,
        vol.Optional(CONF_START_DATE): str,
        vol.Optional(CONF_END_DATE): str,
    },
)


def _raise_auth_failed(message: str) -> None:
    """Raise authentication failed exception."""
    raise ConfigEntryAuthFailed(message)


def _setup_entry(hass: HomeAssistant, entry: DropCountrConfigEntry) -> DropCountrClient:
    """Config entry set up in executor."""
    config = entry.data

    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    try:
        client = DropCountrClient()
        if not client.login(username, password):
            _raise_auth_failed("Login failed")
        elif not client.is_logged_in():
            # Verify authentication status
            _raise_auth_failed("Authentication verification failed")
        else:
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

    async def get_service_connection(call: ServiceCall) -> ServiceResponse:
        """Return details for a specific service connection."""
        start_time = time.time()
        entry_id: str = call.data[CONF_CONFIG_ENTRY]
        service_connection_id: int = call.data[CONF_SERVICE_CONNECTION_ID]

        _LOGGER.debug(
            f"Service call: get_service_connection for service {service_connection_id}"
        )

        entry: DropCountrConfigEntry | None = hass.config_entries.async_get_entry(
            entry_id
        )
        if not entry:
            raise ValueError(f"Invalid config entry: {entry_id}")
        if not entry.state == ConfigEntryState.LOADED:
            raise ValueError(f"Config entry not loaded: {entry_id}")

        try:
            service_connection = await hass.async_add_executor_job(
                entry.runtime_data.client.get_service_connection, service_connection_id
            )
            elapsed = time.time() - start_time
            _LOGGER.debug(
                f"Service get_service_connection completed in {elapsed:.2f}s (service {service_connection_id})"
            )
            return {
                "service_connection": service_connection.model_dump()
                if service_connection
                else None
            }
        except Exception as ex:
            elapsed = time.time() - start_time
            _LOGGER.error(
                f"Service get_service_connection failed after {elapsed:.2f}s: {ex}"
            )
            raise ValueError(
                f"Error getting service connection {service_connection_id}: {ex}"
            ) from ex

    async def get_hourly_usage(call: ServiceCall) -> ServiceResponse:
        """Return hourly usage data for a specific service connection."""
        start_time = time.time()

        entry_id: str = call.data[CONF_CONFIG_ENTRY]
        service_connection_id: int = call.data[CONF_SERVICE_CONNECTION_ID]
        start_date = call.data.get(CONF_START_DATE)
        end_date = call.data.get(CONF_END_DATE)

        _LOGGER.debug(
            f"Service call: get_hourly_usage for service {service_connection_id} (date range: {start_date or 'last 24h'} to {end_date or 'now'})"
        )

        entry: DropCountrConfigEntry | None = hass.config_entries.async_get_entry(
            entry_id
        )
        if not entry:
            raise ValueError(f"Invalid config entry: {entry_id}")
        if not entry.state == ConfigEntryState.LOADED:
            raise ValueError(f"Config entry not loaded: {entry_id}")

        # Default to last 24 hours if no dates provided
        if not start_date or not end_date:
            end_dt = datetime.now(UTC)
            start_dt = end_dt - timedelta(days=1)
        else:
            try:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            except ValueError as ex:
                raise ValueError(f"Invalid date format. Use ISO format: {ex}") from ex

        try:
            usage_response = await hass.async_add_executor_job(
                entry.runtime_data.client.get_usage,
                service_connection_id,
                start_dt,
                end_dt,
                "hour",  # Use hourly granularity
            )
            elapsed = time.time() - start_time
            data_count = (
                len(usage_response.usage_data)
                if usage_response and usage_response.usage_data
                else 0
            )
            _LOGGER.info(
                f"Service get_hourly_usage: service {service_connection_id} returned {data_count} hourly records in {elapsed:.2f}s"
            )
            return {
                "usage_data": usage_response.model_dump() if usage_response else None,
                "start_date": start_dt.isoformat(),
                "end_date": end_dt.isoformat(),
                "granularity": "hour",
            }
        except Exception as ex:
            elapsed = time.time() - start_time
            _LOGGER.error(f"Service get_hourly_usage failed after {elapsed:.2f}s: {ex}")
            raise ValueError(
                f"Error getting hourly usage for service {service_connection_id}: {ex}"
            ) from ex

    # Register all services
    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_USAGE,
        list_usage,
        schema=LIST_USAGE_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_SERVICE_CONNECTION,
        get_service_connection,
        schema=GET_SERVICE_CONNECTION_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_HOURLY_USAGE,
        get_hourly_usage,
        schema=GET_HOURLY_USAGE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
