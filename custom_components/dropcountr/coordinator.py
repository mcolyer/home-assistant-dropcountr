"""The DropCountr integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from pydropcountr import DropCountrClient, ServiceConnection, UsageData, UsageResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    _LOGGER,
    DOMAIN,
    LAST_SEEN_DATES_KEY,
    LAST_UPDATE_KEY,
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
        self._historical_state: dict[int, dict[str, Any]] = {}

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

    def _get_historical_state(self, service_connection_id: int) -> dict[str, Any]:
        """Get historical state for a service connection."""
        if service_connection_id not in self._historical_state:
            self._historical_state[service_connection_id] = {
                LAST_SEEN_DATES_KEY: set(),
                LAST_UPDATE_KEY: None,
            }
        return self._historical_state[service_connection_id]

    def _detect_new_historical_data(
        self, service_connection_id: int, usage_response: UsageResponse
    ) -> list[UsageData]:
        """Detect newly arrived historical data."""
        if not usage_response or not usage_response.usage_data:
            return []

        historical_state = self._get_historical_state(service_connection_id)
        last_seen_dates = historical_state[LAST_SEEN_DATES_KEY]

        new_historical_data = []
        current_date = datetime.now().date()

        for usage_data in usage_response.usage_data:
            # Convert start_date to date for comparison
            usage_date = usage_data.start_date.date()

            # Check if this is new data and if it's more than 1 day old (historical)
            is_new_data = usage_date not in last_seen_dates
            is_historical = (current_date - usage_date).days > 1

            if is_new_data and is_historical:
                new_historical_data.append(usage_data)
                _LOGGER.debug(
                    f"Detected new historical data for service {service_connection_id}: "
                    f"{usage_date} ({(current_date - usage_date).days} days old)"
                )

        return new_historical_data

    async def _fire_historical_state_events(
        self, service_connection_id: int, historical_data: list[UsageData]
    ) -> None:
        """Fire state_changed events for historical data with original timestamps."""
        if not historical_data:
            return

        # Get service connection name for entity naming
        try:
            service_connections = await self.hass.async_add_executor_job(
                self.client.list_service_connections
            )
            service_connection = next(
                (sc for sc in service_connections if sc.id == service_connection_id),
                None,
            )
            if not service_connection:
                return
        except Exception as ex:
            _LOGGER.error(
                f"Error getting service connection for historical events: {ex}"
            )
            return

        # Fire events for each sensor type
        sensor_types = [
            "irrigation_gallons",
            "irrigation_events",
            "daily_total",
            "weekly_total",
            "monthly_total",
        ]

        for usage_data in historical_data:
            # Calculate the timestamp for this historical data (end of day)
            historical_timestamp = usage_data.end_date.isoformat()

            for sensor_type in sensor_types:
                # Calculate the appropriate value for this sensor type
                if sensor_type == "irrigation_gallons":
                    value = usage_data.irrigation_gallons
                elif sensor_type == "irrigation_events":
                    value = usage_data.irrigation_events
                elif sensor_type == "daily_total":
                    value = usage_data.total_gallons
                elif sensor_type in ["weekly_total", "monthly_total"]:
                    # For aggregated totals, we'll let the normal sensor logic handle these
                    continue
                else:
                    continue

                # Create entity_id - this matches the pattern used in sensor.py
                entity_id = f"sensor.{service_connection.name.lower().replace(' ', '_')}_{sensor_type}"

                # Fire the state_changed event with historical timestamp
                self.hass.bus.async_fire(
                    "state_changed",
                    {
                        "entity_id": entity_id,
                        "new_state": {
                            "entity_id": entity_id,
                            "state": str(value),
                            "last_updated": historical_timestamp,
                            "attributes": {
                                "service_connection_id": service_connection_id,
                                "service_connection_name": service_connection.name,
                                "service_connection_address": service_connection.address,
                                "period_start": usage_data.start_date.isoformat(),
                                "period_end": usage_data.end_date.isoformat(),
                                "is_leaking": usage_data.is_leaking,
                                "historical_data": True,
                            },
                        },
                    },
                )

                _LOGGER.debug(
                    f"Fired historical state event for {entity_id}: "
                    f"value={value}, timestamp={historical_timestamp}"
                )

    def _update_historical_state(
        self, service_connection_id: int, usage_response: UsageResponse
    ) -> None:
        """Update the historical state tracking."""
        if not usage_response or not usage_response.usage_data:
            return

        historical_state = self._get_historical_state(service_connection_id)

        # Add all current dates to the seen set
        for usage_data in usage_response.usage_data:
            usage_date = usage_data.start_date.date()
            historical_state[LAST_SEEN_DATES_KEY].add(usage_date)

        # Update the last update timestamp
        historical_state[LAST_UPDATE_KEY] = datetime.now()

        # Clean up old dates (keep only last 60 days to prevent memory growth)
        cutoff_date = datetime.now().date() - timedelta(days=60)
        historical_state[LAST_SEEN_DATES_KEY] = {
            date for date in historical_state[LAST_SEEN_DATES_KEY] if date > cutoff_date
        }

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
                    # Detect and process historical data
                    historical_data = self._detect_new_historical_data(
                        service_connection.id, usage_response
                    )
                    if historical_data:
                        await self._fire_historical_state_events(
                            service_connection.id, historical_data
                        )

                    # Update historical state tracking
                    self._update_historical_state(service_connection.id, usage_response)

                    usage_data[service_connection.id] = usage_response

            self.usage_data = usage_data
            return usage_data
        except Exception as ex:
            raise UpdateFailed(f"Error communicating with DropCountr API: {ex}") from ex
