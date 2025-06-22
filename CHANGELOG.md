# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.7] - 2025-01-03

### Changed
- **BREAKING**: Updated to PyDropCountr 1.0.0 with timezone-aware datetime handling
- **Timezone Support**: DropCountr client now uses Home Assistant's configured timezone for proper local time handling
- **API Compatibility**: All datetime objects from PyDropCountr are now timezone-aware in local time instead of incorrectly parsed as UTC

### Added
- **Hourly External Statistics**: Switched from daily to hourly data collection for more granular water usage analytics
- More frequent polling (every 4 hours) to capture new hourly data timely
- Enhanced leak detection and irrigation monitoring with hourly granularity

### Technical Improvements
- **Statistics Collection**: Changed from daily rollups to hourly data points for external statistics
- **Data Retention**: Reduced from 60-day to 7-day retention window for hourly timestamps (168 hours max per service)
- **API Data Fetching**: Modified coordinator to request hourly data (`period="hour"`) instead of daily
- **Historical Data Logic**: Updated to consider data historical after 2+ hours instead of 1+ days
- **Polling Frequency**: Increased from daily to every 4 hours for timely hourly data capture
- Optimized data volume management with 7-day hourly window (~168 data points per service)
- Enhanced memory management with automatic cleanup of hourly timestamps older than 7 days
- Maintained thread safety and performance optimizations for hourly data processing
- Uses existing statistic IDs for seamless transition from daily to hourly data
- Updated comprehensive test suite to validate hourly data collection and processing

## [0.1.6] - 2025-06-20

### Fixed
- **CRITICAL**: Statistics reset logic that was causing data corruption and false warnings
- Removed unnecessary reset logic that reprocessed all historical data on every update cycle
- Eliminated recurring "Statistics inconsistency detected" warnings that appeared on every update
- Data corruption from duplicate statistics processing that added same values multiple times to cumulative sums
- Performance issues from unnecessary reprocessing of 44+ historical records per update cycle

### Changed
- Simplified statistics processing logic by removing 25+ lines of complex and unnecessary reset code
- Enhanced debug logging to show continuation vs fresh starts for better troubleshooting
- Improved timestamp-based filtering which correctly handles all date gap scenarios without corruption

### Technical Improvements
- Statistics now properly continue from last processed timestamp instead of resetting
- Cumulative sums maintain integrity across updates without duplicate value additions
- Cleaner, more reliable codebase with simplified timestamp handling and comparison logic
- Better data integrity protection in Home Assistant's statistics database

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