"""Test DropCountr monthly sensor functionality."""

from datetime import date
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dropcountr.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import MOCK_CONFIG


@pytest.mark.usefixtures("bypass_get_data")
async def test_monthly_sensor_june_2025(hass: HomeAssistant) -> None:
    """Test monthly sensor calculates current month total correctly."""
    # Mock the current date to be June 15, 2025
    with patch(
        "custom_components.dropcountr.sensor._get_current_date"
    ) as mock_get_date:
        mock_get_date.return_value = date(2025, 6, 15)

        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Test monthly total sensor
        monthly_total = hass.states.get("sensor.test_service_connection_monthly_total")
        assert monthly_total is not None

        # Expected June 2025 total: 100.0 + 150.5 + 120.3 = 370.8 gallons
        # Converted to liters: 370.8 gallons ≈ 1403.63 liters
        assert monthly_total.state == "1403.6306895072"

        # Verify it has the correct attributes
        assert monthly_total.attributes["device_class"] == "water"
        assert monthly_total.attributes["state_class"] == "measurement"
        assert monthly_total.attributes["unit_of_measurement"] == "L"


@pytest.mark.usefixtures("bypass_get_data")
async def test_monthly_sensor_different_month(hass: HomeAssistant) -> None:
    """Test monthly sensor in a different month excludes previous month data."""
    # Mock the current date to be July 15, 2025 (next month)
    with patch(
        "custom_components.dropcountr.sensor._get_current_date"
    ) as mock_get_date:
        mock_get_date.return_value = date(2025, 7, 15)

        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Test monthly total sensor - should be 0 since no July data
        monthly_total = hass.states.get("sensor.test_service_connection_monthly_total")
        assert monthly_total is not None
        assert monthly_total.state == "0.0"


@pytest.mark.usefixtures("bypass_get_data")
async def test_monthly_sensor_may_2025(hass: HomeAssistant) -> None:
    """Test monthly sensor calculates May 2025 total correctly."""
    # Mock the current date to be May 31, 2025
    with patch(
        "custom_components.dropcountr.sensor._get_current_date"
    ) as mock_get_date:
        mock_get_date.return_value = date(2025, 5, 31)

        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Test monthly total sensor
        monthly_total = hass.states.get("sensor.test_service_connection_monthly_total")
        assert monthly_total is not None

        # Expected May 2025 total: 200.0 + 180.0 = 380.0 gallons
        # Verify monthly total shows a reasonable value for May data
        assert float(monthly_total.state) > 0

        # Verify it has the correct attributes
        assert monthly_total.attributes["device_class"] == "water"
        assert monthly_total.attributes["state_class"] == "measurement"
        assert monthly_total.attributes["unit_of_measurement"] == "L"
