# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

- `scripts/setup` - Install Python dependencies and dev dependencies using uv
- `scripts/develop` - Start Home Assistant in debug mode with this custom component
- `scripts/lint` - Format and lint code using ruff
- `scripts/test` - Run pytest test suite

## Architecture

This is a Home Assistant custom component for DropCountr water monitoring service. The integration is built on the integration_blueprint template structure:

- **Domain**: `dropcountr` (defined in const.py and manifest.json)
- **Platforms**: Binary sensor and sensor platforms
- **Authentication**: Uses PyDropCountr library with simple email/password login via config_flow.py
- **Data Coordination**: DropCountrUsageDataUpdateCoordinator handles API polling with reasonable intervals (15 minutes for usage data)
- **Configuration**: Config entry-based setup with email/password credentials

## Key Components

- `coordinator.py` - Data update coordinators for usage data from service connections
- `config_flow.py` - Simple email/password configuration flow for user setup with enhanced validation
- `entity.py` - Base entity classes for DropCountr service connections
- `sensor.py` - Water usage sensors (total gallons, irrigation gallons, events, daily/weekly totals)
- `binary_sensor.py` - Leak detection and connection status sensors
- `services.yaml` - Service definitions for all available services

## Data Model

DropCountr integration works with:
- **Service Connections**: Water meter connections associated with a user account
- **Usage Data**: Daily water usage data including total gallons, irrigation gallons, irrigation events, and leak detection status
- **Authentication**: Simple email/password login with enhanced validation using `is_logged_in()` check

## PyDropCountr API Coverage

The integration utilizes all major PyDropCountr APIs:

### Authentication APIs
- ✅ `login(email, password)` - Used for initial authentication
- ✅ `logout()` - Used during integration unload
- ✅ `is_logged_in()` - Used for authentication verification in setup and config flow

### Service Connection APIs  
- ✅ `list_service_connections()` - Used by coordinator and config flow validation
- ✅ `get_service_connection(service_id)` - Available via `get_service_connection` service

### Usage Data APIs
- ✅ `get_usage(service_connection_id, start_date, end_date, period='day')` - Used by coordinator for daily data
- ✅ `get_usage(..., period='hour')` - Available via `get_hourly_usage` service for granular data

## Available Services

The integration provides three Home Assistant services:

1. **list_usage** - Returns cached daily usage data for all service connections
2. **get_service_connection** - Retrieves detailed information for a specific service connection
3. **get_hourly_usage** - Fetches hourly granularity usage data with optional date range

## Development Environment

The integration includes a development container setup with Home Assistant pre-configured. The `config/configuration.yaml` enables debug logging for the custom component. The PYTHONPATH is modified during development to include the custom_components directory.

## Testing

The integration includes a comprehensive test suite using pytest with Home Assistant custom component testing framework:

- `scripts/test` - Run full test suite
- `scripts/lint` - Run ruff linting and formatting
- Test files are in `tests/` directory with fixtures in `conftest.py`
- Tests use `MockConfigEntry` and bypass actual API calls with `bypass_get_data` fixture
- Entity naming follows Home Assistant conventions (device_class determines entity IDs)

## Development Notes

- **Coordinator Sharing**: Both sensor and binary_sensor platforms use the shared coordinator from `runtime_data` instead of creating new instances
- **Entity Naming**: Home Assistant generates entity IDs using device_class (e.g., "moisture", "connectivity") rather than the entity key
- **Manifest Requirements**: HA 2025.6.0+ requires a "version" field in manifest.json
- **Python Version**: Uses Python 3.13.3 managed by uv for compatibility with latest HA versions