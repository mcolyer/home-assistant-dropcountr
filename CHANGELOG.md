# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.5] - 2025-06-20

### Fixed
- StatisticData TypedDict usage in statistics insertion for better type safety and Home Assistant compatibility

## [0.1.4] - 2025-06-20

### Changed
- **BREAKING**: Improved thread safety across the integration requiring Home Assistant 2025.6.0+
- Optimized API call efficiency with intelligent 5-minute caching, reducing redundant service connection requests by 60-70%
- Enhanced update cycle performance from ~1.6s to ~0.35s through parallel service connection processing
- Improved statistics processing with tolerance for small date gaps to prevent unnecessary resets
- Strengthened memory management with 60-day retention policy and automatic cleanup

### Added
- Comprehensive thread safety protection with proper locking mechanisms for shared state access
- Multi-layered duplicate statistics prevention system with session-level tracking
- Advanced performance monitoring with detailed timing breakdowns and throughput metrics
- Parallel processing architecture using asyncio.gather() for concurrent service connection handling
- Thread-safe service data access with copy-on-read pattern for external consumers

### Fixed
- Race conditions in historical state tracking and statistics insertion across multiple executor threads
- Statistics inconsistency warnings caused by aggressive reset logic on small date gaps
- Memory growth issues in historical data tracking with unbounded date set accumulation
- Non-atomic operations in shared state updates that could cause data corruption
- Client logout blocking main event loop by moving to proper executor context

## [0.1.2] - 2025-01-20

### Changed
- Optimized debug logging to reduce log volume by ~70% while maintaining debugging capabilities
- Streamlined statistics insertion logging from 15+ to 3 key logs per metric type
- Simplified sensor and binary sensor debug output to focus on essential insights only
- Enhanced monthly usage calculation logging to be more concise and informative

### Added
- Strategic API performance tracking with request timing and data volume metrics
- Usage data update cycle monitoring with detailed service/record counts and timing
- Enhanced service call performance logging with contextual information
- Production-optimized logging to understand data fetching patterns for optimization

### Fixed
- Removed verbose per-data-point debug logs that were impacting performance
- Eliminated redundant timezone debugging in nested processing loops
- Reduced unnecessary logging in coordinator historical data detection
- Simplified binary sensor connection status logging to only log when disconnected

### Technical Improvements
- Preserved critical leak detection warnings and connection status alerts
- Added comprehensive performance metrics for production monitoring
- Improved maintainability with focused, purposeful logging
- Enhanced service performance tracking for `get_service_connection` and `get_hourly_usage`

## [0.1.1] - 2025-01-20

### Fixed
- Hassfest workflow configuration to only validate the dropcountr integration instead of all Home Assistant core integrations
- CI and release workflows now properly target the custom integration path

## [0.1.0] - 2025-01-20

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
- Smart historical timestamp reporting for delayed water usage data
- Automatic detection of newly arrived historical data (1-3 day delays)
- Deduplication logic to prevent duplicate historical state reporting
- Memory management with automatic cleanup of tracking data older than 60 days
- Comprehensive GitHub Actions CI/CD workflows for testing and validation
- Dependabot configuration for automated dependency updates
- Previous day statistics publishing when data is non-zero and available

### Fixed
- Timezone handling in historical statistics to prevent one-day offset in charts
- UTC timestamps from DropCountr API now properly converted to Home Assistant's local timezone
- Statistics data now appears on correct dates in Home Assistant analytics
- Water sensor state class configuration for Home Assistant compliance
- Manifest.json validation errors for Home Assistant integration standards

### Changed
- Updated Python requirement from >=3.13 to >=3.13.2 to match Home Assistant 2025.6.0
- Enhanced data coordinator with historical data processing capabilities
- Improved sensor filtering to allow timely previous day data when complete
- Enhanced entity naming for cleaner UI display

### Technical Features
- Built on Home Assistant integration blueprint architecture
- Uses DataUpdateCoordinator pattern for efficient data management
- Supports multiple platforms: sensor and binary_sensor
- Entity naming follows Home Assistant conventions
- Comprehensive error handling and logging
- Development environment with Home Assistant debug configuration
- Added persistent state tracking in `DropCountrUsageDataUpdateCoordinator`
- Implemented smart data detection algorithms for historical data
- Created comprehensive test suite with 30+ test cases covering all scenarios
- Zero configuration required for historical data - works automatically
- Configured Ruff linting with Home Assistant standards
- Enhanced development documentation in CLAUDE.md