"""Sensor for displaying usage data from DropCountr."""

from datetime import date
from typing import Any

from pydropcountr import UsageData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import DropCountrConfigEntry, DropCountrUsageDataUpdateCoordinator
from .entity import DropCountrEntity


def _get_current_date() -> date:
    """Get current date - helper function for easier testing."""
    return date.today()


DROPCOUNTR_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="irrigation_gallons",
        translation_key="irrigation_gallons",
        suggested_display_precision=2,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="irrigation_events",
        translation_key="irrigation_events",
        suggested_display_precision=0,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="daily_total",
        translation_key="daily_total",
        suggested_display_precision=2,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="weekly_total",
        translation_key="weekly_total",
        suggested_display_precision=2,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="monthly_total",
        translation_key="monthly_total",
        suggested_display_precision=2,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DropCountrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the DropCountr sensor."""

    dropcountr_domain_data = config_entry.runtime_data
    coordinator = dropcountr_domain_data.usage_coordinator

    # Get service connections
    service_connections = await hass.async_add_executor_job(
        dropcountr_domain_data.client.list_service_connections
    )

    if not service_connections:
        return

    entities: list[DropCountrSensor] = []

    for service_connection in service_connections:
        entities.extend(
            [
                DropCountrSensor(
                    coordinator=coordinator,
                    description=description,
                    service_connection_id=service_connection.id,
                    service_connection_name=service_connection.name,
                    service_connection_address=service_connection.address,
                )
                for description in DROPCOUNTR_SENSORS
            ]
        )

    async_add_entities(entities)


class DropCountrSensor(
    DropCountrEntity[DropCountrUsageDataUpdateCoordinator], SensorEntity
):
    """Representation of the DropCountr sensor."""

    def __init__(self, *args, **kwargs):
        """Initialize the sensor."""
        super().__init__(*args, **kwargs)

        # Set custom entity_id using the key for clarity
        self.entity_id = (
            f"sensor.{self.safe_service_connection_name}_{self.entity_description.key}"
        )

        # Use concise names from translation strings
        name_mapping = {
            "irrigation_gallons": "Daily Irrigation",
            "irrigation_events": "Irrigation Events",
            "daily_total": "Daily Total",
            "weekly_total": "Weekly Total",
            "monthly_total": "Monthly Total",
        }
        self._attr_name = name_mapping.get(
            self.entity_description.key,
            self.entity_description.key.replace("_", " ").title(),
        )

    def _get_latest_usage_data(self) -> UsageData | None:
        """Get the latest usage data for this service connection."""
        if not self.coordinator.data:
            return None

        usage_response = self.coordinator.data.get(self.service_connection_id)
        if not usage_response or not usage_response.usage_data:
            return None

        # Return the most recent usage data
        return usage_response.usage_data[-1]

    def _get_aggregated_usage(self, days: int) -> float:
        """Get aggregated usage for the specified number of days."""
        if not self.coordinator.data:
            return 0.0

        usage_response = self.coordinator.data.get(self.service_connection_id)
        if not usage_response or not usage_response.usage_data:
            return 0.0

        # Sum up the specified number of most recent days
        recent_data = (
            usage_response.usage_data[-days:]
            if days <= len(usage_response.usage_data)
            else usage_response.usage_data
        )

        if self.entity_description.key == "irrigation_gallons":
            return sum(data.irrigation_gallons for data in recent_data)
        else:
            return sum(data.total_gallons for data in recent_data)

    def _get_monthly_usage(self) -> float:
        """Get usage for the current month to date."""
        if not self.coordinator.data:
            return 0.0

        usage_response = self.coordinator.data.get(self.service_connection_id)
        if not usage_response or not usage_response.usage_data:
            return 0.0

        # Get the start of current month
        today = _get_current_date()
        month_start = date(today.year, today.month, 1)

        # Debug logging to understand the data
        from .const import _LOGGER
        _LOGGER.warning(f"Monthly calculation for service {self.service_connection_id}:")
        _LOGGER.warning(f"Today: {today}, Month start: {month_start}")
        _LOGGER.warning(f"Total usage data entries: {len(usage_response.usage_data)}")

        # Check if we have data spanning the full month
        if usage_response.usage_data:
            earliest_date = min(data.start_date.date() for data in usage_response.usage_data if hasattr(data, "start_date") and data.start_date)
            latest_date = max(data.start_date.date() for data in usage_response.usage_data if hasattr(data, "start_date") and data.start_date)
            _LOGGER.warning(f"Data range: {earliest_date} to {latest_date}")

        # Filter usage data for current month
        monthly_data = []
        total_all_data = 0.0
        for data in usage_response.usage_data:
            total_all_data += data.total_gallons
            # Use the start_date property which is already a datetime object
            if hasattr(data, "start_date") and data.start_date:
                data_date = data.start_date.date()
                _LOGGER.warning(f"Data entry: {data_date}, gallons: {data.total_gallons}, in month: {data_date >= month_start}")
                if data_date >= month_start:
                    monthly_data.append(data)

        monthly_total = sum(data.total_gallons for data in monthly_data)
        _LOGGER.warning(f"Monthly data entries: {len(monthly_data)}")
        _LOGGER.warning(f"Monthly total: {monthly_total} gallons")
        _LOGGER.warning(f"All data total: {total_all_data} gallons")
        _LOGGER.warning(f"Website shows: 9,291 gallons vs our calculation: {monthly_total} gallons")

        # For monthly total, always use total gallons (not irrigation specific)
        return monthly_total

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        sensor_key = self.entity_description.key
        latest_data = self._get_latest_usage_data()

        if sensor_key == "monthly_total":
            return self._get_monthly_usage()

        if not latest_data:
            return None

        if sensor_key == "irrigation_gallons":
            return latest_data.irrigation_gallons
        elif sensor_key == "irrigation_events":
            return latest_data.irrigation_events
        elif sensor_key == "daily_total":
            return self._get_aggregated_usage(1)
        elif sensor_key == "weekly_total":
            return self._get_aggregated_usage(7)

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        latest_data = self._get_latest_usage_data()

        if not latest_data:
            return None

        return {
            "service_connection_id": self.service_connection_id,
            "service_connection_name": self.service_connection_name,
            "service_connection_address": self.service_connection_address,
            "period_start": latest_data.start_date.isoformat() if latest_data else None,
            "period_end": latest_data.end_date.isoformat() if latest_data else None,
            "is_leaking": latest_data.is_leaking if latest_data else None,
        }
