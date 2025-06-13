# DropCountr Home Assistant Integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![pre-commit][pre-commit-shield]][pre-commit]
[![Black][black-shield]][black]

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

[![Discord][discord-shield]][discord]
[![Community Forum][forum-shield]][forum]

A comprehensive Home Assistant integration for [DropCountr](https://dropcountr.com/) water monitoring systems. Track your water usage, detect leaks, and monitor your consumption patterns with rich sensor data and automation capabilities.

## ✨ Features

### 📊 **Comprehensive Water Monitoring**
- **Real-time Usage Data**: Daily water consumption tracking
- **Irrigation Monitoring**: Separate tracking for irrigation vs. total usage
- **Leak Detection**: Binary sensor alerts for detected leaks
- **Connection Status**: Monitor service connection health
- **Multi-timeframe Analytics**: Daily, weekly, and monthly usage totals

### 🔧 **Advanced Capabilities**
- **Complete API Coverage**: Utilizes all PyDropCountr library features
- **Flexible Data Access**: On-demand hourly usage data via service calls
- **Service Connection Details**: Detailed metadata for each water meter
- **Automation Ready**: All sensors available for Home Assistant automations
- **Unit Conversion**: Automatic conversion between gallons and liters

### 🏠 **Home Assistant Native**
- **Config Flow Setup**: Easy configuration through the UI
- **Device Registry**: Proper device representation with metadata
- **Entity Naming**: Follows Home Assistant conventions
- **Translation Support**: Localized entity names and descriptions
- **HACS Compatible**: Easy installation and updates

## 📦 Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add `https://github.com/mcolyer/home-assistant-dropcountr` as an Integration
6. Search for "DropCountr" and install
7. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/dropcountr` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Add the integration through the UI

## ⚙️ Configuration

### Initial Setup

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "DropCountr"
4. Enter your DropCountr account credentials:
   - **Email**: Your DropCountr account email
   - **Password**: Your DropCountr account password

### Authentication
- Uses simple email/password authentication (no OAuth required)
- Credentials are stored securely in Home Assistant
- Supports reauthentication if credentials change

## 📈 Sensors

The integration creates the following sensors for each service connection:

### Water Usage Sensors
| Sensor | Description | Unit | Device Class |
|--------|-------------|------|--------------|
| **Daily Irrigation** | Latest daily irrigation usage | Gallons | Water |
| **Irrigation Events** | Number of irrigation events | Count | - |
| **Daily Total** | Most recent day's usage | Gallons | Water |
| **Weekly Total** | Last 7 days total usage | Gallons | Water |
| **Monthly Total** | Current month to date usage | Gallons | Water |

### Status Sensors
| Sensor | Description | Device Class |
|--------|-------------|--------------|
| **Leak Detected** | Binary sensor for leak detection | Moisture |
| **Connection Status** | Service connection health | Connectivity |

## 🔧 Services

### `dropcountr.list_usage`
Returns cached daily usage data for all service connections.

### `dropcountr.get_service_connection`
Retrieves detailed information for a specific service connection.

**Parameters:**
- `config_entry`: DropCountr integration config entry
- `service_connection_id`: ID of the service connection

### `dropcountr.get_hourly_usage`
Fetches hourly granularity usage data with optional date range.

**Parameters:**
- `config_entry`: DropCountr integration config entry  
- `service_connection_id`: ID of the service connection
- `start_date` (optional): Start date in ISO format
- `end_date` (optional): End date in ISO format

## 🚀 Automation Examples

### Leak Detection Alert
```yaml
automation:
  - alias: "Water Leak Detected"
    trigger:
      - platform: state
        entity_id: binary_sensor.dropcountr_main_moisture
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          message: "Water leak detected at main meter!"
          title: "🚨 Leak Alert"
```

### High Usage Warning
```yaml
automation:
  - alias: "High Monthly Water Usage"
    trigger:
      - platform: numeric_state
        entity_id: sensor.dropcountr_main_monthly_total
        above: 5000  # 5000 gallons
    action:
      - service: notify.family
        data:
          message: "Monthly water usage has exceeded 5,000 gallons"
```

### Daily Usage Report
```yaml
automation:
  - alias: "Daily Water Usage Report"
    trigger:
      - platform: time
        at: "09:00:00"
    action:
      - service: notify.homeowner
        data:
          message: >
            Yesterday's water usage: {{ states('sensor.dropcountr_main_daily_total') }} gallons
            ({{ states('sensor.dropcountr_main_irrigation_gallons') }} irrigation)
```

## 🔄 Data Updates

- **Usage Data**: Updates daily (configurable)
- **Service Connections**: Updates daily
- **On-Demand**: Service calls provide immediate data access

The integration uses efficient polling intervals that respect DropCountr's API while ensuring data freshness.

## 🛠️ Development

### Requirements
- Python 3.13+
- Home Assistant 2025.6.0+
- PyDropCountr library

### Setup Development Environment
```bash
# Clone the repository
git clone https://github.com/mcolyer/home-assistant-dropcountr.git
cd home-assistant-dropcountr

# Install dependencies
scripts/setup

# Run tests
scripts/test

# Start development instance
scripts/develop
```

### Testing
The integration includes comprehensive test coverage:
- Unit tests for all components
- Integration tests with mocked API responses
- Config flow testing for all scenarios
- Monthly sensor boundary testing

Run tests with: `scripts/test`

## 📚 Documentation

- **[PyDropCountr Library](https://pypi.org/project/pydropcountr/)**: Underlying API client
- **[DropCountr Website](https://dropcountr.com/)**: Official water monitoring service
- **[Home Assistant Developer Docs](https://developers.home-assistant.io/)**: Integration development guide

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass: `scripts/test`
6. Run linting: `scripts/lint`
7. Submit a pull request

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🐛 Issues & Support

- **Bug Reports**: [GitHub Issues](https://github.com/mcolyer/home-assistant-dropcountr/issues)
- **Feature Requests**: [GitHub Issues](https://github.com/mcolyer/home-assistant-dropcountr/issues)
- **Discussion**: [Home Assistant Community](https://community.home-assistant.io/)

## ⭐ Acknowledgments

- Powered by the [PyDropCountr](https://pypi.org/project/pydropcountr/) library
- Inspired by the Home Assistant community's dedication to home automation

---

**Disclaimer**: This integration is not officially affiliated with DropCountr. Use at your own risk.

[releases-shield]: https://img.shields.io/github/release/mcolyer/home-assistant-dropcountr.svg?style=for-the-badge
[releases]: https://github.com/mcolyer/home-assistant-dropcountr/releases
[commits-shield]: https://img.shields.io/github/commit-activity/y/mcolyer/home-assistant-dropcountr.svg?style=for-the-badge
[commits]: https://github.com/mcolyer/home-assistant-dropcountr/commits/main
[license-shield]: https://img.shields.io/github/license/mcolyer/home-assistant-dropcountr.svg?style=for-the-badge
[pre-commit]: https://github.com/pre-commit/pre-commit
[pre-commit-shield]: https://img.shields.io/badge/pre--commit-enabled-brightgreen?style=for-the-badge
[black]: https://github.com/psf/black
[black-shield]: https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[user]: https://github.com/mcolyer
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40mcolyer-blue.svg?style=for-the-badge
[buymecoffee]: https://www.buymeacoffee.com/mcolyer
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[discord]: https://discord.gg/Qa5fW2R
[discord-shield]: https://img.shields.io/discord/330944238910963714.svg?style=for-the-badge