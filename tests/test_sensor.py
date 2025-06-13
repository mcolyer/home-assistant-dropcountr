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

    # Test that sensors are created
    total_gallons = hass.states.get("sensor.dropcountr_test_service_connection_total_gallons")
    assert total_gallons is not None
    assert total_gallons.state == "120.3"  # Most recent usage data

    irrigation_gallons = hass.states.get("sensor.dropcountr_test_service_connection_irrigation_gallons")
    assert irrigation_gallons is not None
    assert irrigation_gallons.state == "50.1"

    irrigation_events = hass.states.get("sensor.dropcountr_test_service_connection_irrigation_events")
    assert irrigation_events is not None
    assert irrigation_events.state == "2.0"

    daily_total = hass.states.get("sensor.dropcountr_test_service_connection_daily_total")
    assert daily_total is not None
    assert daily_total.state == "120.3"  # Latest day total

    weekly_total = hass.states.get("sensor.dropcountr_test_service_connection_weekly_total")
    assert weekly_total is not None
    assert weekly_total.state == "270.8"  # Sum of both days