# Ice Skating Race Predictor

A Python application for live prediction of lap and finish times for ice skating races.

## Features

### Current Version
- **Race Distance Presets**: Pre-configured distances (1500m, 3000m, 5000m, 10000m)
- **Variable Lap Distances**: Correctly handles shorter first laps
- **Fast Numeric Input**: Input lap times as `1 15.00` for skater 1
- **Dual Input**: Input both skaters at once with `23.5 31.2`
- **Live Predictions**: Real-time finish time predictions accounting for lap distance variations
- **Speed-Based Predictions**: Uses average speed (m/s) instead of average lap time for accurate predictions
- **Competition Management**: Track multiple competitions with leaderboards
- **Competition Selection**: Choose from existing competitions or create new ones
- **Lap-by-Lap Storage**: Full lap time history for detailed analysis
- **Live Comparison**: Compare current race against historical leader reference
- **Current Leader Tracking**: Compare skaters in real-time
- **Auto-Refresh Display**: Clean in-place screen updates

### Future Features
- Skater profiles with Personal Bests (PBs) and Season Bests (SBs)
- Historical performance-based predictions
- Data persistence and race history

## Installation

```bash
# No external dependencies required - uses Python standard library
python3 race_predictor.py
```

## Usage

### Quick Start

1. Run the application:
   ```bash
   python3 race_predictor.py
   ```

2. Select a race distance:
   - Available: `1500m`, `3000m`, `5000m`, `10000m`
   - Custom presets can be added to `presets/` directory

3. Choose a competition:
   - Select from existing competitions for that distance
   - Or create a new competition by entering a name

4. Enter skater names

5. Input lap times using fast numeric format:
   - `1 23.5` - Skater 1 completed lap in 23.5 seconds
   - `2 31.2` - Skater 2 completed lap in 31.2 seconds
   - `23.5 31.2` - Both skaters at once (skater 1 = 23.5s, skater 2 = 31.2s)
   - The screen auto-refreshes with updated predictions

6. View results:
   - Race results are automatically saved to the competition
   - View leaderboard: `python3 race_predictor.py --leaderboard 1500m`

### Race Distance Examples

- **1500m**: 4 laps (300m + 3×400m)
- **3000m**: 8 laps (200m + 7×400m)  
- **5000m**: 13 laps (200m + 12×400m)
- **10000m**: 25 laps (25×400m)

### Creating Custom Race Presets

Add a new JSON file to `presets/` directory:

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

## Application Structure

- `race_predictor.py` - Main application entry point
- `models/skater.py` - Skater data model with speed-based predictions
- `models/race.py` - Race management and state
- `models/race_preset.py` - Race distance preset loader
- `models/competition.py` - Competition tracking and leaderboards
- `engine/predictor.py` - Prediction algorithms and time formatting
- `ui/cli.py` - Command-line interface with numeric input
- `presets/` - Race distance configuration files
- `data/competitions/` - Competition data and results
