"""The DropCountr integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pydropcountr import DropCountrClient, ServiceConnection, UsageData, UsageResponse

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
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

    def _raise_update_failed(self, message: str) -> None:
        """Raise update failed exception."""
        raise UpdateFailed(message)

    async def _async_update_data(self) -> list[ServiceConnection]:
        """Get the latest service connections from DropCountr."""
        try:
            service_connections = await self.hass.async_add_executor_job(
                self.client.list_service_connections
            )
            if service_connections is None:
                self._raise_update_failed("Failed to get service connections")
            else:
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
                _LOGGER.info(
                    f"Detected new historical data for service {service_connection_id}: "
                    f"{usage_date} ({(current_date - usage_date).days} days old), "
                    f"total_gallons={usage_data.total_gallons}"
                )
            elif is_new_data:
                _LOGGER.debug(
                    f"Detected new recent data (not historical) for service {service_connection_id}: "
                    f"{usage_date} ({(current_date - usage_date).days} days old)"
                )

        return new_historical_data

    async def _insert_historical_statistics(
        self, service_connection_id: int, historical_data: list[UsageData]
    ) -> None:
        """Insert historical usage data as external statistics."""
        if not historical_data:
            _LOGGER.debug("No historical data to insert")
            return

        # Check if recorder is available
        try:
            recorder_instance = get_instance(self.hass)
            if not recorder_instance:
                _LOGGER.warning(
                    "Recorder instance not available, skipping statistics insertion"
                )
                return
        except Exception as ex:
            _LOGGER.warning(
                f"Recorder not available: {ex}, skipping statistics insertion"
            )
            return

        # Get service connection for naming
        try:
            service_connections = await self.hass.async_add_executor_job(
                self.client.list_service_connections
            )
            service_connection = next(
                (sc for sc in service_connections if sc.id == service_connection_id),
                None,
            )
            if not service_connection:
                _LOGGER.error(f"Service connection {service_connection_id} not found")
                return
        except Exception as ex:
            _LOGGER.error(f"Error getting service connection for statistics: {ex}")
            return

        _LOGGER.info(
            f"Starting statistics insertion for {len(historical_data)} historical data points"
        )

        # Create statistic IDs and metadata
        id_prefix = f"dropcountr_{service_connection_id}"
        statistics_config = {
            "total_gallons": {
                "id": f"{DOMAIN}:{id_prefix}_total_gallons",
                "name": f"DropCountr {service_connection.name} Total Water Usage",
                "unit": UnitOfVolume.GALLONS,
            },
            "irrigation_gallons": {
                "id": f"{DOMAIN}:{id_prefix}_irrigation_gallons",
                "name": f"DropCountr {service_connection.name} Irrigation Water Usage",
                "unit": UnitOfVolume.GALLONS,
            },
            "irrigation_events": {
                "id": f"{DOMAIN}:{id_prefix}_irrigation_events",
                "name": f"DropCountr {service_connection.name} Irrigation Events",
                "unit": None,
            },
        }

        # Process each metric type
        for metric_type, config in statistics_config.items():
            statistic_id = config["id"]

            # Get the last existing statistic to determine starting point for sums
            try:
                last_stat = await get_instance(self.hass).async_add_executor_job(
                    get_last_statistics, self.hass, 1, statistic_id, True, set()
                )
                _LOGGER.debug(
                    f"Retrieved last statistics for {statistic_id}: {bool(last_stat)}"
                )
            except Exception as ex:
                _LOGGER.error(f"Failed to get last statistics for {statistic_id}: {ex}")
                last_stat = {}

            if last_stat:
                # Continue from where we left off
                existing_sum = last_stat[statistic_id][0].get("sum", 0.0)
                last_time = last_stat[statistic_id][0]["start"]

                # Convert last_time to datetime for easier comparison
                from datetime import datetime

                if isinstance(last_time, (int, float)):
                    last_time_dt = datetime.fromtimestamp(last_time, tz=UTC)
                else:
                    last_time_dt = last_time
                    # Ensure it has timezone info
                    if last_time_dt.tzinfo is None:
                        last_time_dt = last_time_dt.replace(tzinfo=UTC)

                _LOGGER.debug(
                    f"Continuing {metric_type} statistics from {last_time_dt}, sum={existing_sum}"
                )

                # Check if the last processed time is in the future (indicating corrupted data)
                oldest_historical_date = min(
                    usage_data.start_date for usage_data in historical_data
                )
                # Ensure both datetimes have timezone info for comparison
                if oldest_historical_date.tzinfo is None:
                    oldest_historical_date = oldest_historical_date.replace(tzinfo=UTC)

                if last_time_dt > oldest_historical_date:
                    _LOGGER.warning(
                        f"Last processed time ({last_time_dt}) is newer than historical data ({oldest_historical_date}). "
                        f"This may indicate corrupted statistics. Resetting to process historical data."
                    )
                    # Reset to allow historical data processing
                    existing_sum = 0.0
                    last_time = 0
            else:
                # Starting fresh
                existing_sum = 0.0
                last_time = 0
                _LOGGER.debug(f"Starting {metric_type} statistics from scratch")

            # Create metadata
            metadata = StatisticMetaData(
                mean_type=StatisticMeanType.NONE,
                has_sum=True,
                name=config["name"],
                source=DOMAIN,
                statistic_id=statistic_id,
                unit_of_measurement=config["unit"],
            )

            # Create statistics data
            statistics = []
            current_sum = existing_sum

            for usage_data in historical_data:
                # Skip data that's already been processed
                if usage_data.start_date.timestamp() <= last_time:
                    _LOGGER.debug(
                        f"Skipping already processed data for {metric_type}: {usage_data.start_date}"
                    )
                    continue

                # Get the appropriate value for this metric
                if metric_type == "total_gallons":
                    value = usage_data.total_gallons
                elif metric_type == "irrigation_gallons":
                    value = usage_data.irrigation_gallons
                elif metric_type == "irrigation_events":
                    value = usage_data.irrigation_events
                else:
                    continue

                current_sum += value

                _LOGGER.debug(
                    f"Creating {metric_type} statistic: date={usage_data.start_date}, value={value}, sum={current_sum}"
                )

                statistics.append(
                    StatisticData(
                        start=usage_data.start_date,
                        state=value,
                        sum=current_sum,
                    )
                )

            if statistics:
                try:
                    _LOGGER.info(
                        f"Inserting {len(statistics)} {metric_type} statistics for service {service_connection_id}"
                    )
                    async_add_external_statistics(self.hass, metadata, statistics)
                    _LOGGER.info(f"Successfully inserted {metric_type} statistics")
                except Exception as ex:
                    _LOGGER.error(
                        f"Failed to insert {metric_type} statistics: {ex}",
                        exc_info=True,
                    )
                    raise
            else:
                _LOGGER.debug(f"No new {metric_type} statistics to add")

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
                        try:
                            await self._insert_historical_statistics(
                                service_connection.id, historical_data
                            )
                            _LOGGER.info(
                                f"Successfully inserted {len(historical_data)} historical statistics for service {service_connection.id}"
                            )
                        except Exception as ex:
                            _LOGGER.error(
                                f"Failed to insert historical statistics: {ex}. Continuing with normal operation.",
                                exc_info=True,
                            )

                    # Update historical state tracking
                    self._update_historical_state(service_connection.id, usage_response)

                    usage_data[service_connection.id] = usage_response

            self.usage_data = usage_data
        except Exception as ex:
            raise UpdateFailed(f"Error communicating with DropCountr API: {ex}") from ex
        else:
            return usage_data
