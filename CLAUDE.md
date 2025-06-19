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
- **Data Coordination**: DropCountrUsageDataUpdateCoordinator handles API polling with reasonable intervals (daily for usage data)
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
- **Python Version**: Uses Python 3.13.2+ (required by Home Assistant 2025.6.0) managed by uv for compatibility with latest HA versions
- **Polling Strategy**: Usage data updates daily (not real-time), so coordinator polls once per day to reduce API load while maintaining data freshness
- **CI/CD**: GitHub Actions workflows automatically run tests, linting, and Hassfest validation on pull requests
- **Code Quality**: Ruff linting configured with Home Assistant standards, ignoring overly strict rules (TRY300, TRY301)
- **Documentation**: CHANGELOG.md tracks all notable changes following Keep a Changelog format

## Historical Data Reporting

The integration includes smart historical timestamp reporting to handle DropCountr's delayed data reporting (typically 1-3 days).

### Key Features

- **Automatic Detection**: Identifies newly arrived historical data during daily polling
- **Accurate Timestamps**: Fires `state_changed` events with original historical timestamps
- **Deduplication**: Prevents duplicate reporting of the same historical data
- **Memory Management**: Automatically cleans up tracking data older than 60 days
- **Zero Configuration**: Works automatically without user intervention

### Algorithm

1. **State Tracking**: Maintains a set of previously seen usage dates per service connection
2. **New Data Detection**: Compares current API response with tracked dates to identify new entries
3. **Historical Filtering**: Only processes data older than 1 day as "historical"
4. **Statistics Insertion**: Inserts historical usage data as external statistics using Home Assistant's statistics system
5. **State Update**: Updates tracking state with all current dates

### Implementation

- `coordinator.py`: Core historical data processing logic using `async_add_external_statistics`
- `const.py`: Historical data tracking constants
- `tests/test_historical_data.py`: Comprehensive test suite covering all scenarios

The implementation uses Home Assistant's external statistics system to store historical water usage data. This allows the data to:
- Persist across integration restarts
- Be displayed in Home Assistant's statistics graphs
- Maintain cumulative sums for long-term tracking
- Integrate with Home Assistant's analytics capabilities

Statistics are created for three metrics per service connection:
- **Total Water Usage**: Daily total gallons consumed
- **Irrigation Water Usage**: Daily irrigation gallons consumed  
- **Irrigation Events**: Daily count of irrigation events

The implementation gracefully handles failures (falls back to normal operation if statistics insertion fails).

## Home Assistant Development Best Practices

Based on development experience with this integration, here are key learnings for Home Assistant custom components:

### Statistics System Integration

**When to use Home Assistant's statistics system:**
- For historical data that needs to persist across restarts
- When you want data to appear in HA's built-in analytics/graphs
- For cumulative tracking with proper sum calculations
- When integrating utility-type data (energy, water, gas usage)

**Implementation patterns:**
- Use `async_add_external_statistics()` with proper `StatisticData` and `StatisticMetaData`
- Always include graceful error handling for statistics failures
- Declare `recorder` in `after_dependencies` in manifest.json
- Mock statistics calls in tests to avoid database dependencies

### Sensor State Classes

**Critical requirement:** Water sensors with `device_class="water"` MUST use:
- `state_class=SensorStateClass.TOTAL_INCREASING` (for cumulative totals)
- `state_class=SensorStateClass.TOTAL` (for resetting totals)
- **Never** `state_class=SensorStateClass.MEASUREMENT` (causes validation errors)

### Event Handling Patterns

**Avoid manual state_changed events:**
- Never manually fire `state_changed` events - they require specific structure (`old_state`/`new_state`)
- Use custom events for notifications: `hass.bus.async_fire("custom_event_name", data)`
- For historical data, prefer statistics system over events

### Testing Considerations

**Essential test patterns:**
- Mock all external dependencies in `conftest.py` 
- Use `bypass_get_data` fixture pattern for API mocking
- Mock database/recorder calls for statistics testing
- Always test state class validation in sensor tests

### Manifest Dependencies

**Dependency declaration rules:**
- Use `dependencies` for hard requirements (integration fails without them)
- Use `after_dependencies` for soft requirements (integration works without them)
- Always declare component usage to avoid validation errors
- Example: `"after_dependencies": ["recorder"]` for statistics usage

### Error Handling Philosophy

**Graceful degradation pattern:**
- Wrap advanced features (like statistics) in try-catch blocks
- Log warnings but continue normal operation on failures
- Ensure core functionality (sensors/entities) always works
- Use this pattern for optional integrations with HA subsystems

### Code Quality Standards

**Home Assistant validation requirements:**
- All sensor state classes must match device classes
- All component dependencies must be declared
- Use proper typing and async patterns
- Follow HA's entity naming conventions

These patterns ensure robust integrations that work reliably in diverse Home Assistant environments.

## Project Maintenance

### Changelog Management
All notable changes are documented in `CHANGELOG.md` following the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format:
- **Added** - New features
- **Changed** - Changes in existing functionality  
- **Deprecated** - Soon-to-be removed features
- **Removed** - Removed features
- **Fixed** - Bug fixes
- **Security** - Vulnerability fixes

### Development Workflow
1. **Feature Development**: Create feature branch from `main`
2. **Testing**: Ensure all tests pass with `scripts/test`
3. **Code Quality**: Run `scripts/lint` to ensure code standards
4. **Documentation**: Update CLAUDE.md and CHANGELOG.md as needed
5. **Pull Request**: Create PR with detailed description and testing notes
6. **CI Validation**: GitHub Actions automatically validates code quality and integration standards
7. **Review & Merge**: Code review and merge to main

### Release Process
- Update version in `manifest.json` and `pyproject.toml`
- Move unreleased changes in CHANGELOG.md to new version section
- Create GitHub release with changelog notes
- GitHub Actions automatically validates release builds