"""Platform for shared base classes for sensors."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    DropCountrServiceConnectionDataUpdateCoordinator,
    DropCountrUsageDataUpdateCoordinator,
)


class DropCountrEntity[
    _DropCountrCoordinatorT: DropCountrServiceConnectionDataUpdateCoordinator
    | DropCountrUsageDataUpdateCoordinator
](CoordinatorEntity[_DropCountrCoordinatorT]):
    """Base entity class."""

    _attr_attribution = "Data provided by DropCountr API"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: _DropCountrCoordinatorT,
        description: EntityDescription,
        service_connection_id: int,
        service_connection_name: str,
        service_connection_address: str,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator)
        self.entity_description = description
        self.service_connection_id = service_connection_id

        self._attr_unique_id = f"{description.key}_{service_connection_id}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(service_connection_id))},
            manufacturer="DropCountr",
            model="Water Meter",
            name=f"DropCountr {service_connection_name}",
            configuration_url="https://dropcountr.com",
        )

        # Store additional service connection info
        self.service_connection_name = service_connection_name
        self.service_connection_address = service_connection_address

    async def async_added_to_hass(self) -> None:
        """Request an update when added."""
        await super().async_added_to_hass()
        # We do not ask for an update with async_add_entities()
        # because it will update disabled entities
        await self.coordinator.async_request_refresh()
