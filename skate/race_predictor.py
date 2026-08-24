#!/usr/bin/env python3
"""
Ice Skating Race Predictor - Main Application Entry Point

A live prediction tool for ice skating races with real-time finish time
calculations and leader comparisons.
"""

import os
import sys

from models.competition import Competition
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

                # If additional args provided, try to determine whether the
                # user passed a competition name/file or a race distance.
                # Usage examples supported:
                #   python3 race_predictor.py --leaderboard                 -> show default comp
                #   python3 race_predictor.py --leaderboard 1500m           -> filter by distance
                #   python3 race_predictor.py --leaderboard MyComp          -> show competition named "MyComp"
                #   python3 race_predictor.py --leaderboard my_comp.json    -> show specific file
                distance = None

                if len(sys.argv) > 2:
                    arg = sys.argv[2]

                    # Check for an explicit file in data/competitions (resolve relative
                    # to this script so commands work from workspace root)
                    comp_dir = os.path.join(os.path.dirname(__file__), 'data', 'competitions')
                    possible_files = [arg]
                    if not arg.lower().endswith('.json'):
                        possible_files.append(f"{arg}.json")

                    matched_comp = None
                    for fname in possible_files:
                        fpath = os.path.join(comp_dir, fname)
                        if os.path.exists(fpath):
                            matched_comp = fpath
                            break

                    # Also allow matching by competition name (case-insensitive)
                    if not matched_comp:
                        for comp_info in Competition.list_competitions(comp_dir):
                            if arg.lower() == comp_info['name'].lower() or arg.lower() == comp_info['filename'].lower() or arg.lower() == comp_info['filename'].lower().replace('.json',''):
                                matched_comp = comp_info['filepath']
                                break

                    # If we found a competition file, create CLI bound to it
                    if matched_comp:
                        # Optional third arg may be a distance filter
                        distance = sys.argv[3] if len(sys.argv) > 3 else None
                        cli = RaceCLI(competition_file=matched_comp)
                        cli.clear_screen()
                        cli.print_header()
                        cli.display_leaderboard(distance)
                        return
                    else:
                        # Treat the provided arg as a distance filter
                        distance = arg

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
        raise e


if __name__ == "__main__":
    main()
