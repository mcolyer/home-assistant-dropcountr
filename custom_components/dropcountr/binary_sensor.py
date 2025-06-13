"""DropCountr binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    DropCountrConfigEntry,
    DropCountrUsageDataUpdateCoordinator,
)
from .entity import DropCountrEntity

DROPCOUNTR_BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="leak_detected",
        translation_key="leak_detected",
        device_class=BinarySensorDeviceClass.MOISTURE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="connection_status",
        translation_key="connection_status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DropCountrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up DropCountr binary sensors."""
    dropcountr_domain_data = config_entry.runtime_data
    client = dropcountr_domain_data.client

    # Get service connections
    service_connections = await hass.async_add_executor_job(
        client.list_service_connections
    )

    if not service_connections:
        return

    entities: list[DropCountrBinarySensor] = []

    for service_connection in service_connections:
        coordinator = DropCountrUsageDataUpdateCoordinator(
            hass=hass,
            config_entry=config_entry,
            client=client,
        )

        entities.extend(
            [
                DropCountrBinarySensor(
                    coordinator=coordinator,
                    description=description,
                    service_connection_id=service_connection.id,
                    service_connection_name=service_connection.name,
                    service_connection_address=service_connection.address,
                )
                for description in DROPCOUNTR_BINARY_SENSORS
            ]
        )

    async_add_entities(entities)


class DropCountrBinarySensor(
    DropCountrEntity[DropCountrUsageDataUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor for DropCountr."""

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        sensor_key = self.entity_description.key

        if sensor_key == "leak_detected":
            return self._get_leak_status()
        elif sensor_key == "connection_status":
            return self._get_connection_status()

        return False

    def _get_leak_status(self) -> bool:
        """Check if there's a leak detected."""
        if not self.coordinator.data:
            return False

        usage_response = self.coordinator.data.get(self.service_connection_id)
        if not usage_response or not usage_response.usage_data:
            return False

        # Check the most recent usage data for leak status
        latest_data = usage_response.usage_data[-1]
        return latest_data.is_leaking

    def _get_connection_status(self) -> bool:
        """Check if the service connection is active."""
        if not self.coordinator.data:
            return False

        # If we have recent data, consider the connection active
        usage_response = self.coordinator.data.get(self.service_connection_id)
        return usage_response is not None and len(usage_response.usage_data) > 0
