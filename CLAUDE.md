# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

- `scripts/setup` - Install Python dependencies
- `scripts/develop` - Start Home Assistant in debug mode with this custom component
- `scripts/lint` - Format and lint code using ruff

## Architecture

This is a Home Assistant custom component for DropCountr water monitoring service. The integration is built on the integration_blueprint template structure:

- **Domain**: `dropcountr` (defined in const.py and manifest.json)
- **Platforms**: Binary sensor and sensor platforms
- **Authentication**: Uses PyDropCountr library with simple email/password login via config_flow.py
- **Data Coordination**: DropCountrUsageDataUpdateCoordinator handles API polling with reasonable intervals (15 minutes for usage data)
- **Configuration**: Config entry-based setup with email/password credentials

## Key Components

- `coordinator.py` - Data update coordinators for usage data from service connections
- `config_flow.py` - Simple email/password configuration flow for user setup
- `entity.py` - Base entity classes for DropCountr service connections
- `sensor.py` - Water usage sensors (total gallons, irrigation gallons, events, daily/weekly totals)
- `binary_sensor.py` - Leak detection and connection status sensors
- `services.yaml` - Service definitions for list_usage service

## Data Model

DropCountr integration works with:
- **Service Connections**: Water meter connections associated with a user account
- **Usage Data**: Daily water usage data including total gallons, irrigation gallons, irrigation events, and leak detection status
- **Authentication**: Simple email/password login (no OAuth2 required)

## Development Environment

The integration includes a development container setup with Home Assistant pre-configured. The `config/configuration.yaml` enables debug logging for the custom component. The PYTHONPATH is modified during development to include the custom_components directory.

## Testing

Run lint checks before committing: `scripts/lint`