# Data Directory

This directory stores competition data and race results.

## Structure

- `competitions/` - Competition data files
  - `competition.json` - Main competition with all race results and leaderboard

## Format

The competition data is stored in JSON format and includes:
- All race results with timestamps and lap times
- Skater names and finish times
- Race distances
- Positions

This data is used to:
- Maintain leaderboards
- Track the overall competition leader
- Provide lap-by-lap comparison against best historical performance
