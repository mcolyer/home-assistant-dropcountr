"""The DropCountr component."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.const import Platform

DOMAIN = "dropcountr"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]

DEFAULT_NAME = "DropCountr Sensor"

# DropCountr API - reasonable polling intervals
# Usage data typically updates once daily, so check once per day
USAGE_SCAN_INTERVAL = timedelta(days=1)
# Service connections rarely change, so check once per day
SERVICE_CONNECTION_SCAN_INTERVAL = timedelta(days=1)

_LOGGER = logging.getLogger(__package__)

# Service connection data keys
KEY_SERVICE_CONNECTION_ID = "id"
KEY_SERVICE_CONNECTION_NAME = "name"
KEY_SERVICE_CONNECTION_ADDRESS = "address"
KEY_SERVICE_CONNECTION_ACCOUNT = "account_number"
KEY_SERVICE_CONNECTION_STATUS = "status"
KEY_SERVICE_CONNECTION_METER = "meter_serial"

# Usage data keys
KEY_USAGE_TOTAL_GALLONS = "total_gallons"
KEY_USAGE_IRRIGATION_GALLONS = "irrigation_gallons"
KEY_USAGE_IRRIGATION_EVENTS = "irrigation_events"
KEY_USAGE_IS_LEAKING = "is_leaking"
KEY_USAGE_DURING = "during"
