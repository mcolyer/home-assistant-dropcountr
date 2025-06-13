"""Constants for DropCountr tests."""

from custom_components.dropcountr.const import DOMAIN

MOCK_CONFIG = {
    "username": "test@example.com",
    "password": "password123"
}

MOCK_SERVICE_CONNECTION = {
    "id": 12345,
    "name": "Test Service Connection",
    "address": "123 Test Street, Test City, TS 12345",
    "account_number": "ACC123456",
    "service_type": "residential",
    "status": "active",
    "meter_serial": "MTR789",
    "api_id": "https://dropcountr.com/api/service_connections/12345"
}

MOCK_USAGE_DATA = [
    # Previous month data (May 2025) - should not be included in current month totals
    {
        "during": "2025-05-30T00:00:00.000Z/2025-05-31T00:00:00.000Z",
        "total_gallons": 200.0,
        "irrigation_gallons": 100.0,
        "irrigation_events": 4.0,
        "is_leaking": False
    },
    {
        "during": "2025-05-30T00:00:00.000Z/2025-05-31T00:00:00.000Z",
        "total_gallons": 180.0,
        "irrigation_gallons": 90.0,
        "irrigation_events": 3.0,
        "is_leaking": False
    },
    # Current month data (June 2025) - should be included in monthly totals
    {
        "during": "2025-06-01T00:00:00.000Z/2025-06-02T00:00:00.000Z",
        "total_gallons": 100.0,
        "irrigation_gallons": 40.0,
        "irrigation_events": 2.0,
        "is_leaking": False
    },
    {
        "during": "2025-06-12T00:00:00.000Z/2025-06-13T00:00:00.000Z",
        "total_gallons": 150.5,
        "irrigation_gallons": 75.2,
        "irrigation_events": 3.0,
        "is_leaking": False
    },
    {
        "during": "2025-06-13T00:00:00.000Z/2025-06-14T00:00:00.000Z", 
        "total_gallons": 120.3,
        "irrigation_gallons": 50.1,
        "irrigation_events": 2.0,
        "is_leaking": False
    }
]

MOCK_USAGE_RESPONSE = {
    "usage_data": MOCK_USAGE_DATA,
    "total_items": 5,
    "api_id": "https://dropcountr.com/api/service_connections/12345/usage",
    "consumed_via_id": "https://dropcountr.com/api/service_connections/12345"
}