"""Test previous day statistics functionality."""

from datetime import datetime, timedelta
from unittest.mock import Mock

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
def create_usage_data_with_values():
    """Create usage data for specific dates and values."""

    def _create_usage_data_with_values(
        date_offset_days: int,
        total_gallons: float = 100.0,
        irrigation_gallons: float = 25.0,
        irrigation_events: int = 2,
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
            irrigation_events=irrigation_events,
            is_leaking=False,
        )

    return _create_usage_data_with_values


@pytest.fixture
def mock_coordinator_with_previous_day_data(hass, create_usage_data_with_values):
    """Create a coordinator with previous day data."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    mock_client = Mock()

    coordinator = DropCountrUsageDataUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=mock_client,
    )

    # Create usage data: 3 days ago, 2 days ago, yesterday (non-zero), today (zero)
    usage_data = [
        create_usage_data_with_values(
            3, total_gallons=300.0, irrigation_gallons=75.0, irrigation_events=5
        ),  # 3 days ago
        create_usage_data_with_values(
            2, total_gallons=200.0, irrigation_gallons=50.0, irrigation_events=3
        ),  # 2 days ago
        create_usage_data_with_values(
            1, total_gallons=150.0, irrigation_gallons=35.0, irrigation_events=2
        ),  # Yesterday (non-zero)
        create_usage_data_with_values(
            0, total_gallons=0.0, irrigation_gallons=0.0, irrigation_events=0
        ),  # Today (zero)
    ]

    usage_response = UsageResponse(
        usage_data=usage_data,
        total_items=len(usage_data),
        api_id="https://dropcountr.com/api/service_connections/12345/usage",
        consumed_via_id="https://dropcountr.com/api/service_connections/12345",
    )

    coordinator.data = {MOCK_SERVICE_CONNECTION["id"]: usage_response}
    return coordinator


async def test_coordinator_detects_non_zero_previous_day_as_historical(
    hass, create_usage_data_with_values
):
    """Test that coordinator detects non-zero previous day data as historical."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    mock_client = Mock()

    coordinator = DropCountrUsageDataUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=mock_client,
    )

    # Create usage response with non-zero yesterday data
    usage_data = [
        create_usage_data_with_values(1, total_gallons=150.0),  # Yesterday (non-zero)
    ]

    usage_response = UsageResponse(
        usage_data=usage_data,
        total_items=len(usage_data),
        api_id="https://dropcountr.com/api/service_connections/12345/usage",
        consumed_via_id="https://dropcountr.com/api/service_connections/12345",
    )

    # Test the detection method directly
    historical_data = coordinator._detect_new_historical_data(
        MOCK_SERVICE_CONNECTION["id"], usage_response
    )

    # Should detect the previous day data as historical since it's non-zero
    assert len(historical_data) == 1
    assert historical_data[0].total_gallons == 150.0


