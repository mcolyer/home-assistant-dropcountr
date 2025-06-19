# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Smart historical timestamp reporting for delayed water usage data
- Automatic detection of newly arrived historical data (1-3 day delays)
- Historical state_changed events with accurate original timestamps
- Deduplication logic to prevent duplicate historical state reporting
- Memory management with automatic cleanup of tracking data older than 60 days
- Comprehensive GitHub Actions CI/CD workflows for testing and validation
- Dependabot configuration for automated dependency updates
- Comprehensive .gitignore file for Python development

### Changed
- Updated Python requirement from >=3.13 to >=3.13.2 to match Home Assistant 2025.6.0
- Enhanced data coordinator with historical data processing capabilities
- Improved documentation with detailed algorithm explanations

### Technical Details
- Added persistent state tracking in `DropCountrUsageDataUpdateCoordinator`
- Implemented `_detect_new_historical_data()` for smart data detection
- Added `_fire_historical_state_events()` for historical timestamp reporting
- Created comprehensive test suite with 16+ test cases covering all scenarios
- Zero configuration required - works automatically without user intervention

### Development
- Added comprehensive test coverage for historical data functionality
- Configured Ruff linting with Home Assistant standards
- Set up automated CI/CD pipeline with GitHub Actions
- Enhanced development documentation in CLAUDE.md

## [0.1.0] - Initial Release

### Added
- Initial Home Assistant integration for DropCountr water monitoring service
- Support for multiple service connections per account
- Water usage sensors (daily, weekly, monthly totals)
- Irrigation usage tracking (gallons and events)
- Leak detection binary sensors
- Connection status monitoring
- Configuration flow with email/password authentication
- Home Assistant services for data retrieval:
  - `list_usage` - Get cached daily usage data
  - `get_service_connection` - Get service connection details
  - `get_hourly_usage` - Get hourly usage data with date range
- Integration with PyDropCountr library v0.1.2
- Daily polling strategy optimized for DropCountr's data update patterns
- Support for Home Assistant statistics and long-term data storage

### Technical Features
- Built on Home Assistant integration blueprint architecture
- Uses DataUpdateCoordinator pattern for efficient data management
- Supports multiple platforms: sensor and binary_sensor
- Entity naming follows Home Assistant conventions
- Comprehensive error handling and logging
- Development environment with Home Assistant debug configuration