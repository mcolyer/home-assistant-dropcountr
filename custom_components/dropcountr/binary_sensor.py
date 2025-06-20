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

from .const import _LOGGER
from .coordinator import DropCountrConfigEntry, DropCountrUsageDataUpdateCoordinator
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
    coordinator = dropcountr_domain_data.usage_coordinator

    # Get service connections
    service_connections = await hass.async_add_executor_job(
        dropcountr_domain_data.client.list_service_connections
    )

    if not service_connections:
        return

    entities: list[DropCountrBinarySensor] = []

    for service_connection in service_connections:
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

    def __init__(self, *args, **kwargs):
        """Initialize the binary sensor."""
        super().__init__(*args, **kwargs)

        # Use concise names
        name_mapping = {
            "leak_detected": "Leak Detected",
            "connection_status": "Connection Status",
        }
        self._attr_name = name_mapping.get(
            self.entity_description.key,
            self.entity_description.key.replace("_", " ").title(),
        )

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
        leak_status = latest_data.is_leaking

        if leak_status:
            _LOGGER.warning(
                f"LEAK DETECTED on service {self.service_connection_id} (date: {latest_data.start_date.date()})"
            )

        return leak_status

    def _get_connection_status(self) -> bool:
        """Check if the service connection is active."""
        if not self.coordinator.data:
            return False

        # If we have recent data, consider the connection active
        usage_response = self.coordinator.data.get(self.service_connection_id)
        is_connected = usage_response is not None and len(usage_response.usage_data) > 0

        # Only log connection issues (when disconnected)
        if not is_connected:
            _LOGGER.debug(
                f"Service {self.service_connection_id} appears disconnected (no recent data)"
            )

        return is_connected
