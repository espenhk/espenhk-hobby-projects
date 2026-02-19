#!/usr/bin/env python3
"""
Quick start script for the Ice Skating Race Predictor.
Provides example commands and usage instructions.
"""

import sys


def print_usage():
    """Print usage instructions."""
    print("=" * 70)
    print(" " * 15 + "🏁 ICE SKATING RACE PREDICTOR 🏁")
    print("=" * 70)
    print()
    print("USAGE:")
    print("  python3 race_predictor.py    - Start interactive race tracking")
    print("  python3 demo.py              - Run a demonstration race")
    print("  python3 test_race_predictor.py - Run unit tests")
    print()
    print("FEATURES:")
    print("  ✓ Race distance presets (1500m, 3000m, 5000m, 10000m)")
    print("  ✓ Variable lap distances (shorter first lap)")
    print("  ✓ Fast numeric skater input (1 = Skater 1, 2 = Skater 2)")
    print("  ✓ Real-time finish time predictions")
    print("  ✓ Speed-based predictions accounting for lap distance")
    print("  ✓ Current leader tracking and comparisons")
    print("  ✓ Auto-refresh display")
    print("  ✓ Competition leaderboard tracking")
    print("  ✓ Best time records and statistics")
    print()
    print("RACE DISTANCES:")
    print("  1500m  - 4 laps  (300m + 3×400m)")
    print("  3000m  - 8 laps  (200m + 7×400m)")
    print("  5000m  - 13 laps (200m + 12×400m)")
    print("  10000m - 25 laps (25×400m)")
    print()
    print("TIME INPUT FORMATS:")
    print("  MM:SS.mmm  - Minutes:Seconds.milliseconds (e.g., 1:30.500)")
    print("  SS.mmm     - Seconds.milliseconds (e.g., 45.250)")
    print("  SS         - Seconds only (e.g., 32)")
    print()
    print("QUICK INPUT EXAMPLES:")
    print("  '1 23.5'      - Skater 1 did 23.5 seconds")
    print("  '2 31.2'      - Skater 2 did 31.2 seconds")
    print("  '23.5 31.2'   - Both skaters (1=23.5s, 2=31.2s)")
    print()
    print("COMMANDS DURING RACE:")
    print("  status - Show current race status")
    print("  quit   - Exit race tracking")
    print()
    print("LEADERBOARD:")
    print("  python3 race_predictor.py --leaderboard       - View overall leaderboard")
    print("  python3 race_predictor.py --leaderboard 1500m - View 1500m leaderboard")
    print()
    print("CUSTOM PRESETS:")
    print("  Add custom race distances to presets/ directory")
    print("  See presets/README.md for format")
    print()
    print("=" * 70)
    print()
    print("Ready to start? Run: python3 race_predictor.py")
    print()


if __name__ == "__main__":
    print_usage()
    
    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h', 'help']:
        sys.exit(0)
    
    # Ask if user wants to start now
    try:
        response = input("Start race tracking now? (y/n): ").strip().lower()
        if response == 'y':
            import race_predictor
            race_predictor.main()
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
        sys.exit(0)
