"""Global fixtures for DropCountr integration tests."""

from unittest.mock import Mock, patch

from pydropcountr import ServiceConnection, UsageData, UsageResponse
import pytest

from .const import MOCK_SERVICE_CONNECTION, MOCK_USAGE_DATA


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations defined in the test dir."""
    return


@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture():
    """Skip notification calls."""
    with (
        patch("homeassistant.components.persistent_notification.async_create"),
        patch("homeassistant.components.persistent_notification.async_dismiss"),
    ):
        yield


@pytest.fixture(name="bypass_get_data")
def bypass_get_data_fixture():
    """Skip calls to get data from API."""

    # Create mock service connection
    mock_service_connection = ServiceConnection(
        id=MOCK_SERVICE_CONNECTION["id"],
        name=MOCK_SERVICE_CONNECTION["name"],
        address=MOCK_SERVICE_CONNECTION["address"],
        account_number=MOCK_SERVICE_CONNECTION["account_number"],
        service_type=MOCK_SERVICE_CONNECTION["service_type"],
        status=MOCK_SERVICE_CONNECTION["status"],
        meter_serial=MOCK_SERVICE_CONNECTION["meter_serial"],
        api_id=MOCK_SERVICE_CONNECTION["api_id"],
    )

    # Create mock usage data
    mock_usage_data = [
        UsageData(
            during=data["during"],
            total_gallons=data["total_gallons"],
            irrigation_gallons=data["irrigation_gallons"],
            irrigation_events=data["irrigation_events"],
            is_leaking=data["is_leaking"],
        )
        for data in MOCK_USAGE_DATA
    ]

    # Create mock usage response
    mock_usage_response = UsageResponse(
        usage_data=mock_usage_data,
        total_items=len(mock_usage_data),
        api_id="https://dropcountr.com/api/service_connections/12345/usage",
        consumed_via_id="https://dropcountr.com/api/service_connections/12345",
    )

    # Create a mock session object
    mock_session = Mock()
    mock_session.cookies.clear = Mock()

    def mock_init(self, timezone=None):
        self.session = mock_session
        self.timezone = timezone

    with (
        # Mock the constructor to accept timezone parameter and set session
        patch("pydropcountr.DropCountrClient.__init__", mock_init),
        # Mock all the methods individually
        patch("pydropcountr.DropCountrClient.login", return_value=True),
        patch("pydropcountr.DropCountrClient.is_logged_in", return_value=True),
        patch(
            "pydropcountr.DropCountrClient.list_service_connections",
            return_value=[mock_service_connection],
        ),
        patch(
            "pydropcountr.DropCountrClient.get_usage",
            return_value=mock_usage_response,
        ),
        patch(
            "pydropcountr.DropCountrClient.get_service_connection",
            return_value=mock_service_connection,
        ),
        patch("pydropcountr.DropCountrClient.logout", return_value=None),
        # Mock statistics-related calls to avoid database dependencies in tests
        patch("homeassistant.components.recorder.get_instance"),
        patch(
            "homeassistant.components.recorder.statistics.get_last_statistics",
            return_value={},
        ),
        patch(
            "homeassistant.components.recorder.statistics.async_add_external_statistics"
        ),
    ):
        yield


@pytest.fixture(name="error_on_connect")
def error_on_connect_fixture():
    """Simulate error when connecting to DropCountr."""
    with patch(
        "pydropcountr.DropCountrClient.login",
        side_effect=Exception("Connection failed"),
    ):
        yield
