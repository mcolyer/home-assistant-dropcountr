"""The DropCountr integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from pydropcountr import DropCountrClient, ServiceConnection, UsageResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    _LOGGER,
    DOMAIN,
    SERVICE_CONNECTION_SCAN_INTERVAL,
    USAGE_SCAN_INTERVAL,
)


@dataclass
class DropCountrRuntimeData:
    """Runtime data for the DropCountr config entry."""

    client: DropCountrClient
    usage_coordinator: DropCountrUsageDataUpdateCoordinator


type DropCountrConfigEntry = ConfigEntry[DropCountrRuntimeData]


class DropCountrServiceConnectionDataUpdateCoordinator(
    DataUpdateCoordinator[list[ServiceConnection]]
):
    """Data update coordinator for service connections."""

    config_entry: DropCountrConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: DropCountrConfigEntry,
        client: DropCountrClient,
    ) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            config_entry=config_entry,
            name=DOMAIN,
            logger=_LOGGER,
            update_interval=SERVICE_CONNECTION_SCAN_INTERVAL,
        )

        self.client = client

    async def _async_update_data(self) -> list[ServiceConnection]:
        """Get the latest service connections from DropCountr."""
        try:
            service_connections = await self.hass.async_add_executor_job(
                self.client.list_service_connections
            )
            if service_connections is None:
                raise UpdateFailed("Failed to get service connections")
            return service_connections
        except Exception as ex:
            raise UpdateFailed(f"Error communicating with DropCountr API: {ex}") from ex


class DropCountrUsageDataUpdateCoordinator(
    DataUpdateCoordinator[dict[int, UsageResponse]]
):
    """Data update coordinator for usage data from all service connections."""

    config_entry: DropCountrConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: DropCountrConfigEntry,
        client: DropCountrClient,
    ) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            config_entry=config_entry,
            name=DOMAIN,
            logger=_LOGGER,
            update_interval=USAGE_SCAN_INTERVAL,
        )

        self.client = client
        self.usage_data: dict[int, UsageResponse] = {}

    def _get_usage_for_service(
        self, service_connection_id: int
    ) -> UsageResponse | None:
        """Get usage data for a specific service connection."""
        try:
            # Get usage from the start of current month to ensure monthly totals are accurate
            end_date = datetime.now()
            # Start from the beginning of the current month, or 45 days ago, whichever is earlier
            # This ensures we get full month data plus some history for weekly totals
            month_start = datetime(end_date.year, end_date.month, 1)
            start_date = min(month_start, end_date - timedelta(days=45))

            _LOGGER.debug(
                f"Requesting usage data for service {service_connection_id} from {start_date.date()} to {end_date.date()}"
            )

            return self.client.get_usage(
                service_connection_id=service_connection_id,
                start_date=start_date,
                end_date=end_date,
                period="day",
            )
        except Exception as ex:
            _LOGGER.error(
                f"Error getting usage for service {service_connection_id}: {ex}"
            )
            return None

    async def _async_update_data(self) -> dict[int, UsageResponse]:
        """Update usage data for all service connections."""
        try:
            # First get all service connections
            service_connections = await self.hass.async_add_executor_job(
                self.client.list_service_connections
            )
            if not service_connections:
                return {}

            usage_data = {}
            for service_connection in service_connections:
                usage_response = await self.hass.async_add_executor_job(
                    self._get_usage_for_service, service_connection.id
                )
                if usage_response:
                    usage_data[service_connection.id] = usage_response

            self.usage_data = usage_data
            return usage_data
        except Exception as ex:
            raise UpdateFailed(f"Error communicating with DropCountr API: {ex}") from ex
