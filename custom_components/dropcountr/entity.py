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
    DropCountrCoordinatorT: DropCountrServiceConnectionDataUpdateCoordinator
    | DropCountrUsageDataUpdateCoordinator
](CoordinatorEntity[DropCountrCoordinatorT]):
    """Base entity class."""

    _attr_attribution = "Data provided by DropCountr API"
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: DropCountrCoordinatorT,
        description: EntityDescription,
        service_connection_id: int,
        service_connection_name: str,
        service_connection_address: str,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator)
        self.entity_description = description
        self.service_connection_id = service_connection_id

        # Create a comprehensive unique ID that includes domain, service connection, and description key
        self._attr_unique_id = f"{DOMAIN}_{service_connection_id}_{description.key}"

        # Store clean names for entity generation
        safe_name = service_connection_name.lower().replace(" ", "_").replace("-", "_")

        # Store service connection name for sensor naming
        self.safe_service_connection_name = safe_name

        # Create a user-friendly device name
        if service_connection_address:
            # Use the first part of the address as a more readable name
            address_parts = service_connection_address.split(",")
            location_name = (
                address_parts[0].strip() if address_parts else service_connection_name
            )
            device_name = f"DropCountr Water Meter ({location_name})"
        else:
            device_name = f"DropCountr {service_connection_name}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(service_connection_id))},
            manufacturer="DropCountr",
            model="Water Meter",
            name=device_name,
            configuration_url="https://dropcountr.com",
            suggested_area=service_connection_address.split(",")[0]
            if service_connection_address
            else None,
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
