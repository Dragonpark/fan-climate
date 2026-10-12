# Fan Climate Control

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/default)

A Home Assistant custom integration that automatically controls a fan's speed based on a climate or temperature sensor entity's reading.

## Features

- **Climate Entity** — Exposes a thermostat climate entity (`climate.fan_climate_*`).
  - **Set-point**: Adjust the target temperature directly on the thermostat card to define when the fan turns on.
  - **HVAC Modes**: `fan_only` enables automatic fan speed control; `off` disables it and turns the fan off.
  - **HVAC Action**: Shows `idle` (temperature is below set-point) or `fan` (fan running).
- **Auto-detection of Fan Speeds** — Automatically calculates the number of supported fan speeds upon adding the device by evaluating `100 / percentage_step`.
- **Configurable Entities** — Exposes number entities on the same device so you can view and tune settings without reinstalling:
  - `number.fan_climate_*_temperature_step`: Temperature difference in which the fan speed increases by 1 level.
  - `number.fan_climate_*_number_of_speeds`: Number of discrete fan speeds (auto-detected initially, can be overridden).
- **Simplified Setup** — During initial configuration, you only need to choose the fan entity and temperature source.

## Installation

### Method 1: HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed and running.
2. In Home Assistant, open **HACS** -> **Integrations**.
3. Click the three dots in the top right corner and select **Custom repositories**.
4. Add the URL of your repository and select category **Integration**.
5. Click **Download**, then restart Home Assistant.

### Method 2: Manual Installation

1. Copy the `custom_components/fan_climate` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## Adding the Integration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Fan Climate Control**.
3. Select your fan and temperature source entity.

## Configuration

During setup, you will be prompted for:

| Parameter | Description |
|---|---|
| **Fan** | The fan entity to control (`fan.*`) |
| **Temperature source** | A `climate` or `sensor` entity providing the current temperature |

The set-point (defaults to 72°), temperature step (defaults to 2°), and number of speeds (auto-detected from `percentage_step` or default 3) are automatically initialized and can be controlled via the exposed entities.

## Entities Created

Under the integration device, you get:
1. `climate.fan_climate_<name>`: Thermostat interface for set-point and automation state.
2. `number.fan_climate_<name>_temperature_step`: Controls temperature step per speed increase.
3. `number.fan_climate_<name>_number_of_speeds`: Controls/overrides total fan speed levels.
