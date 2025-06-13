"""Test DropCountr setup process."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dropcountr.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import MOCK_CONFIG


@pytest.mark.usefixtures("bypass_get_data")
async def test_setup_entry(hass: HomeAssistant):
    """Test setting up and unloading the integration."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)

    # Test setup
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    # Ensure that the runtime data is available
    assert config_entry.runtime_data is not None
    assert config_entry.runtime_data.client is not None
    assert config_entry.runtime_data.usage_coordinator is not None

    # Test unload
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("error_on_connect")
async def test_setup_entry_connection_error(hass: HomeAssistant):
    """Test setup fails when connection to DropCountr fails."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
