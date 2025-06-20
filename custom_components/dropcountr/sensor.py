"""Sensor for displaying usage data from DropCountr."""

from datetime import date, timedelta
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

from .const import _LOGGER
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
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="weekly_total",
        translation_key="weekly_total",
        suggested_display_precision=2,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="monthly_total",
        translation_key="monthly_total",
        suggested_display_precision=2,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
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

    def _filter_recent_incomplete_data(
        self, usage_data: list[UsageData]
    ) -> list[UsageData]:
        """Filter out incomplete recent data to avoid reporting premature values.

        - Always filters today's data (typically incomplete)
        - Filters yesterday's data only if it's zero (incomplete)
        - Includes yesterday's data if non-zero (likely complete)

        This allows timely reporting of complete previous day data while avoiding
        premature reporting of incomplete data.
        """
        if not usage_data:
            return []

        today = _get_current_date()
        yesterday = today - timedelta(days=1)

        # Filter out incomplete data:
        # - Always filter today's data (typically incomplete)
        # - Filter yesterday's data only if it's zero (incomplete)
        # - Include yesterday's data if it has non-zero values (likely complete)
        filtered_data = []
        for data in usage_data:
            usage_date = data.start_date.date()
            if usage_date < yesterday:  # Include data from 2+ days ago
                filtered_data.append(data)
            elif (
                usage_date == yesterday and data.total_gallons > 0
            ):  # Include non-zero yesterday data
                filtered_data.append(data)

        return filtered_data

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
            _LOGGER.debug(
                f"No coordinator data available for monthly usage calculation on {self.service_connection_id}"
            )
            return 0.0

        usage_response = self.coordinator.data.get(self.service_connection_id)
        if not usage_response or not usage_response.usage_data:
            _LOGGER.debug(
                f"No usage data available for service {self.service_connection_id}"
            )
            return 0.0

        # Get the start of current month
        today = _get_current_date()
        month_start = date(today.year, today.month, 1)

        # Filter usage data for current month
        monthly_data = []
        for data in usage_response.usage_data:
            # Use the start_date property which is already a datetime object
            if hasattr(data, "start_date") and data.start_date:
                data_date = data.start_date.date()
                if data_date >= month_start:
                    monthly_data.append(data)

        # For monthly total, always use total gallons (not irrigation specific)
        total_usage = sum(data.total_gallons for data in monthly_data)

        _LOGGER.debug(
            f"Monthly usage calculation for service {self.service_connection_id}: "
            f"{len(monthly_data)} days in month, total: {total_usage:.2f} gallons"
        )

        return total_usage

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        sensor_key = self.entity_description.key

        if sensor_key == "monthly_total":
            return self._get_monthly_usage()

        # For daily sensors that will be updated by historical data,
        # avoid reporting 0 values for today/yesterday
        if sensor_key in ["irrigation_gallons", "irrigation_events", "daily_total"]:
            return self._get_latest_non_recent_value(sensor_key)
        elif sensor_key == "weekly_total":
            return self._get_aggregated_usage(7)

        return None

    def _get_latest_non_recent_value(self, sensor_key: str) -> StateType:
        """Get the latest value excluding today/yesterday to avoid 0 values for incomplete data."""
        if not self.coordinator.data:
            return None

        usage_response = self.coordinator.data.get(self.service_connection_id)
        if not usage_response or not usage_response.usage_data:
            return None

        # Filter out recent incomplete data (today/yesterday)
        filtered_data = self._filter_recent_incomplete_data(usage_response.usage_data)

        if not filtered_data:
            _LOGGER.debug(
                f"No filtered data available for {sensor_key} on service {self.service_connection_id}"
            )
            return None

        # Get the most recent filtered data
        latest_data = filtered_data[-1]

        sensor_value_map = {
            "irrigation_gallons": latest_data.irrigation_gallons,
            "irrigation_events": latest_data.irrigation_events,
            "daily_total": latest_data.total_gallons,
        }

        value = sensor_value_map.get(sensor_key)
        _LOGGER.debug(
            f"Sensor {sensor_key} for service {self.service_connection_id}: "
            f"filtered {len(usage_response.usage_data)} -> {len(filtered_data)} data points, "
            f"latest date: {latest_data.start_date.date()}, value: {value}"
        )

        return value

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
