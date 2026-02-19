# Race Presets

This directory contains race distance presets for the Ice Skating Race Predictor.

## File Format

Each preset is a JSON file with the following structure:

```json
{
  "name": "1500m",
  "total_distance": 1500,
  "lap_distance": 400,
  "laps": [
    {"lap": 1, "distance": 300},
    {"lap": 2, "distance": 400},
    {"lap": 3, "distance": 400},
    {"lap": 4, "distance": 400}
  ]
}
```

## Available Presets

- **1500m**: 4 laps (300m + 3×400m)
- **3000m**: 8 laps (200m + 7×400m)
- **5000m**: 13 laps (200m + 12×400m)
- **10000m**: 25 laps (25×400m)

## Creating Custom Presets

To create a new race distance:

1. Create a new `.json` file in this directory
2. Name it after the race distance (e.g., `2000m.json`)
3. Follow the structure above:
   - `name`: Display name for the race
   - `total_distance`: Total distance in meters
   - `lap_distance`: Standard lap distance (usually 400m for ice skating)
   - `laps`: Array of lap configurations
     - `lap`: Lap number (1-indexed)
     - `distance`: Distance for this specific lap in meters

### Example: Creating a 2000m race

File: `2000m.json`
```json
{
  "name": "2000m",
  "total_distance": 2000,
  "lap_distance": 400,
  "laps": [
    {"lap": 1, "distance": 400},
    {"lap": 2, "distance": 400},
    {"lap": 3, "distance": 400},
    {"lap": 4, "distance": 400},
    {"lap": 5, "distance": 400}
  ]
}
```

## Notes

- The first lap is typically shorter when the total distance is not evenly divisible by 400m
- For 1500m: First lap = 1500 - (3×400) = 300m
- For 3000m: First lap = 3000 - (7×400) = 200m
- For 10000m: All laps are 400m (evenly divisible)
- Predictions automatically account for different lap distances by calculating average speed (m/s) rather than average lap time