async def test_coordinator_does_not_detect_zero_previous_day_as_historical(
    hass, create_usage_data_with_values
):
    """Test that coordinator does not detect zero previous day data as historical."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    mock_client = Mock()

    coordinator = DropCountrUsageDataUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=mock_client,
    )

    # Create usage response with zero yesterday data
    usage_data = [
        create_usage_data_with_values(1, total_gallons=0.0),  # Yesterday (zero)
    ]

    usage_response = UsageResponse(
        usage_data=usage_data,
        total_items=len(usage_data),
        api_id="https://dropcountr.com/api/service_connections/12345/usage",
        consumed_via_id="https://dropcountr.com/api/service_connections/12345",
    )

    # Test the detection method directly
    historical_data = coordinator._detect_new_historical_data(
        MOCK_SERVICE_CONNECTION["id"], usage_response
    )

    # Should not detect zero previous day data as historical
    assert len(historical_data) == 0


async def test_sensor_includes_non_zero_previous_day_data(
    mock_coordinator_with_previous_day_data,
):
    """Test that sensor includes non-zero previous day data."""
    sensor = DropCountrSensor(
        coordinator=mock_coordinator_with_previous_day_data,
        description=DROPCOUNTR_SENSORS[0],  # irrigation_gallons
        service_connection_id=MOCK_SERVICE_CONNECTION["id"],
        service_connection_name=MOCK_SERVICE_CONNECTION["name"],
        service_connection_address=MOCK_SERVICE_CONNECTION["address"],
    )

    # Get the usage data from coordinator
    usage_response = mock_coordinator_with_previous_day_data.data[
        MOCK_SERVICE_CONNECTION["id"]
    ]

    # Test the filtering method directly
    filtered_data = sensor._filter_recent_incomplete_data(usage_response.usage_data)

    # Should include 3 days ago, 2 days ago, and yesterday (non-zero)
    # Should exclude today (zero)
    assert len(filtered_data) == 3

    # Verify the data includes yesterday's non-zero data
    dates = [data.start_date.date() for data in filtered_data]
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    assert yesterday in dates


async def test_sensor_excludes_zero_previous_day_data(
    hass, create_usage_data_with_values
):
    """Test that sensor excludes zero previous day data."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    mock_client = Mock()

    coordinator = DropCountrUsageDataUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=mock_client,
    )

    # Create usage data with zero yesterday data
    usage_data = [
        create_usage_data_with_values(
            2, total_gallons=200.0, irrigation_gallons=50.0
        ),  # 2 days ago
        create_usage_data_with_values(
            1, total_gallons=0.0, irrigation_gallons=0.0
        ),  # Yesterday (zero)
        create_usage_data_with_values(
            0, total_gallons=0.0, irrigation_gallons=0.0
        ),  # Today (zero)
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

    # Test the filtering method directly
    filtered_data = sensor._filter_recent_incomplete_data(usage_response.usage_data)

    # Should only include 2 days ago data, exclude zero yesterday and today
    assert len(filtered_data) == 1

    # Verify it's the 2 days ago data
    dates = [data.start_date.date() for data in filtered_data]
    today = datetime.now().date()
    two_days_ago = today - timedelta(days=2)

    assert dates == [two_days_ago]


async def test_sensor_always_excludes_today_data(hass, create_usage_data_with_values):
    """Test that sensor always excludes today's data regardless of value."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    mock_client = Mock()

    coordinator = DropCountrUsageDataUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=mock_client,
    )

    # Create usage data with non-zero today data (should still be excluded)
    usage_data = [
        create_usage_data_with_values(
            1, total_gallons=150.0, irrigation_gallons=35.0
        ),  # Yesterday (non-zero)
        create_usage_data_with_values(
            0, total_gallons=100.0, irrigation_gallons=25.0
        ),  # Today (non-zero but should be excluded)
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

    # Test the filtering method directly
    filtered_data = sensor._filter_recent_incomplete_data(usage_response.usage_data)

    # Should only include yesterday, exclude today even though it's non-zero
    assert len(filtered_data) == 1

    # Verify it's yesterday's data
    dates = [data.start_date.date() for data in filtered_data]
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    assert dates == [yesterday]


async def test_sensor_value_with_non_zero_previous_day(
    mock_coordinator_with_previous_day_data,
):
    """Test sensor value includes non-zero previous day data."""
    sensor = DropCountrSensor(
        coordinator=mock_coordinator_with_previous_day_data,
        description=DROPCOUNTR_SENSORS[0],  # irrigation_gallons
        service_connection_id=MOCK_SERVICE_CONNECTION["id"],
        service_connection_name=MOCK_SERVICE_CONNECTION["name"],
        service_connection_address=MOCK_SERVICE_CONNECTION["address"],
    )

    # Should return yesterday's irrigation gallons (35.0) since it's the most recent non-filtered data
    value = sensor.native_value
    assert value == 35.0  # irrigation_gallons from yesterday
