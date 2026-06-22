"""Hourly DropCountr usage fetching helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from pydropcountr import DropCountrClient, UsageData, UsageResponse

_LOGGER = logging.getLogger(__package__)


def fetch_hourly_usage_in_daily_windows(
    client: DropCountrClient,
    service_connection_id: int,
    start_date: datetime,
    end_date: datetime,
) -> UsageResponse | None:
    """Fetch hourly usage in API-safe daily windows.

    DropCountr silently returns an empty hourly response for multi-day ranges.
    Split larger ranges into <=24-hour requests and aggregate the returned records.
    """
    if end_date <= start_date:
        return None

    usage_data_by_record: dict[tuple[str, float, float, float, bool], UsageData] = {}
    first_response: UsageResponse | None = None
    cursor = start_date
    request_count = 0

    while cursor < end_date:
        window_end = min(cursor + timedelta(days=1), end_date)
        request_count += 1
        response = client.get_usage(
            service_connection_id=service_connection_id,
            start_date=cursor,
            end_date=window_end,
            period="hour",
        )
        if response is not None:
            if first_response is None:
                first_response = response
            if response.usage_data:
                for usage in response.usage_data:
                    record_key = (
                        usage.during,
                        usage.total_gallons,
                        usage.irrigation_gallons,
                        usage.irrigation_events,
                        usage.is_leaking,
                    )
                    usage_data_by_record[record_key] = usage
        cursor = window_end

    usage_data = sorted(usage_data_by_record.values(), key=lambda data: data.start_date)
    if first_response is None:
        return None

    _LOGGER.debug(
        "Fetched %d hourly records for service %s using %d daily window request(s)",
        len(usage_data),
        service_connection_id,
        request_count,
    )

    return UsageResponse(
        usage_data=usage_data,
        total_items=len(usage_data),
        api_id=first_response.api_id,
        consumed_via_id=first_response.consumed_via_id,
    )
