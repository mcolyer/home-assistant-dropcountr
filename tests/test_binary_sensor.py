"""Test DropCountr binary sensor platform."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dropcountr.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import MOCK_CONFIG


@pytest.mark.usefixtures("bypass_get_data")
async def test_binary_sensors(hass: HomeAssistant) -> None:
    """Test setting up creates the binary sensors."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Test leak detection sensor
    leak_detected = hass.states.get(
        "binary_sensor.test_service_connection_leak_detected"
    )
    assert leak_detected is not None
    assert leak_detected.state == "off"  # Mock data shows no leak

    # Test connection status sensor
    connection_status = hass.states.get(
        "binary_sensor.test_service_connection_connection_status"
    )
    assert connection_status is not None
    assert connection_status.state == "on"  # Should be on since we have data
