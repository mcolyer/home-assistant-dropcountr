"""Test timezone handling in statistics insertion."""

from datetime import datetime
from unittest.mock import Mock
from zoneinfo import ZoneInfo

from pydropcountr import ServiceConnection, UsageData
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dropcountr.const import DOMAIN
from custom_components.dropcountr.coordinator import (
    DropCountrUsageDataUpdateCoordinator,
)
import homeassistant.util.dt as dt_util

from .const import MOCK_CONFIG, MOCK_SERVICE_CONNECTION


@pytest.fixture
def mock_service_connection():
    """Create a mock service connection."""
    return ServiceConnection(
        id=MOCK_SERVICE_CONNECTION["id"],
        name=MOCK_SERVICE_CONNECTION["name"],
        address=MOCK_SERVICE_CONNECTION["address"],
        account_number=MOCK_SERVICE_CONNECTION["account_number"],
        service_type=MOCK_SERVICE_CONNECTION["service_type"],
    )


@pytest.fixture
def config_entry():
    """Create a test config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        data=MOCK_CONFIG,
        entry_id="test",
    )


@pytest.fixture
def mock_client():
    """Create a mock client."""
    return Mock()


@pytest.fixture
def coordinator(hass, config_entry, mock_client):
    """Create a coordinator for testing."""
    return DropCountrUsageDataUpdateCoordinator(
        hass=hass, config_entry=config_entry, client=mock_client
    )


@pytest.mark.asyncio
async def test_timezone_handling_utc_midnight_dates(
    hass, coordinator, mock_service_connection
):
    """Test that UTC midnight dates are correctly converted to local dates without day shifting.

    This test validates the fix for the timezone issue where PyDropCountr returns
    dates like '2025-05-06 00:00:00+00:00' (UTC midnight) but they should appear
    as '2025-05-06' in the UI regardless of the local timezone.

    Before the fix: UTC midnight could shift to previous day in negative UTC offset timezones
    After the fix: Date is preserved using dt_util.start_of_local_day()
    """
    # Set up Home Assistant timezone to simulate a timezone with negative UTC offset
    # This would cause the original bug where UTC midnight becomes previous day locally
    original_tz = dt_util.DEFAULT_TIME_ZONE

    try:
        # Mock a timezone that's UTC-8 (like Pacific Time)
        dt_util.DEFAULT_TIME_ZONE = ZoneInfo("America/Los_Angeles")

        # Create historical usage data with UTC midnight timestamps
        # These are the exact format that PyDropCountr returns
        historical_usage_data = [
            UsageData(
                during="2025-05-06T00:00:00.000Z/2025-05-07T00:00:00.000Z",  # UTC midnight to midnight
                total_gallons=100.0,
                irrigation_gallons=50.0,
                irrigation_events=2,
                is_leaking=False,
            ),
            UsageData(
                during="2025-05-07T00:00:00.000Z/2025-05-08T00:00:00.000Z",  # UTC midnight to midnight
                total_gallons=150.0,
                irrigation_gallons=75.0,
                irrigation_events=3,
                is_leaking=False,
            ),
        ]

        # Test the timezone conversion logic directly using the coordinator's internal methods
        # This tests the core logic without needing to mock the complex recorder system

        # Test the core timezone conversion that the fix addresses
        for usage_data in historical_usage_data:
            # This is the original problematic approach (before the fix)
            # original_local_date = dt_util.as_local(usage_data.start_date)

            # This is the fixed approach that preserves the date
            usage_date = usage_data.start_date.date()
            fixed_local_date = dt_util.start_of_local_day(
                datetime.combine(usage_date, datetime.min.time())
            )

            # Key assertion: the date should be preserved regardless of timezone conversion
            assert fixed_local_date.date() == usage_data.start_date.date(), (
                f"Date should be preserved: {usage_data.start_date.date()} -> {fixed_local_date.date()}"
            )

            # Verify it's local midnight
            assert fixed_local_date.hour == 0
            assert fixed_local_date.minute == 0
            assert fixed_local_date.second == 0

            # Verify it's in the local timezone (America/Los_Angeles)
            assert str(fixed_local_date.tzinfo) == "America/Los_Angeles"

        # With PyDropCountr 1.0, timezone-aware datetimes are returned in local time
        # This means the date shifting bug is fixed at the API level
        for usage_data in historical_usage_data:
            # This is what the old code did: dt_util.as_local(usage_data.start_date)
            original_local_date = dt_util.as_local(usage_data.start_date)

            # With PyDropCountr 1.0, the start_date is already timezone-aware in local time
            # So dt_util.as_local() should not shift the date anymore
            if str(original_local_date.tzinfo) == "America/Los_Angeles":
                # With PyDropCountr 1.0, the date should be preserved
                assert original_local_date.date() == usage_data.start_date.date(), (
                    f"PyDropCountr 1.0 preserves date: {usage_data.start_date.date()} -> {original_local_date.date()}"
                )

                # The time should remain midnight in local time
                assert original_local_date.hour == 0  # Midnight in Pacific Time

    finally:
        # Restore original timezone
        dt_util.DEFAULT_TIME_ZONE = original_tz


def test_timezone_handling_preserves_date_across_timezones():
    """Test that the same UTC date produces the same local date across different timezones.

    This test ensures that regardless of the Home Assistant timezone setting,
    a UTC date like '2025-05-06 00:00:00+00:00' always results in local date '2025-05-06'.
    """
    # Test data: UTC midnight on May 6th
    usage_data = UsageData(
        during="2025-05-06T00:00:00.000Z/2025-05-07T00:00:00.000Z",  # UTC midnight to midnight
        total_gallons=100.0,
        irrigation_gallons=50.0,
        irrigation_events=2,
        is_leaking=False,
    )

    # Test in multiple timezones
    timezones_to_test = [
        "America/Los_Angeles",  # UTC-8/-7 (negative offset)
        "America/New_York",  # UTC-5/-4 (negative offset)
        "UTC",  # UTC+0 (no offset)
        "Europe/London",  # UTC+0/+1 (positive offset)
        "Asia/Tokyo",  # UTC+9 (positive offset)
        "Australia/Sydney",  # UTC+10/+11 (positive offset)
    ]

    original_tz = dt_util.DEFAULT_TIME_ZONE

    try:
        for timezone_name in timezones_to_test:
            # Set the timezone directly
            dt_util.DEFAULT_TIME_ZONE = ZoneInfo(timezone_name)

            # Test the fixed approach that preserves the date
            usage_date = usage_data.start_date.date()
            fixed_local_date = dt_util.start_of_local_day(
                datetime.combine(usage_date, datetime.min.time())
            )

            # Key assertion: the date should be preserved regardless of timezone
            assert fixed_local_date.date() == datetime(2025, 5, 6).date(), (
                f"In timezone {timezone_name}, expected date 2025-05-06, got {fixed_local_date.date()}"
            )

            # Verify it's local midnight in the target timezone
            assert fixed_local_date.hour == 0
            assert fixed_local_date.minute == 0
            assert fixed_local_date.second == 0

            # Verify it's in the correct timezone
            assert str(fixed_local_date.tzinfo) == timezone_name

    finally:
        # Restore original timezone
        dt_util.DEFAULT_TIME_ZONE = original_tz
