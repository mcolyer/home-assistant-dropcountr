"""Test sensor filtering for recent incomplete data."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from pydropcountr import UsageData, UsageResponse
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dropcountr.const import DOMAIN
from custom_components.dropcountr.coordinator import (
    DropCountrUsageDataUpdateCoordinator,
)
from custom_components.dropcountr.sensor import DROPCOUNTR_SENSORS, DropCountrSensor

from .const import MOCK_CONFIG, MOCK_SERVICE_CONNECTION


@pytest.fixture
def create_usage_data_with_dates():
    """Create usage data for specific dates."""

    def _create_usage_data_with_dates(
        date_offset_days: int,
        total_gallons: float = 100.0,
        irrigation_gallons: float = 25.0,
    ):
        target_date = datetime.now() - timedelta(days=date_offset_days)
        start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = target_date.replace(
            hour=23, minute=59, second=59, microsecond=999999
        )
        during = f"{start_date.isoformat()}Z/{end_date.isoformat()}Z"
        return UsageData(
            during=during,
            total_gallons=total_gallons,
            irrigation_gallons=irrigation_gallons,
            irrigation_events=2,
            is_leaking=False,
        )

    return _create_usage_data_with_dates


@pytest.fixture
def mock_coordinator_with_mixed_data(hass, create_usage_data_with_dates):
    """Create a coordinator with mixed recent and older data."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    mock_client = Mock()

    coordinator = DropCountrUsageDataUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=mock_client,
    )

    # Create usage data: today (0 days), yesterday (1 day), 2 days ago, 3 days ago
    usage_data = [
        create_usage_data_with_dates(
            3, total_gallons=300.0, irrigation_gallons=75.0
        ),  # 3 days ago
        create_usage_data_with_dates(
            2, total_gallons=200.0, irrigation_gallons=50.0
        ),  # 2 days ago
        create_usage_data_with_dates(
            1, total_gallons=100.0, irrigation_gallons=25.0
        ),  # Yesterday
        create_usage_data_with_dates(
            0, total_gallons=50.0, irrigation_gallons=10.0
        ),  # Today
    ]

    usage_response = UsageResponse(
        usage_data=usage_data,
        total_items=len(usage_data),
        api_id="https://dropcountr.com/api/service_connections/12345/usage",
        consumed_via_id="https://dropcountr.com/api/service_connections/12345",
    )

    coordinator.data = {MOCK_SERVICE_CONNECTION["id"]: usage_response}
    return coordinator


async def test_filter_recent_incomplete_data(
    mock_coordinator_with_mixed_data, create_usage_data_with_dates
):
    """Test that recent incomplete data is properly filtered."""
    # Create a sensor to test the filtering
    sensor = DropCountrSensor(
        coordinator=mock_coordinator_with_mixed_data,
        description=DROPCOUNTR_SENSORS[0],  # irrigation_gallons
        service_connection_id=MOCK_SERVICE_CONNECTION["id"],
        service_connection_name=MOCK_SERVICE_CONNECTION["name"],
        service_connection_address=MOCK_SERVICE_CONNECTION["address"],
    )

    # Test the filtering method directly
    usage_data = [
        create_usage_data_with_dates(3),  # 3 days ago - should be included
        create_usage_data_with_dates(2),  # 2 days ago - should be included
        create_usage_data_with_dates(
            1
        ),  # Yesterday - should be included (non-zero total_gallons=100.0)
        create_usage_data_with_dates(0),  # Today - should be filtered out
    ]

    filtered_data = sensor._filter_recent_incomplete_data(usage_data)

    # Should include 3 days ago, 2 days ago, and yesterday (non-zero), but exclude today
    assert len(filtered_data) == 3

    # Verify the filtered data is from 3, 2, and 1 days ago
    dates = [data.start_date.date() for data in filtered_data]
    today = datetime.now().date()
    expected_dates = [
        today - timedelta(days=3),
        today - timedelta(days=2),
        today - timedelta(days=1),  # Yesterday now included since it's non-zero
    ]

    assert dates == expected_dates


async def test_irrigation_gallons_sensor_includes_yesterday_data(
    mock_coordinator_with_mixed_data,
):
    """Test that irrigation_gallons sensor includes yesterday's non-zero data."""
    sensor = DropCountrSensor(
        coordinator=mock_coordinator_with_mixed_data,
        description=DROPCOUNTR_SENSORS[0],  # irrigation_gallons
        service_connection_id=MOCK_SERVICE_CONNECTION["id"],
        service_connection_name=MOCK_SERVICE_CONNECTION["name"],
        service_connection_address=MOCK_SERVICE_CONNECTION["address"],
    )

    # Should return yesterday's value (1 day ago = 25.0) since it's non-zero
    value = sensor.native_value
    assert value == 25.0  # irrigation_gallons from yesterday


async def test_irrigation_events_sensor_includes_yesterday_data(
    mock_coordinator_with_mixed_data,
):
    """Test that irrigation_events sensor includes yesterday's data when usage is non-zero."""
    sensor = DropCountrSensor(
        coordinator=mock_coordinator_with_mixed_data,
        description=DROPCOUNTR_SENSORS[1],  # irrigation_events
        service_connection_id=MOCK_SERVICE_CONNECTION["id"],
        service_connection_name=MOCK_SERVICE_CONNECTION["name"],
        service_connection_address=MOCK_SERVICE_CONNECTION["address"],
    )

    # Should return yesterday's value (1 day ago = 2 events) since total usage is non-zero
    value = sensor.native_value
    assert value == 2  # irrigation_events from yesterday


