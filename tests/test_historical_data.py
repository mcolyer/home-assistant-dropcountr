"""Test historical data functionality."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from pydropcountr import ServiceConnection, UsageData, UsageResponse
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dropcountr.const import (
    DOMAIN,
    LAST_SEEN_DATES_KEY,
    LAST_UPDATE_KEY,
)
from custom_components.dropcountr.coordinator import (
    DropCountrUsageDataUpdateCoordinator,
)

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
        status=MOCK_SERVICE_CONNECTION["status"],
        meter_serial=MOCK_SERVICE_CONNECTION["meter_serial"],
        api_id=MOCK_SERVICE_CONNECTION["api_id"],
    )


@pytest.fixture
def create_usage_data():
    """Create usage data for testing."""

    def _create_usage_data(
        hours_ago: int, total_gallons: float = 5.0, irrigation_gallons: float = 1.0
    ):
        base_datetime = datetime.now() - timedelta(hours=hours_ago)
        start_date = base_datetime.replace(minute=0, second=0, microsecond=0)
        end_date = start_date.replace(minute=59, second=59, microsecond=999999)
        during = f"{start_date.isoformat()}Z/{end_date.isoformat()}Z"
        return UsageData(
            during=during,
            total_gallons=total_gallons,
            irrigation_gallons=irrigation_gallons,
            irrigation_events=1 if irrigation_gallons > 0 else 0,
            is_leaking=False,
        )

    return _create_usage_data


@pytest.fixture
def create_usage_response():
    """Create usage response for testing."""

    def _create_usage_response(usage_data: list[UsageData]):
        return UsageResponse(
            usage_data=usage_data,
            total_items=len(usage_data),
            api_id="https://dropcountr.com/api/service_connections/12345/usage",
            consumed_via_id="https://dropcountr.com/api/service_connections/12345",
        )

    return _create_usage_response


@pytest.fixture
def config_entry():
    """Create a mock config entry."""
    return MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)


@pytest.fixture
def usage_coordinator(hass, config_entry):
    """Create a usage coordinator for testing."""
    mock_client = Mock()
    mock_client.list_service_connections.return_value = []

    coordinator = DropCountrUsageDataUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=mock_client,
    )
    return coordinator


async def test_get_historical_state_initialization(usage_coordinator):
    """Test that historical state is properly initialized."""
    service_id = 12345

    # First call should initialize the state
    state = usage_coordinator._get_historical_state(service_id)

    assert LAST_SEEN_DATES_KEY in state
    assert LAST_UPDATE_KEY in state
    assert isinstance(state[LAST_SEEN_DATES_KEY], set)
    assert len(state[LAST_SEEN_DATES_KEY]) == 0
    assert state[LAST_UPDATE_KEY] is None


async def test_detect_new_historical_data_no_data(
    usage_coordinator, create_usage_response
):
    """Test historical data detection with no data."""
    service_id = 12345
    usage_response = create_usage_response([])

    historical_data = usage_coordinator._detect_new_historical_data(
        service_id, usage_response
    )

    assert historical_data == []


async def test_detect_new_historical_data_recent_data(
    usage_coordinator, create_usage_data, create_usage_response
):
    """Test that recent data (within 2 hours) is not considered historical."""
    service_id = 12345

    # Create usage data from 1 hour ago (too recent)
    recent_usage = create_usage_data(1)
    usage_response = create_usage_response([recent_usage])

    historical_data = usage_coordinator._detect_new_historical_data(
        service_id, usage_response
    )

    assert historical_data == []


async def test_detect_new_historical_data_old_data_first_time(
    usage_coordinator, create_usage_data, create_usage_response
):
    """Test detecting historical data for the first time."""
    service_id = 12345

    # Create usage data from 5 hours ago (historical)
    old_usage = create_usage_data(5)
    usage_response = create_usage_response([old_usage])

    historical_data = usage_coordinator._detect_new_historical_data(
        service_id, usage_response
    )

    assert len(historical_data) == 1
    assert historical_data[0] == old_usage


async def test_detect_new_historical_data_already_seen(
    usage_coordinator, create_usage_data, create_usage_response
):
    """Test that already seen historical data is not detected again."""
    service_id = 12345

    # Create usage data from 5 hours ago
    old_usage = create_usage_data(5)
    usage_response = create_usage_response([old_usage])

    # First detection - should find new data
    historical_data = usage_coordinator._detect_new_historical_data(
        service_id, usage_response
    )
    assert len(historical_data) == 1

    # Update historical state
    usage_coordinator._update_historical_state(service_id, usage_response)

    # Second detection - should not find any new data
    historical_data = usage_coordinator._detect_new_historical_data(
        service_id, usage_response
    )
    assert len(historical_data) == 0


async def test_detect_mixed_new_and_old_data(
    usage_coordinator, create_usage_data, create_usage_response
):
    """Test detecting new historical data mixed with already seen data."""
    service_id = 12345

    # First batch - 5 hours ago
    old_usage_1 = create_usage_data(5)
    usage_response_1 = create_usage_response([old_usage_1])

    # Process first batch
    usage_coordinator._detect_new_historical_data(service_id, usage_response_1)
    usage_coordinator._update_historical_state(service_id, usage_response_1)

    # Second batch - mix of old (seen) and new historical data
    old_usage_2 = create_usage_data(7)  # New historical data (7 hours ago)
    usage_response_2 = create_usage_response([old_usage_1, old_usage_2])

    historical_data = usage_coordinator._detect_new_historical_data(
        service_id, usage_response_2
    )

    assert len(historical_data) == 1
    assert historical_data[0] == old_usage_2


async def test_update_historical_state(
    usage_coordinator, create_usage_data, create_usage_response
):
    """Test updating historical state tracking."""
    service_id = 12345

    # Create usage data
    usage_1 = create_usage_data(5)
    usage_2 = create_usage_data(3)
    usage_response = create_usage_response([usage_1, usage_2])

    # Update state
    usage_coordinator._update_historical_state(service_id, usage_response)

    # Check state was updated
    state = usage_coordinator._get_historical_state(service_id)

    assert len(state[LAST_SEEN_DATES_KEY]) == 2
    assert state[LAST_UPDATE_KEY] is not None


async def test_historical_state_cleanup(
    usage_coordinator, create_usage_data, create_usage_response
):
    """Test that old hourly timestamps are cleaned up from historical state."""
    service_id = 12345

    # Create usage data from 8 days ago (should be cleaned up - outside 7 day window)
    old_usage = create_usage_data(8 * 24)  # 8 days * 24 hours
    # Create recent usage data from 5 hours ago (should be kept)
    recent_usage = create_usage_data(5)

    usage_response = create_usage_response([old_usage, recent_usage])

    # Update state
    usage_coordinator._update_historical_state(service_id, usage_response)

    # Check that only recent data is kept (older than 7 days is cleaned up)
    state = usage_coordinator._get_historical_state(service_id)

    assert len(state[LAST_SEEN_DATES_KEY]) == 1
    # The recent usage should still be there, but old usage should be cleaned up
    # We need to check based on the actual hourly timestamps that were tracked


async def test_full_update_cycle_with_historical_data(
    hass,
    config_entry,
    mock_service_connection,
    create_usage_data,
    create_usage_response,
):
    """Test the full update cycle including historical data processing."""
    # Create mock client
    mock_client = Mock()
    mock_client.list_service_connections.return_value = [mock_service_connection]

    # Create usage response with historical data
    historical_usage = create_usage_data(5, total_gallons=10.0)  # 5 hours ago
    recent_usage = create_usage_data(1, total_gallons=5.0)  # 1 hour ago (too recent)

    usage_response = create_usage_response([historical_usage, recent_usage])
    mock_client.get_usage.return_value = usage_response

    # Create coordinator
    coordinator = DropCountrUsageDataUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=mock_client,
    )

    # Mock the statistics insertion method
    with patch.object(
        coordinator, "_insert_historical_statistics"
    ) as mock_insert_stats:
        # Run update
        result = await coordinator._async_update_data()

        # Check that data was returned
        assert mock_service_connection.id in result
        assert result[mock_service_connection.id] == usage_response

        # Check that historical statistics were inserted
        mock_insert_stats.assert_called_once()
        call_args = mock_insert_stats.call_args
        assert call_args[0][0] == mock_service_connection.id  # service_connection_id
        historical_data_arg = call_args[0][1]  # historical_data list
        assert len(historical_data_arg) == 1  # Only historical data (5 hours old)
        assert historical_data_arg[0] == historical_usage

    # Check that historical state was updated
    state = coordinator._get_historical_state(mock_service_connection.id)
    assert (
        len(state[LAST_SEEN_DATES_KEY]) == 2
    )  # Both hourly timestamps should be tracked


async def test_no_duplicate_events_on_subsequent_updates(
    hass,
    config_entry,
    mock_service_connection,
    create_usage_data,
    create_usage_response,
):
    """Test that duplicate historical events are not fired on subsequent updates."""
    # Create mock client
    mock_client = Mock()
    mock_client.list_service_connections.return_value = [mock_service_connection]

    # Create usage response with historical data
    historical_usage = create_usage_data(5, total_gallons=10.0)  # 5 hours ago
    usage_response = create_usage_response([historical_usage])
    mock_client.get_usage.return_value = usage_response

    # Create coordinator
    coordinator = DropCountrUsageDataUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=mock_client,
    )

    # Mock the statistics insertion method
    with patch.object(
        coordinator, "_insert_historical_statistics"
    ) as mock_insert_stats:
        # First update - should insert statistics
        await coordinator._async_update_data()
        first_call_count = mock_insert_stats.call_count
        assert first_call_count == 1

        # Second update with same data - should not insert additional statistics
        await coordinator._async_update_data()
        second_call_count = mock_insert_stats.call_count

        assert second_call_count == 1  # No additional calls
