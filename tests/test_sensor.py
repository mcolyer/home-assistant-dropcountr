"""Test DropCountr sensor platform."""

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dropcountr.const import DOMAIN

from .const import MOCK_CONFIG


@pytest.mark.usefixtures("bypass_get_data")
async def test_sensors(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Test that sensors are created with device class-based entity IDs
    total_gallons = hass.states.get("sensor.dropcountr_test_service_connection_water")
    assert total_gallons is not None
    assert total_gallons.state == "455.3850376152"  # 120.3 gallons in liters

    irrigation_gallons = hass.states.get("sensor.dropcountr_test_service_connection_water_2")
    assert irrigation_gallons is not None
    assert irrigation_gallons.state == "189.6491303784"  # 50.1 gallons in liters

    irrigation_events = hass.states.get("sensor.dropcountr_test_service_connection_none")
    assert irrigation_events is not None
    assert irrigation_events.state == "2.0"

    daily_total = hass.states.get("sensor.dropcountr_test_service_connection_water_3")
    assert daily_total is not None
    assert daily_total.state == "455.3850376152"  # Latest day total in liters

    weekly_total = hass.states.get("sensor.dropcountr_test_service_connection_water_4")
    assert weekly_total is not None
    assert weekly_total.state == "2842.0871674272"  # Sum of last 7 days in liters

    monthly_total = hass.states.get("sensor.dropcountr_test_service_connection_water_5")
    assert monthly_total is not None
    # June total (when test runs in current month): varies based on test date
    # Just verify it's a valid number and not None
    assert monthly_total.state is not None
    assert float(monthly_total.state) >= 0