async def test_daily_total_sensor_includes_yesterday_data(
    mock_coordinator_with_mixed_data,
):
    """Test that daily_total sensor includes yesterday's non-zero data."""
    sensor = DropCountrSensor(
        coordinator=mock_coordinator_with_mixed_data,
        description=DROPCOUNTR_SENSORS[2],  # daily_total
        service_connection_id=MOCK_SERVICE_CONNECTION["id"],
        service_connection_name=MOCK_SERVICE_CONNECTION["name"],
        service_connection_address=MOCK_SERVICE_CONNECTION["address"],
    )

    # Should return yesterday's value (1 day ago = 100.0) since it's non-zero
    value = sensor.native_value
    assert value == 100.0  # total_gallons from yesterday


async def test_weekly_total_sensor_not_affected(mock_coordinator_with_mixed_data):
    """Test that weekly_total sensor continues to aggregate normally."""
    sensor = DropCountrSensor(
        coordinator=mock_coordinator_with_mixed_data,
        description=DROPCOUNTR_SENSORS[3],  # weekly_total
        service_connection_id=MOCK_SERVICE_CONNECTION["id"],
        service_connection_name=MOCK_SERVICE_CONNECTION["name"],
        service_connection_address=MOCK_SERVICE_CONNECTION["address"],
    )

    # Should return sum of all 4 days (no filtering for weekly totals)
    value = sensor.native_value
    assert value == 650.0  # 300 + 200 + 100 + 50


async def test_monthly_total_sensor_not_affected(mock_coordinator_with_mixed_data):
    """Test that monthly_total sensor continues to work normally."""
    # Mock _get_current_date to return a date in the same month as our test data
    with patch("custom_components.dropcountr.sensor._get_current_date") as mock_date:
        mock_date.return_value = datetime.now().date()

        sensor = DropCountrSensor(
            coordinator=mock_coordinator_with_mixed_data,
            description=DROPCOUNTR_SENSORS[4],  # monthly_total
            service_connection_id=MOCK_SERVICE_CONNECTION["id"],
            service_connection_name=MOCK_SERVICE_CONNECTION["name"],
            service_connection_address=MOCK_SERVICE_CONNECTION["address"],
        )

        # Should aggregate all data for the current month (no filtering for monthly totals)
        value = sensor.native_value
        assert value == 650.0  # 300 + 200 + 100 + 50


async def test_sensor_with_zero_yesterday_data_returns_none(
    hass, create_usage_data_with_dates
):
    """Test sensor behavior when only today/yesterday data is available with zero values."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    mock_client = Mock()

    coordinator = DropCountrUsageDataUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=mock_client,
    )

    # Only today and yesterday data with zero values (both will be filtered out)
    usage_data = [
        create_usage_data_with_dates(1, total_gallons=0.0),  # Yesterday (zero)
        create_usage_data_with_dates(0, total_gallons=0.0),  # Today (zero)
    ]

    usage_response = UsageResponse(
        usage_data=usage_data,
        total_items=len(usage_data),
        api_id="https://dropcountr.com/api/service_connections/12345/usage",
        consumed_via_id="https://dropcountr.com/api/service_connections/12345",
    )

    coordinator.data = {MOCK_SERVICE_CONNECTION["id"]: usage_response}

    sensor = DropCountrSensor(
        coordinator=coordinator,
        description=DROPCOUNTR_SENSORS[0],  # irrigation_gallons
        service_connection_id=MOCK_SERVICE_CONNECTION["id"],
        service_connection_name=MOCK_SERVICE_CONNECTION["name"],
        service_connection_address=MOCK_SERVICE_CONNECTION["address"],
    )

    # Should return None since no usable data is available (zero yesterday data is filtered)
    value = sensor.native_value
    assert value is None


async def test_sensor_with_non_zero_yesterday_data_returns_value(
    hass, create_usage_data_with_dates
):
    """Test sensor behavior when yesterday has non-zero data."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    mock_client = Mock()

    coordinator = DropCountrUsageDataUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=mock_client,
    )

    # Yesterday with non-zero data, today with zero
    usage_data = [
        create_usage_data_with_dates(
            1, total_gallons=100.0, irrigation_gallons=25.0
        ),  # Yesterday (non-zero)
        create_usage_data_with_dates(0, total_gallons=0.0),  # Today (zero)
    ]

    usage_response = UsageResponse(
        usage_data=usage_data,
        total_items=len(usage_data),
        api_id="https://dropcountr.com/api/service_connections/12345/usage",
        consumed_via_id="https://dropcountr.com/api/service_connections/12345",
    )

    coordinator.data = {MOCK_SERVICE_CONNECTION["id"]: usage_response}

    sensor = DropCountrSensor(
        coordinator=coordinator,
        description=DROPCOUNTR_SENSORS[0],  # irrigation_gallons
        service_connection_id=MOCK_SERVICE_CONNECTION["id"],
        service_connection_name=MOCK_SERVICE_CONNECTION["name"],
        service_connection_address=MOCK_SERVICE_CONNECTION["address"],
    )

    # Should return yesterday's irrigation gallons since it's non-zero
    value = sensor.native_value
    assert value == 25.0
