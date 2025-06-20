"""The DropCountr integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import time
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
from homeassistant.util import dt as dt_util

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
        start_time = time.time()
        try:
            service_connections = await self.hass.async_add_executor_job(
                self.client.list_service_connections
            )
            elapsed = time.time() - start_time
            if service_connections is None:
                _LOGGER.warning(
                    f"API call to list_service_connections failed (took {elapsed:.2f}s)"
                )
                self._raise_update_failed("Failed to get service connections")
            else:
                _LOGGER.debug(
                    f"Retrieved {len(service_connections)} service connections in {elapsed:.2f}s"
                )
                return service_connections
        except Exception as ex:
            elapsed = time.time() - start_time
            _LOGGER.error(
                f"API call to list_service_connections failed after {elapsed:.2f}s: {ex}"
            )
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
        start_time = time.time()
        try:
            # Get usage from the start of current month to ensure monthly totals are accurate
            end_date = datetime.now(UTC)
            # Start from the beginning of the current month, or 45 days ago, whichever is earlier
            # This ensures we get full month data plus some history for weekly totals
            month_start = datetime(end_date.year, end_date.month, 1, tzinfo=UTC)
            start_date = min(month_start, end_date - timedelta(days=45))

            _LOGGER.debug(
                f"Fetching usage data for service {service_connection_id} ({(end_date - start_date).days} days)"
            )

            result = self.client.get_usage(
                service_connection_id=service_connection_id,
                start_date=start_date,
                end_date=end_date,
                period="day",
            )

            elapsed = time.time() - start_time
            if result and result.usage_data:
                _LOGGER.debug(
                    f"API fetch: service {service_connection_id} returned {len(result.usage_data)} usage records in {elapsed:.2f}s"
                )
                return result
            else:
                _LOGGER.warning(
                    f"API fetch: service {service_connection_id} returned no data (took {elapsed:.2f}s)"
                )
                return result
        except Exception as ex:
            elapsed = time.time() - start_time
            _LOGGER.error(
                f"Error getting usage for service {service_connection_id} after {elapsed:.2f}s: {ex}"
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

            # Check if this is new data and if it's historical
            is_new_data = usage_date not in last_seen_dates
            days_old = (current_date - usage_date).days

            # Consider data historical if:
            # - It's more than 1 day old, OR
            # - It's exactly 1 day old (yesterday) and has non-zero total gallons
            is_historical = days_old > 1 or (
                days_old == 1 and usage_data.total_gallons > 0
            )

            if is_new_data and is_historical:
                new_historical_data.append(usage_data)

        if new_historical_data:
            _LOGGER.info(
                f"Found {len(new_historical_data)} new historical data points for service {service_connection_id} "
                f"(dates: {[data.start_date.date() for data in new_historical_data]})"
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
            f"Inserting statistics for {len(historical_data)} historical data points (service {service_connection_id})"
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
            except Exception as ex:
                _LOGGER.error(f"Failed to get last statistics for {statistic_id}: {ex}")
                last_stat = {}

            if last_stat:
                # Continue from where we left off
                existing_sum = last_stat[statistic_id][0].get("sum", 0.0)
                last_time = last_stat[statistic_id][0]["start"]

                # Convert last_time to datetime for easier comparison
                if isinstance(last_time, (int, float)):
                    last_time_dt = datetime.fromtimestamp(last_time, tz=UTC)
                else:
                    last_time_dt = last_time
                    # Ensure it has timezone info
                    if last_time_dt.tzinfo is None:
                        last_time_dt = last_time_dt.replace(tzinfo=UTC)

                # For date comparisons, use the date part only to avoid timezone issues
                oldest_historical_date = min(
                    usage_data.start_date for usage_data in historical_data
                )
                oldest_historical_local = dt_util.as_local(oldest_historical_date)

                # Compare using dates only to avoid timezone precision issues
                if last_time_dt.date() > oldest_historical_local.date():
                    _LOGGER.warning(
                        f"Statistics inconsistency detected for {statistic_id}: last processed date ({last_time_dt.date()}) "
                        f"is newer than oldest historical date ({oldest_historical_local.date()}). Resetting to process historical data."
                    )
                    # Reset to allow historical data processing
                    existing_sum = 0.0
                    last_time = 0
            else:
                # Starting fresh
                existing_sum = 0.0
                last_time = 0

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
                # Preserve the date from PyDropCountr and create local midnight for that date
                # This avoids timezone shifting that could move data to wrong day
                usage_date = usage_data.start_date.date()
                local_start_date = dt_util.start_of_local_day(
                    datetime.combine(usage_date, datetime.min.time())
                )

                # Skip data that's already been processed
                if local_start_date.timestamp() <= last_time:
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

                statistics.append(
                    StatisticData(
                        start=local_start_date,
                        state=value,
                        sum=current_sum,
                    )
                )

            if statistics:
                try:
                    async_add_external_statistics(self.hass, metadata, statistics)
                    _LOGGER.debug(
                        f"Inserted {len(statistics)} {metric_type} statistics"
                    )
                except Exception as ex:
                    _LOGGER.error(
                        f"Failed to insert {metric_type} statistics: {ex}",
                        exc_info=True,
                    )
                    raise

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
        start_time = time.time()
        _LOGGER.debug("Starting usage data update cycle")

        try:
            # First get all service connections
            conn_start = time.time()
            service_connections = await self.hass.async_add_executor_job(
                self.client.list_service_connections
            )
            conn_elapsed = time.time() - conn_start
            if not service_connections:
                _LOGGER.warning(
                    f"No service connections found (API call took {conn_elapsed:.2f}s)"
                )
                return {}
            else:
                _LOGGER.debug(
                    f"Retrieved {len(service_connections)} service connections in {conn_elapsed:.2f}s"
                )

            usage_data = {}
            processed_count = 0
            historical_count = 0
            total_usage_records = 0

            for service_connection in service_connections:
                usage_response = await self.hass.async_add_executor_job(
                    self._get_usage_for_service, service_connection.id
                )
                if usage_response:
                    processed_count += 1
                    if usage_response.usage_data:
                        total_usage_records += len(usage_response.usage_data)
                    # Detect and process historical data
                    historical_data = self._detect_new_historical_data(
                        service_connection.id, usage_response
                    )
                    if historical_data:
                        historical_count += len(historical_data)
                        try:
                            await self._insert_historical_statistics(
                                service_connection.id, historical_data
                            )
                        except Exception as ex:
                            _LOGGER.error(
                                f"Failed to insert historical statistics for service {service_connection.id}: {ex}. Continuing with normal operation.",
                                exc_info=True,
                            )

                    # Update historical state tracking
                    self._update_historical_state(service_connection.id, usage_response)

                    usage_data[service_connection.id] = usage_response

            self.usage_data = usage_data
            elapsed = time.time() - start_time
            _LOGGER.info(
                f"Update cycle completed: {processed_count}/{len(service_connections)} services, "
                f"{total_usage_records} usage records, {historical_count} historical points inserted, {elapsed:.2f}s total"
            )
        except Exception as ex:
            elapsed = time.time() - start_time
            _LOGGER.error(f"Usage data update failed after {elapsed:.2f}s: {ex}")
            raise UpdateFailed(f"Error communicating with DropCountr API: {ex}") from ex
        else:
            return usage_data
