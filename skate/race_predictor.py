#!/usr/bin/env python3
"""
Ice Skating Race Predictor - Main Application Entry Point

A live prediction tool for ice skating races with real-time finish time
calculations and leader comparisons.
"""

import sys
from ui.cli import RaceCLI


def main():
    """Main application entry point."""
    try:
        cli = RaceCLI()
        
        # Check for command-line arguments
        if len(sys.argv) > 1:
            if sys.argv[1] in ['--leaderboard', '-l', 'leaderboard']:
                # Show leaderboard and exit
                cli.clear_screen()
                cli.print_header()
                
                # Get race distance filter if provided
                distance = sys.argv[2] if len(sys.argv) > 2 else None
                cli.display_leaderboard(distance)
                return
            elif sys.argv[1] in ['--help', '-h', 'help']:
                print("Usage:")
                print("  python3 race_predictor.py              - Start race tracking")
                print("  python3 race_predictor.py --leaderboard [distance] - Show leaderboard")
                print("  python3 race_predictor.py --help       - Show this help")
                return
        
        cli.run()
    except KeyboardInterrupt:
        print("\n\nRace tracking interrupted. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
