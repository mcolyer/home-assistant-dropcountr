"""Test water cost statistics functionality."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from pydropcountr import ServiceConnection, UsageData, UsageResponse
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dropcountr.const import COST_PER_GALLON, DOMAIN
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
            irrigation_events=2,
            is_leaking=False,
        )

    return _create_usage_data


def create_usage_response(usage_data_list):
    """Create a UsageResponse with the given usage data."""
    return UsageResponse(
        usage_data=usage_data_list,
        total_items=len(usage_data_list),
        api_id="https://dropcountr.com/api/service_connections/12345/usage",
        consumed_via_id="https://dropcountr.com/api/service_connections/12345",
    )


@pytest.fixture
def config_entry():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="test_unique_id",
        entry_id="test_entry_id",
    )


async def test_cost_calculation_in_statistics(
    hass, config_entry, mock_service_connection, create_usage_data
):
    """Test that water cost is correctly calculated and included in statistics."""
    # Create mock client
    mock_client = Mock()
    mock_client.list_service_connections.return_value = [mock_service_connection]

    # Create usage data with known gallon amounts
    test_gallons = 100.0
    historical_usage = create_usage_data(5, total_gallons=test_gallons)  # 5 hours ago

    usage_response = create_usage_response([historical_usage])
    mock_client.get_usage.return_value = usage_response

    # Create coordinator
    coordinator = DropCountrUsageDataUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=mock_client,
    )

    # Mock the async_add_external_statistics method to capture what gets inserted
    inserted_statistics = []

    def capture_statistics(hass_instance, metadata, stats):
        inserted_statistics.append((metadata["statistic_id"], metadata, stats))

    # Mock the statistics insertion
    with patch(
        "custom_components.dropcountr.coordinator.async_add_external_statistics",
        side_effect=capture_statistics,
    ):
        with patch(
            "custom_components.dropcountr.coordinator.get_instance"
        ) as mock_get_instance:
            mock_get_instance.return_value = hass
            with patch(
                "custom_components.dropcountr.coordinator.get_last_statistics",
                return_value={},
            ):
                # Run the statistics insertion
                historical_data = [historical_usage]
                await coordinator._insert_historical_statistics(
                    mock_service_connection.id, historical_data, mock_service_connection
                )

    # Verify statistics were captured - 4 types including cost
    assert len(inserted_statistics) == 4

    # Find the cost statistics
    total_cost_stats = next(
        (s for s in inserted_statistics if s[0].endswith("_total_cost")), None
    )
    assert total_cost_stats is not None, "Cost statistics should be present"

    # Verify cost metadata
    cost_metadata = total_cost_stats[1]
    assert (
        cost_metadata["name"]
        == f"DropCountr {mock_service_connection.name} Total Water Cost"
    )
    assert cost_metadata["unit_of_measurement"] == "$"

    # Verify cost calculation
    cost_data_points = total_cost_stats[2]
    assert len(cost_data_points) == 1, "Should have one cost data point"

    expected_cost = round(test_gallons * COST_PER_GALLON, 2)
    actual_cost = cost_data_points[0]["state"]

    assert actual_cost == expected_cost, (
        f"Expected cost {expected_cost}, got {actual_cost}"
    )

    # Also verify the sum (cumulative total)
    expected_sum = expected_cost  # First entry, so sum equals state
    actual_sum = cost_data_points[0]["sum"]
    assert actual_sum == expected_sum, f"Expected sum {expected_sum}, got {actual_sum}"


async def test_cost_calculation_with_multiple_data_points(
    hass, config_entry, mock_service_connection, create_usage_data
):
    """Test cost calculation with multiple historical data points."""
    # Create mock client
    mock_client = Mock()
    mock_client.list_service_connections.return_value = [mock_service_connection]

    # Create multiple usage data points
    usage_data_list = [
        create_usage_data(10, total_gallons=50.0),  # 10 hours ago
        create_usage_data(8, total_gallons=75.0),  # 8 hours ago
        create_usage_data(6, total_gallons=100.0),  # 6 hours ago
    ]

    usage_response = create_usage_response(usage_data_list)
    mock_client.get_usage.return_value = usage_response

    # Create coordinator
    coordinator = DropCountrUsageDataUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=mock_client,
    )

    # Mock the async_add_external_statistics method to capture what gets inserted
    inserted_statistics = []

    def capture_statistics(hass_instance, metadata, stats):
        inserted_statistics.append((metadata["statistic_id"], metadata, stats))

    # Mock the statistics insertion
    with patch(
        "custom_components.dropcountr.coordinator.async_add_external_statistics",
        side_effect=capture_statistics,
    ):
        with patch(
            "custom_components.dropcountr.coordinator.get_instance"
        ) as mock_get_instance:
            mock_get_instance.return_value = hass
            with patch(
                "custom_components.dropcountr.coordinator.get_last_statistics",
                return_value={},
            ):
                # Run the statistics insertion
                await coordinator._insert_historical_statistics(
                    mock_service_connection.id, usage_data_list, mock_service_connection
                )

    # Find the cost statistics
    total_cost_stats = next(
        (s for s in inserted_statistics if s[0].endswith("_total_cost")), None
    )
    assert total_cost_stats is not None

    # Verify we have 3 data points
    cost_data_points = total_cost_stats[2]
    assert len(cost_data_points) == 3, "Should have three cost data points"

    # Verify cost calculations for each point
    expected_costs = [
        round(50.0 * COST_PER_GALLON, 2),
        round(75.0 * COST_PER_GALLON, 2),
        round(100.0 * COST_PER_GALLON, 2),
    ]

    actual_costs = [point["state"] for point in cost_data_points]
    assert actual_costs == expected_costs

    # Verify cumulative sums
    expected_sums = [
        expected_costs[0],  # First point: sum = state
        expected_costs[0] + expected_costs[1],  # Second point: running total
        sum(expected_costs),  # Third point: total of all
    ]

    actual_sums = [point["sum"] for point in cost_data_points]
    assert actual_sums == expected_sums


async def test_zero_gallons_zero_cost(
    hass, config_entry, mock_service_connection, create_usage_data
):
    """Test that zero gallons results in zero cost."""
    # Create mock client
    mock_client = Mock()
    mock_client.list_service_connections.return_value = [mock_service_connection]

    # Create usage data with zero gallons
    zero_usage = create_usage_data(5, total_gallons=0.0)  # 5 hours ago

    usage_response = create_usage_response([zero_usage])
    mock_client.get_usage.return_value = usage_response

    # Create coordinator
    coordinator = DropCountrUsageDataUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=mock_client,
    )

    # Mock the async_add_external_statistics method to capture what gets inserted
    inserted_statistics = []

    def capture_statistics(hass_instance, metadata, stats):
        inserted_statistics.append((metadata["statistic_id"], metadata, stats))

    # Mock the statistics insertion
    with patch(
        "custom_components.dropcountr.coordinator.async_add_external_statistics",
        side_effect=capture_statistics,
    ):
        with patch(
            "custom_components.dropcountr.coordinator.get_instance"
        ) as mock_get_instance:
            mock_get_instance.return_value = hass
            with patch(
                "custom_components.dropcountr.coordinator.get_last_statistics",
                return_value={},
            ):
                # Run the statistics insertion
                await coordinator._insert_historical_statistics(
                    mock_service_connection.id, [zero_usage], mock_service_connection
                )

    # Find the cost statistics
    total_cost_stats = next(
        (s for s in inserted_statistics if s[0].endswith("_total_cost")), None
    )
    assert total_cost_stats is not None

    # Verify zero cost for zero gallons
    cost_data_points = total_cost_stats[2]
    assert len(cost_data_points) == 1
    assert cost_data_points[0]["state"] == 0.0
    assert cost_data_points[0]["sum"] == 0.0
