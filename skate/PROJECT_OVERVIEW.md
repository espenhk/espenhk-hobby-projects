# Ice Skating Race Predictor - Project Overview

## ✅ Project Complete!

A fully functional Python application for live prediction of lap and finish times in ice skating races.

## 📁 Project Structure

```
skate/
├── race_predictor.py           # Main application entry point
├── start.py                    # Quick start helper script
├── demo.py                     # Demonstration script
├── test_race_predictor.py      # Unit tests (11 tests, all passing)
├── README.md                   # Project documentation
│
├── models/                     # Data models
│   ├── __init__.py
│   ├── skater.py              # Skater class with lap tracking
│   └── race.py                # Race management and state
│
├── engine/                     # Prediction algorithms
│   ├── __init__.py
│   └── predictor.py           # Prediction engine with multiple algorithms
│
└── ui/                        # User interface
    ├── __init__.py
    └── cli.py                 # Interactive command-line interface
```

## 🎯 Current Features (v1.0)

### ✓ Implemented
- ✅ Live lap time input for two skaters simultaneously
- ✅ Real-time finish time predictions based on current pace
- ✅ Comparison with current race leader
- ✅ Average lap time calculation
- ✅ Time gap analysis between skaters
- ✅ Multiple prediction algorithms:
  - Simple average-based prediction
  - Weighted prediction (recent laps weighted more)
  - Fatigue-adjusted prediction
- ✅ Flexible time input formats (MM:SS.mmm, SS.mmm, SS)
- ✅ Race state management
- ✅ Leader tracking
- ✅ Comprehensive unit tests

## 🚀 How to Use

### Quick Start
```bash
cd /home/espenhk/priv/skate
python3 start.py
```

### Interactive Race Tracking
```bash
python3 race_predictor.py
```

### Run Demo
```bash
python3 demo.py
```

### Run Tests
```bash
python3 test_race_predictor.py
```

## 📊 Usage Example

1. **Start the application**
   ```bash
   python3 race_predictor.py
   ```

2. **Enter race configuration**
   - Total number of laps: `10`
   - Skater 1 name: `Erik Hoff`
   - Skater 2 name: `Anna Berg`

3. **Input lap times as they complete**
   ```
   Skater name: Erik Hoff
   Lap time: 31.5
   ```

4. **View live predictions and comparisons**
   - Current leader
   - Predicted finish times
   - Time gaps
   - Average lap times

5. **Mark skaters as finished**
   ```
   Lap time: done
   ```

## 🎨 Key Features Demonstrated

### Real-time Predictions
The application calculates predicted finish times based on:
- Average lap pace
- Recent performance trends
- Fatigue factors (optional)

### Leader Tracking
- Identifies current leader based on elapsed time
- Shows time gaps between skaters
- Updates after each lap

### Flexible Input
Supports multiple time formats:
- `1:30.500` (1 minute, 30.5 seconds)
- `45.250` (45.25 seconds)
- `32` (32 seconds)

## 🔮 Future Features (Planned)

### Next Version Enhancements
- [ ] **Skater Profiles**
  - Personal Best (PB) times
  - Season Best (SB) times
  - Historical performance data

- [ ] **Advanced Predictions**
  - PB/SB-based predictions
  - Performance trend analysis
  - Historical comparison

- [ ] **Data Persistence**
  - Save race results
  - Load previous races
  - Export to CSV/JSON

- [ ] **Extended Features**
  - Support for more than 2 skaters
  - Multiple race distances
  - Split times and intermediate points
  - Graphical visualization (optional)

## 🧪 Testing

All core functionality is tested with 11 unit tests covering:
- Skater management
- Lap time tracking
- Race state management
- Prediction algorithms
- Time parsing and formatting
- Leader calculation
- Gap analysis

**Test Results:** ✅ All tests passing (100% success rate)

## 🏗️ Architecture

### Clean Separation of Concerns
- **Models**: Data structures (Skater, Race)
- **Engine**: Business logic (predictions, calculations)
- **UI**: User interaction (CLI)

### Design Principles
- Modular and extensible
- Easy to add new prediction algorithms
- Testable components
- Clear data flow

## 💡 Technical Details

### Dependencies
- **Python 3.6+** (uses standard library only)
- No external packages required

### Key Classes

**Skater**
- Tracks individual skater data
- Lap times, averages, predictions
- Finish status

**Race**
- Manages multiple skaters
- Race state and configuration
- Leader calculation
- Comparison logic

**PredictionEngine**
- Multiple prediction algorithms
- Time formatting utilities
- Gap calculations

**RaceCLI**
- Interactive interface
- Live input handling
- Status display

## 📈 Example Output

```
======================================================================
                    🏁 ICE SKATING RACE PREDICTOR 🏁
======================================================================

RACE STATUS - 10 Laps Total
======================================================================

🥇 Current Leader: Anna Berg (1:02.600)
📊 Predicted Winner: Anna Berg

----------------------------------------------------------------------
SKATER               LAPS     TIME            AVG LAP         PRED FINISH    
----------------------------------------------------------------------
Anna Berg            2/10     1:02.600        31.300s         5:13.000       
Erik Hoff            2/10     1:02.800        31.400s         5:14.000       

----------------------------------------------------------------------
⏱️  Erik Hoff is 0.200s behind Anna Berg
======================================================================
```

## 🎓 Learning Points

This project demonstrates:
- Object-oriented design in Python
- State management for live applications
- Real-time data processing
- Command-line interface design
- Unit testing best practices
- Modular architecture

---

**Status:** ✅ Ready to use!  
**Version:** 1.0  
**Created:** 2026-02-19
