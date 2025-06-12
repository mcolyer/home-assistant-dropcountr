# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

- `scripts/setup` - Install Python dependencies
- `scripts/develop` - Start Home Assistant in debug mode with this custom component
- `scripts/lint` - Format and lint code using ruff

## Architecture

This is a Home Assistant custom component for Flume water monitoring devices. The integration is built on the integration_blueprint template structure:

- **Domain**: `flume` (defined in const.py and manifest.json)
- **Platforms**: Binary sensor and sensor platforms
- **Authentication**: Uses PyFlume library with OAuth2 flow via config_flow.py
- **Data Coordination**: FlumeNotificationDataUpdateCoordinator handles API polling with rate limiting (120 queries/hour)
- **Configuration**: Config entry-based setup with OAuth2 credentials

## Key Components

- `coordinator.py` - Data update coordinators for device and notification data
- `config_flow.py` - OAuth2 configuration flow for user setup
- `entity.py` - Base entity classes for Flume devices
- `sensor.py` - Water usage sensors and device metrics
- `binary_sensor.py` - Connection status and alert sensors
- `services.yaml` - Service definitions for list_notifications service

## Development Environment

The integration includes a development container setup with Home Assistant pre-configured. The `config/configuration.yaml` enables debug logging for the custom component. The PYTHONPATH is modified during development to include the custom_components directory.

## Testing

Run lint checks before committing: `scripts/lint`