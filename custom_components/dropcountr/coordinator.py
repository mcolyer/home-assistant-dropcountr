"""The DropCountr integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import threading
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
        self._cached_service_connections: list[ServiceConnection] | None = None
        self._service_connections_cache_time: datetime | None = None
        self._cache_duration = timedelta(
            minutes=5
        )  # Cache service connections for 5 minutes
        self._statistics_inserted_this_session: dict[
            int, set[str]
        ] = {}  # Track what we've inserted per service
        self._cache_lock = threading.Lock()  # Thread-safe cache access
        self._state_lock = threading.Lock()  # Thread-safe shared state access

    def _raise_cache_failure(self, message: str) -> None:
        """Raise cache failure exception."""
        raise UpdateFailed(message)

    async def _get_cached_service_connections(self) -> list[ServiceConnection]:
        """Get service connections from cache or fetch fresh if cache is expired."""
        now = datetime.now()

        # Thread-safe cache check
        with self._cache_lock:
            # Check if cache is valid
            if (
                self._cached_service_connections is not None
                and self._service_connections_cache_time is not None
                and now - self._service_connections_cache_time < self._cache_duration
            ):
                _LOGGER.debug(
                    f"Using cached service connections ({len(self._cached_service_connections)} connections)"
                )
                return (
                    self._cached_service_connections.copy()
                )  # Return copy to prevent mutations

            # Check if someone else is already fetching (avoid duplicate API calls)
            cache_expired = (
                self._cached_service_connections is None
                or self._service_connections_cache_time is None
                or now - self._service_connections_cache_time >= self._cache_duration
            )

        if not cache_expired:
            # Another thread updated the cache while we were waiting
            with self._cache_lock:
                if self._cached_service_connections is not None:
                    return self._cached_service_connections.copy()

        # Cache expired or not set, fetch fresh data
        _LOGGER.debug("Fetching fresh service connections (cache expired or not set)")
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
                # Return cached data if available, even if expired
                with self._cache_lock:
                    if self._cached_service_connections is not None:
                        _LOGGER.info(
                            "Returning expired cached service connections due to API failure"
                        )
                        return self._cached_service_connections.copy()
                self._raise_cache_failure("Failed to get service connections")
            else:
                # Thread-safe cache update
                with self._cache_lock:
                    self._cached_service_connections = service_connections
                    self._service_connections_cache_time = now
                _LOGGER.debug(
                    f"Cached {len(service_connections)} service connections in {elapsed:.2f}s"
                )
                return service_connections

        except Exception as ex:
            elapsed = time.time() - start_time
            _LOGGER.error(
                f"API call to list_service_connections failed after {elapsed:.2f}s: {ex}"
            )
            # Return cached data if available, even if expired
            with self._cache_lock:
                if self._cached_service_connections is not None:
                    _LOGGER.info(
                        "Returning expired cached service connections due to API error"
                    )
                    return self._cached_service_connections.copy()
            raise UpdateFailed(f"Error communicating with DropCountr API: {ex}") from ex

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

            days_requested = (end_date - start_date).days
            _LOGGER.debug(
                f"Fetching usage data for service {service_connection_id} ({days_requested} days)"
            )

            api_start = time.time()
            result = self.client.get_usage(
                service_connection_id=service_connection_id,
                start_date=start_date,
                end_date=end_date,
                period="day",
            )
            api_elapsed = time.time() - api_start
            total_elapsed = time.time() - start_time

            if result and result.usage_data:
                records_count = len(result.usage_data)
                _LOGGER.debug(
                    f"API fetch: service {service_connection_id} returned {records_count} usage records "
                    f"(API: {api_elapsed:.3f}s, total: {total_elapsed:.3f}s, {records_count / api_elapsed:.1f} records/sec)"
                )
                return result
            else:
                _LOGGER.warning(
                    f"API fetch: service {service_connection_id} returned no data "
                    f"(API: {api_elapsed:.3f}s, total: {total_elapsed:.3f}s)"
                )
                return result
        except Exception as ex:
            elapsed = time.time() - start_time
            _LOGGER.error(
                f"Error getting usage for service {service_connection_id} after {elapsed:.3f}s: {ex}"
            )
            return None

    def _get_historical_state(self, service_connection_id: int) -> dict[str, Any]:
        """Get historical state for a service connection."""
        with self._state_lock:
            if service_connection_id not in self._historical_state:
                self._historical_state[service_connection_id] = {
                    LAST_SEEN_DATES_KEY: set(),
                    LAST_UPDATE_KEY: None,
                }
            return self._historical_state[service_connection_id]

    def _check_and_mark_statistics_inserted(
        self, service_connection_id: int, insertion_key: str
    ) -> bool:
        """Thread-safe check and mark for statistics insertion tracking."""
        with self._state_lock:
            if service_connection_id not in self._statistics_inserted_this_session:
                self._statistics_inserted_this_session[service_connection_id] = set()

            if (
                insertion_key
                in self._statistics_inserted_this_session[service_connection_id]
            ):
                return True  # Already inserted

            # Mark as inserted
            self._statistics_inserted_this_session[service_connection_id].add(
                insertion_key
            )
            return False  # Not previously inserted

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
            # Sort by date for cleaner logging
            new_historical_data.sort(key=lambda x: x.start_date.date())
            _LOGGER.info(
                f"Found {len(new_historical_data)} new historical data points for service {service_connection_id} "
                f"(date range: {new_historical_data[0].start_date.date()} to {new_historical_data[-1].start_date.date()})"
            )

        return new_historical_data

    async def _insert_historical_statistics(
        self,
        service_connection_id: int,
        historical_data: list[UsageData],
        service_connection: ServiceConnection,
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

        stats_start = time.time()
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

            # Create a key to track this specific insertion and check if already processed
            insertion_key = f"{metric_type}_{min(data.start_date.date() for data in historical_data)}_{max(data.start_date.date() for data in historical_data)}"
            if self._check_and_mark_statistics_inserted(
                service_connection_id, insertion_key
            ):
                _LOGGER.debug(
                    f"Skipping {metric_type} statistics insertion for service {service_connection_id}: already inserted in this session"
                )
                continue

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
                # Only reset if the gap is significant (more than 2 days) to avoid unnecessary resets
                date_diff = (last_time_dt.date() - oldest_historical_local.date()).days
                if date_diff > 2:
                    _LOGGER.warning(
                        f"Statistics inconsistency detected for {statistic_id}: last processed date ({last_time_dt.date()}) "
                        f"is {date_diff} days newer than oldest historical date ({oldest_historical_local.date()}). Resetting to process historical data."
                    )
                    # Reset to allow historical data processing
                    existing_sum = 0.0
                    last_time = 0
                elif date_diff > 0:
                    _LOGGER.debug(
                        f"Small date gap detected for {statistic_id}: last processed date ({last_time_dt.date()}) "
                        f"is {date_diff} days newer than oldest historical date ({oldest_historical_local.date()}). Continuing normally."
                    )
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
                    _LOGGER.debug(
                        f"Skipping {metric_type} for {usage_date}: already processed (timestamp {local_start_date.timestamp()} <= {last_time})"
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

                statistics.append(
                    StatisticData(
                        start=local_start_date,
                        state=value,
                        sum=current_sum,
                    )
                )

            if statistics:
                try:
                    # Log what we're about to insert for debugging
                    date_range = (
                        f"{statistics[0].start.date()} to {statistics[-1].start.date()}"
                        if len(statistics) > 1
                        else str(statistics[0].start.date())
                    )
                    _LOGGER.debug(
                        f"Inserting {len(statistics)} {metric_type} statistics for dates: {date_range}"
                    )

                    async_add_external_statistics(self.hass, metadata, statistics)
                    _LOGGER.debug(
                        f"Successfully inserted {len(statistics)} {metric_type} statistics"
                    )
                except Exception as ex:
                    _LOGGER.error(
                        f"Failed to insert {metric_type} statistics: {ex}",
                        exc_info=True,
                    )
                    raise

        stats_elapsed = time.time() - stats_start
        _LOGGER.debug(
            f"Statistics insertion completed in {stats_elapsed:.3f}s for service {service_connection_id}"
        )

    def _update_historical_state(
        self, service_connection_id: int, usage_response: UsageResponse
    ) -> None:
        """Update the historical state tracking."""
        if not usage_response or not usage_response.usage_data:
            return

        current_date = datetime.now().date()
        cutoff_date = current_date - timedelta(days=60)  # Keep only last 60 days

        # Collect new dates to add
        new_dates = set()
        for usage_data in usage_response.usage_data:
            usage_date = usage_data.start_date.date()
            # Only track dates that are within our retention window
            if cutoff_date <= usage_date <= current_date:
                new_dates.add(usage_date)

        # Thread-safe update of historical state
        with self._state_lock:
            if service_connection_id not in self._historical_state:
                self._historical_state[service_connection_id] = {
                    LAST_SEEN_DATES_KEY: set(),
                    LAST_UPDATE_KEY: None,
                }

            historical_state = self._historical_state[service_connection_id]

            # Merge with existing dates and apply retention policy in one atomic operation
            existing_dates = historical_state[LAST_SEEN_DATES_KEY]
            historical_state[LAST_SEEN_DATES_KEY] = (existing_dates | new_dates) & {
                date for date in (existing_dates | new_dates) if date > cutoff_date
            }

            # Update the last update timestamp
            historical_state[LAST_UPDATE_KEY] = datetime.now()

            # Log memory usage periodically (every 10th update)
            dates_count = len(historical_state[LAST_SEEN_DATES_KEY])
            if dates_count > 0 and dates_count % 10 == 0:
                _LOGGER.debug(
                    f"Historical state memory: service {service_connection_id} tracking {dates_count} dates"
                )

    def _cleanup_historical_state(self) -> None:
        """Periodic cleanup of historical state to prevent memory growth."""
        cutoff_date = datetime.now().date() - timedelta(days=60)
        services_cleaned = 0
        dates_removed = 0

        with self._state_lock:
            for _service_id, state in self._historical_state.items():
                if LAST_SEEN_DATES_KEY in state:
                    original_count = len(state[LAST_SEEN_DATES_KEY])
                    state[LAST_SEEN_DATES_KEY] = {
                        date
                        for date in state[LAST_SEEN_DATES_KEY]
                        if date > cutoff_date
                    }
                    removed = original_count - len(state[LAST_SEEN_DATES_KEY])
                    if removed > 0:
                        services_cleaned += 1
                        dates_removed += removed

        if services_cleaned > 0:
            _LOGGER.debug(
                f"Historical state cleanup: removed {dates_removed} old dates from {services_cleaned} services"
            )

    async def _process_service_connection(
        self, service_connection: ServiceConnection
    ) -> tuple[int, UsageResponse | None, int]:
        """Process a single service connection and return usage data and historical count."""
        usage_response = await self.hass.async_add_executor_job(
            self._get_usage_for_service, service_connection.id
        )

        historical_count = 0
        if usage_response:
            # Detect and process historical data
            historical_data = self._detect_new_historical_data(
                service_connection.id, usage_response
            )
            if historical_data:
                historical_count = len(historical_data)
                try:
                    await self._insert_historical_statistics(
                        service_connection.id, historical_data, service_connection
                    )
                except Exception as ex:
                    _LOGGER.error(
                        f"Failed to insert historical statistics for service {service_connection.id}: {ex}. Continuing with normal operation.",
                        exc_info=True,
                    )

            # Update historical state tracking
            self._update_historical_state(service_connection.id, usage_response)

        return service_connection.id, usage_response, historical_count

    async def _async_update_data(self) -> dict[int, UsageResponse]:
        """Update usage data for all service connections."""
        start_time = time.time()
        _LOGGER.debug("Starting usage data update cycle")

        try:
            # Get all service connections using cache
            conn_start = time.time()
            service_connections = await self._get_cached_service_connections()
            conn_elapsed = time.time() - conn_start

            if not service_connections:
                _LOGGER.warning(
                    f"No service connections found (operation took {conn_elapsed:.2f}s)"
                )
                return {}
            else:
                _LOGGER.debug(
                    f"Retrieved {len(service_connections)} service connections in {conn_elapsed:.2f}s"
                )

            # Process all service connections in parallel
            processing_start = time.time()
            tasks = [
                self._process_service_connection(service_connection)
                for service_connection in service_connections
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)
            processing_elapsed = time.time() - processing_start

            # Process results
            usage_data = {}
            processed_count = 0
            historical_count = 0
            total_usage_records = 0

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    _LOGGER.error(
                        f"Error processing service connection {service_connections[i].id}: {result}",
                        exc_info=result,
                    )
                    continue

                service_id, usage_response, hist_count = result
                if usage_response:
                    processed_count += 1
                    historical_count += hist_count
                    if usage_response.usage_data:
                        total_usage_records += len(usage_response.usage_data)
                    usage_data[service_id] = usage_response

            self.usage_data = usage_data

            # Periodic cleanup of historical state (every 10th update)
            update_count = len(usage_data)
            if update_count > 0 and update_count % 10 == 0:
                self._cleanup_historical_state()

            elapsed = time.time() - start_time
            _LOGGER.info(
                f"Update cycle completed: {processed_count}/{len(service_connections)} services, "
                f"{total_usage_records} usage records, {historical_count} historical points inserted, "
                f"{elapsed:.2f}s total (connections: {conn_elapsed:.2f}s, processing: {processing_elapsed:.2f}s)"
            )
        except Exception as ex:
            elapsed = time.time() - start_time
            _LOGGER.error(f"Usage data update failed after {elapsed:.2f}s: {ex}")
            raise UpdateFailed(f"Error communicating with DropCountr API: {ex}") from ex
        else:
            return usage_data
