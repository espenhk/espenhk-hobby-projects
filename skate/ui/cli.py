"""
Command-line interface for live race tracking.
"""
from typing import Optional
from models.race import Race
from models.skater import Skater
from models.race_preset import RacePreset
from models.competition import Competition
from engine.predictor import PredictionEngine
from .base_ui import BaseRaceUI


class RaceCLI(BaseRaceUI):
    """Interactive CLI for live race tracking."""
    
    def __init__(self, competition_file: str = 'data/competitions/competition.json'):
        """Initialize the CLI."""
        super().__init__(competition_file)
        self.skater_map = {}  # Maps numeric IDs to skater names
        
    def setup_race(self) -> Race:
        """
        Setup a new race with user input.
        
        Returns:
            Configured Race object
        """
        self.clear_screen()
        self.print_header()
        
        print("RACE SETUP")
        print("-" * 70)
        
        # List available presets
        available_presets = RacePreset.list_available_presets()
        if available_presets:
            print("\nAvailable race distances:")
            for preset_name in available_presets:
                print(f"  - {preset_name}")
            print()
        
        # Get race distance
        preset = None
        while not preset:
            preset_name = input("Enter race distance (e.g., 1500m, 3000m): ").strip()
            preset = RacePreset.load_preset(preset_name)
            
            if preset:
                print(f"\n✓ Loaded {preset.name} race:")
                print(f"  Total distance: {preset.total_distance}m")
                print(f"  Laps: {preset.total_laps}")
                print(f"  First lap: {preset.get_lap_distance(1)}m")
                print(f"  Remaining laps: {preset.lap_distance}m")
                print()
            else:
                print(f"❌ Preset '{preset_name}' not found. Try: {', '.join(available_presets)}")
        
        # Select or create competition
        self._select_competition(preset.name)
        
        # Get skater names (for two-skater races)
        print("\nEnter skater names:")
        skater1_name = input("Skater 1: ").strip()
        skater2_name = input("Skater 2: ").strip()
        
        while not skater1_name or not skater2_name:
            print("Both skater names are required!")
            skater1_name = input("Skater 1: ").strip()
            skater2_name = input("Skater 2: ").strip()
        
        # Create skaters
        skaters = [
            Skater(name=skater1_name),
            Skater(name=skater2_name)
        ]
        
        # Create numeric ID mapping for fast input
        self.skater_map = {
            '1': skater1_name,
            '2': skater2_name
        }
        
        return Race(preset=preset, skaters=skaters)
    
    def _select_competition(self, race_distance: str):
        """
        Select an existing competition or create a new one for the given race distance.
        
        Args:
            race_distance: The race distance to filter competitions by
        """
        # List competitions matching this distance
        competitions = Competition.list_competitions_by_distance(race_distance)
        
        if competitions:
            print(f"\n📊 Found {len(competitions)} existing competition(s) for {race_distance}:")
            print("-" * 70)
            for i, comp in enumerate(competitions, 1):
                leader_info = ""
                if comp.get('leader') and comp.get('best_time'):
                    leader_info = f" | Leader: {comp['leader']} ({self.predictor.format_time(comp['best_time'])})"
                print(f"  {i}. {comp['name']} - {comp['race_count']} race(s){leader_info}")
            print("-" * 70)
            print()
            
            # Get user selection
            while True:
                choice = input("Select competition (number) or enter new name: ").strip()
                
                # Check if it's a number (selecting existing competition)
                if choice.isdigit():
                    index = int(choice) - 1
                    if 0 <= index < len(competitions):
                        # Load selected competition
                        selected = competitions[index]
                        self.competition_file = selected['filepath']
                        self.competition = Competition.load(self.competition_file)
                        print(f"\n✓ Loaded competition: {selected['name']}")
                        
                        # Show current leader
                        leader = self.competition.get_current_leader()
                        if leader:
                            print(f"👑 Current Leader: {leader['name']} - {self.predictor.format_time(leader['best_time'])}")
                        print()
                        break
                    else:
                        print(f"❌ Invalid number. Choose 1-{len(competitions)}")
                else:
                    # Create new competition with entered name
                    if choice:
                        comp_name = choice
                        self.competition_file = f"data/competitions/{comp_name.lower().replace(' ', '_')}.json"
                        self.competition = Competition(name=comp_name)
                        print(f"\n✓ Created new competition: {comp_name}")
                        print()
                        break
                    else:
                        print("❌ Please enter a competition name or number")
        else:
            # No existing competitions, create new one
            print(f"\n📊 No existing competitions found for {race_distance}")
            comp_name = input("Enter new competition name: ").strip()
            
            while not comp_name:
                print("❌ Competition name is required!")
                comp_name = input("Enter new competition name: ").strip()
            
            self.competition_file = f"data/competitions/{comp_name.lower().replace(' ', '_')}.json"
            self.competition = Competition(name=comp_name)
            print(f"\n✓ Created new competition: {comp_name}")
            print()
    
    def input_lap_time(self):
        """Handle lap time input."""
        print("\nINPUT LAP TIME")
        print("-" * 70)
        print("Commands: 'status' = show status, 'quit' = exit")
        print("Format: '1 15.00' or '15.00 31.2' (both skaters)")
        print()
        
        # Get input
        user_input = input("Input: ").strip()
        
        if user_input.lower() == 'quit':
            return 'quit'
        elif user_input.lower() == 'status':
            return 'status'
        
        parts = user_input.split()
        
        # Check if this is a two-time input (both are times, no skater ID)
        if len(parts) == 2:
            # Check if first part is a skater ID (1, 2, or a name)
            is_skater_id = parts[0] in self.skater_map or self.race.get_skater_by_name(parts[0]) is not None
            
            if not is_skater_id:
                # Try to parse both as times
                time1 = self.predictor.parse_time_input(parts[0])
                time2 = self.predictor.parse_time_input(parts[1])
                
                # If both parse as times and look like reasonable lap times (>5s), record for both skaters
                if time1 is not None and time2 is not None and time1 > 5 and time2 > 5:
                    return self._record_both_skaters(time1, time2)
            
            # Otherwise treat as "<skater> <time>"
            skater_id, time_input = parts
            skater_name = self.skater_map.get(skater_id, skater_id)
            skater = self.race.get_skater_by_name(skater_name)
            
            if not skater:
                print(f"❌ Skater '{skater_id}' not found!")
                return None
            
            if skater.finished:
                print(f"ℹ️  {skater.name} has already finished!")
                return None
            
            lap_time = self.predictor.parse_time_input(time_input)
            if lap_time is None:
                print("❌ Invalid time format!")
                return None
            
            return self._record_single_skater(skater, lap_time)
            
        elif len(parts) == 1:
            # Single input - could be skater ID or time
            skater_id = parts[0]
            skater_name = self.skater_map.get(skater_id, skater_id)
            skater = self.race.get_skater_by_name(skater_name)
            
            if not skater:
                print(f"❌ Skater '{skater_id}' not found!")
                return None
            
            if skater.finished:
                print(f"ℹ️  {skater.name} has already finished!")
                return None
            
            # Ask for time
            time_input = input(f"Lap time for {skater.name} (MM:SS.mmm or SS.mmm): ").strip()
            
            if time_input.lower() == 'done':
                skater.mark_finished(skater.get_total_time())
                print(f"✅ {skater.name} finished with time: {self.predictor.format_time(skater.finish_time)}")
                return 'finished'
            
            lap_time = self.predictor.parse_time_input(time_input)
            if lap_time is None:
                print("❌ Invalid time format!")
                return None
            
            return self._record_single_skater(skater, lap_time)
        else:
            print("❌ Invalid input format!")
            return None
    
    def _record_single_skater(self, skater, lap_time):
        """Record a lap time for a single skater."""
        self.race.add_lap_time(skater.name, lap_time)
        
        laps_completed = skater.get_laps_completed()
        print(f"✅ Lap {laps_completed} recorded: {self.predictor.format_time(lap_time)}")
        
        if skater.finished:
            print(f"🏁 {skater.name} has finished the race!")
            print(f"   Final time: {self.predictor.format_time(skater.finish_time)}")
        
        return 'recorded'
    
    def _record_both_skaters(self, time1, time2):
        """Record lap times for both skaters (1=first time, 2=second time)."""
        skater1_name = self.skater_map.get('1')
        skater2_name = self.skater_map.get('2')
        
        if not skater1_name or not skater2_name:
            print("❌ Both skaters must be configured!")
            return None
        
        skater1 = self.race.get_skater_by_name(skater1_name)
        skater2 = self.race.get_skater_by_name(skater2_name)
        
        # Record both times
        results = []
        
        if skater1 and not skater1.finished:
            self.race.add_lap_time(skater1.name, time1)
            laps1 = skater1.get_laps_completed()
            print(f"✅ {skater1.name} Lap {laps1}: {self.predictor.format_time(time1)}")
            if skater1.finished:
                print(f"   🏁 Finished! Total: {self.predictor.format_time(skater1.finish_time)}")
            results.append('recorded')
        elif skater1 and skater1.finished:
            print(f"ℹ️  {skater1.name} has already finished (time not recorded)")
        
        if skater2 and not skater2.finished:
            self.race.add_lap_time(skater2.name, time2)
            laps2 = skater2.get_laps_completed()
            print(f"✅ {skater2.name} Lap {laps2}: {self.predictor.format_time(time2)}")
            if skater2.finished:
                print(f"   🏁 Finished! Total: {self.predictor.format_time(skater2.finish_time)}")
            results.append('recorded')
        elif skater2 and skater2.finished:
            print(f"ℹ️  {skater2.name} has already finished (time not recorded)")
        
        return 'recorded' if results else None
    
    def run(self):
        """Run the interactive CLI."""
        self.race = self.setup_race()
        
        while not self.race.is_race_finished():
            self.clear_screen()
            self.print_header()
            self.display_race_status()
            
            result = self.input_lap_time()
            
            if result == 'quit':
                print("\nExiting race tracker...")
                break
        
        if self.race.is_race_finished():
            self.clear_screen()
            self.print_header()
            print("\n🏆 RACE COMPLETE! 🏆")
            self.display_race_status()
            
            # Show final results
            sorted_skaters = self.display_final_results()
            
            # Save results to competition
            race_distance = self.race.preset.name
            skater_data = [(s['name'], s['total_time'], 
                           self.race.get_skater_by_name(s['name']).lap_times) 
                          for s in sorted_skaters]
            self.competition.add_race_results(race_distance, skater_data)
            self.competition.save(self.competition_file)
            print("\n✅ Results saved to competition!")
            
            # Display updated leaderboard
            self.display_leaderboard(race_distance)
            
            # Ask if user wants another race
            print()
            response = input("Start another race? (y/n): ").strip().lower()
            if response == 'y':
                self.run()  # Start a new race


def main():
    """Main entry point for CLI."""
    cli = RaceCLI()
    cli.run()


if __name__ == "__main__":
    main()
    
    def setup_race(self) -> Race:
        """
        Setup a new race with user input.
        
        Returns:
            Configured Race object
        """
        self.clear_screen()
        self.print_header()
        
        print("RACE SETUP")
        print("-" * 70)
        
        # List available presets
        available_presets = RacePreset.list_available_presets()
        if available_presets:
            print("\nAvailable race distances:")
            for preset_name in available_presets:
                print(f"  - {preset_name}")
            print()
        
        # Get race distance
        preset = None
        while not preset:
            preset_name = input("Enter race distance (e.g., 1500m, 3000m): ").strip()
            preset = RacePreset.load_preset(preset_name)
            
            if preset:
                print(f"\n✓ Loaded {preset.name} race:")
                print(f"  Total distance: {preset.total_distance}m")
                print(f"  Laps: {preset.total_laps}")
                print(f"  First lap: {preset.get_lap_distance(1)}m")
                print(f"  Remaining laps: {preset.lap_distance}m")
                print()
            else:
                print(f"❌ Preset '{preset_name}' not found. Try: {', '.join(available_presets)}")
        
        # Select or create competition
        self._select_competition(preset.name)
        
        # Get skater names (for two-skater races)
        print("\nEnter skater names:")
        skater1_name = input("Skater 1: ").strip()
        skater2_name = input("Skater 2: ").strip()
        
        while not skater1_name or not skater2_name:
            print("Both skater names are required!")
            skater1_name = input("Skater 1: ").strip()
            skater2_name = input("Skater 2: ").strip()
        
        # Create skaters
        skaters = [
            Skater(name=skater1_name),
            Skater(name=skater2_name)
        ]
        
        # Create numeric ID mapping for fast input
        self.skater_map = {
            '1': skater1_name,
            '2': skater2_name
        }
        
        return Race(preset=preset, skaters=skaters)
    
    def _select_competition(self, race_distance: str):
        """
        Select an existing competition or create a new one for the given race distance.
        
        Args:
            race_distance: The race distance to filter competitions by
        """
        # List competitions matching this distance
        competitions = Competition.list_competitions_by_distance(race_distance)
        
        if competitions:
            print(f"\n📊 Found {len(competitions)} existing competition(s) for {race_distance}:")
            print("-" * 70)
            for i, comp in enumerate(competitions, 1):
                leader_info = ""
                if comp.get('leader') and comp.get('best_time'):
                    leader_info = f" | Leader: {comp['leader']} ({self.predictor.format_time(comp['best_time'])})"
                print(f"  {i}. {comp['name']} - {comp['race_count']} race(s){leader_info}")
            print("-" * 70)
            print()
            
            # Get user selection
            while True:
                choice = input("Select competition (number) or enter new name: ").strip()
                
                # Check if it's a number (selecting existing competition)
                if choice.isdigit():
                    index = int(choice) - 1
                    if 0 <= index < len(competitions):
                        # Load selected competition
                        selected = competitions[index]
                        self.competition_file = selected['filepath']
                        self.competition = Competition.load(self.competition_file)
                        print(f"\n✓ Loaded competition: {selected['name']}")
                        
                        # Show current leader
                        leader = self.competition.get_current_leader()
                        if leader:
                            print(f"👑 Current Leader: {leader['name']} - {self.predictor.format_time(leader['best_time'])}")
                        print()
                        break
                    else:
                        print(f"❌ Invalid number. Choose 1-{len(competitions)}")
                else:
                    # Create new competition with entered name
                    if choice:
                        comp_name = choice
                        self.competition_file = f"data/competitions/{comp_name.lower().replace(' ', '_')}.json"
                        self.competition = Competition(name=comp_name)
                        print(f"\n✓ Created new competition: {comp_name}")
                        print()
                        break
                    else:
                        print("❌ Please enter a competition name or number")
        else:
            # No existing competitions, create new one
            print(f"\n📊 No existing competitions found for {race_distance}")
            comp_name = input("Enter new competition name: ").strip()
            
            while not comp_name:
                print("❌ Competition name is required!")
                comp_name = input("Enter new competition name: ").strip()
            
            self.competition_file = f"data/competitions/{comp_name.lower().replace(' ', '_')}.json"
            self.competition = Competition(name=comp_name)
            print(f"\n✓ Created new competition: {comp_name}")
            print()
    
    def display_race_status(self):
        """Display current race status."""
        if not self.race:
            return
        
        print(f"\nRACE STATUS - {self.race.preset.name} ({self.race.total_laps} Laps)")
        
        # Display skater ID mapping
        if self.skater_map:
            print("💡 Quick Input: ", end="")
            print(" | ".join([f"{id}={name}" for id, name in sorted(self.skater_map.items())]))
        
        # Get leader reference from competition history
        leader_ref = self.competition.get_leader_reference(self.race.preset.name)
        if leader_ref:
            print(f"📊 Leader Reference: {leader_ref['name']} - {self.predictor.format_time(leader_ref['finish_time'])}")
        
        status = self.race.get_race_status()
        
        # Display leader info
        if status['leader']:
            leader_time = self.predictor.format_time(status['leader_time'])
            print(f"🥇 Current Leader: {status['leader']} ({leader_time})")
        
        if status['predicted_winner'] and status['predicted_winner'] != status['leader']:
            print(f"📊 Predicted Winner: {status['predicted_winner']}")
        
        print(f"\n{'SKATER':<20} {'LAPS':<8} {'TIME':<15} {'AVG LAP':<15} {'PRED FINISH':<15} {'VS LEADER':<20}")
        print("-" * 105)
        
        # Sort skaters by current time
        sorted_skaters = sorted(status['skaters'], 
                               key=lambda x: x['total_time'] if x['laps_completed'] > 0 else float('inf'))
        
        for skater_info in sorted_skaters:
            name = skater_info['name']
            laps = f"{skater_info['laps_completed']}/{self.race.total_laps}"
            
            if skater_info['finished']:
                total_time = self.predictor.format_time(skater_info['total_time'])
                print(f"{name:<20} {'DONE':<8} {total_time:<15} {'✓ FINISHED':<30}")
            else:
                total_time = self.predictor.format_time(skater_info['total_time']) if skater_info['laps_completed'] > 0 else "N/A"
                avg_lap = self.predictor.format_time(skater_info['average_lap']) if skater_info['average_lap'] else "N/A"
                pred_finish = self.predictor.format_time(skater_info['predicted_finish']) if skater_info['predicted_finish'] else "N/A"
                
                # Compare with leader reference if available
                vs_leader = ""
                if leader_ref and skater_info['laps_completed'] > 0:
                    skater = self.race.get_skater_by_name(name)
                    comparison = self._compare_with_leader(skater, leader_ref)
                    if comparison:
                        vs_leader = comparison
                
                print(f"{name:<20} {laps:<8} {total_time:<15} {avg_lap:<15} {pred_finish:<15} {vs_leader:<20}")
        
        # Show comparison if there's a leader
        if len(sorted_skaters) >= 2 and sorted_skaters[0]['laps_completed'] > 0:
            gap, description = self.predictor.calculate_gap(
                self.race.get_skater_by_name(sorted_skaters[0]['name']),
                self.race.get_skater_by_name(sorted_skaters[1]['name'])
            )
            print(f"\n⏱️  {description}")
    
    def _compare_with_leader(self, skater, leader_ref) -> Optional[str]:
        """
        Compare current skater's progress with leader reference.
        
        Args:
            skater: Current skater object
            leader_ref: Leader reference dict with lap_times
            
        Returns:
            Colored comparison string or None
        """
        laps_completed = skater.get_laps_completed()
        
        if laps_completed == 0 or not leader_ref.get('lap_times'):
            return None
        
        # Compare cumulative time at same lap count
        current_time = skater.get_total_time()
        leader_time_at_lap = sum(leader_ref['lap_times'][:laps_completed])
        
        diff = current_time - leader_time_at_lap
        
        # ANSI color codes: green for ahead, red for behind
        GREEN = '\033[92m'
        RED = '\033[91m'
        RESET = '\033[0m'
        
        if abs(diff) < 0.01:
            return "even"
        elif diff < 0:
            return f"{GREEN}-{abs(diff):.2f}s{RESET}"
        else:
            return f"{RED}+{diff:.2f}s{RESET}"
    
    def input_lap_time(self):
        """Handle lap time input."""
        print("\nINPUT LAP TIME")
        print("-" * 70)
        print("Commands: 'status' = show status, 'quit' = exit")
        print("Format: '1 15.00' or '15.00 31.2' (both skaters)")
        print()
        
        # Get input
        user_input = input("Input: ").strip()
        
        if user_input.lower() == 'quit':
            return 'quit'
        elif user_input.lower() == 'status':
            return 'status'
        
        parts = user_input.split()
        
        # Check if this is a two-time input (both are times, no skater ID)
        if len(parts) == 2:
            # Check if first part is a skater ID (1, 2, or a name)
            is_skater_id = parts[0] in self.skater_map or self.race.get_skater_by_name(parts[0]) is not None
            
            if not is_skater_id:
                # Try to parse both as times
                time1 = self.predictor.parse_time_input(parts[0])
                time2 = self.predictor.parse_time_input(parts[1])
                
                # If both parse as times and look like reasonable lap times (>5s), record for both skaters
                if time1 is not None and time2 is not None and time1 > 5 and time2 > 5:
                    return self._record_both_skaters(time1, time2)
            
            # Otherwise treat as "<skater> <time>"
            skater_id, time_input = parts
            skater_name = self.skater_map.get(skater_id, skater_id)
            skater = self.race.get_skater_by_name(skater_name)
            
            if not skater:
                print(f"❌ Skater '{skater_id}' not found!")
                return None
            
            if skater.finished:
                print(f"ℹ️  {skater.name} has already finished!")
                return None
            
            lap_time = self.predictor.parse_time_input(time_input)
            if lap_time is None:
                print("❌ Invalid time format!")
                return None
            
            return self._record_single_skater(skater, lap_time)
            
        elif len(parts) == 1:
            # Single input - could be skater ID or time
            skater_id = parts[0]
            skater_name = self.skater_map.get(skater_id, skater_id)
            skater = self.race.get_skater_by_name(skater_name)
            
            if not skater:
                print(f"❌ Skater '{skater_id}' not found!")
                return None
            
            if skater.finished:
                print(f"ℹ️  {skater.name} has already finished!")
                return None
            
            # Ask for time
            time_input = input(f"Lap time for {skater.name} (MM:SS.mmm or SS.mmm): ").strip()
            
            if time_input.lower() == 'done':
                skater.mark_finished(skater.get_total_time())
                print(f"✅ {skater.name} finished with time: {self.predictor.format_time(skater.finish_time)}")
                return 'finished'
            
            lap_time = self.predictor.parse_time_input(time_input)
            if lap_time is None:
                print("❌ Invalid time format!")
                return None
            
            return self._record_single_skater(skater, lap_time)
        else:
            print("❌ Invalid input format!")
            return None
    
    def _record_single_skater(self, skater, lap_time):
        """Record a lap time for a single skater."""
        self.race.add_lap_time(skater.name, lap_time)
        
        laps_completed = skater.get_laps_completed()
        print(f"✅ Lap {laps_completed} recorded: {self.predictor.format_time(lap_time)}")
        
        if skater.finished:
            print(f"🏁 {skater.name} has finished the race!")
            print(f"   Final time: {self.predictor.format_time(skater.finish_time)}")
        
        return 'recorded'
    
    def _record_both_skaters(self, time1, time2):
        """Record lap times for both skaters (1=first time, 2=second time)."""
        skater1_name = self.skater_map.get('1')
        skater2_name = self.skater_map.get('2')
        
        if not skater1_name or not skater2_name:
            print("❌ Both skaters must be configured!")
            return None
        
        skater1 = self.race.get_skater_by_name(skater1_name)
        skater2 = self.race.get_skater_by_name(skater2_name)
        
        # Record both times
        results = []
        
        if skater1 and not skater1.finished:
            self.race.add_lap_time(skater1.name, time1)
            laps1 = skater1.get_laps_completed()
            print(f"✅ {skater1.name} Lap {laps1}: {self.predictor.format_time(time1)}")
            if skater1.finished:
                print(f"   🏁 Finished! Total: {self.predictor.format_time(skater1.finish_time)}")
            results.append('recorded')
        elif skater1 and skater1.finished:
            print(f"ℹ️  {skater1.name} has already finished (time not recorded)")
        
        if skater2 and not skater2.finished:
            self.race.add_lap_time(skater2.name, time2)
            laps2 = skater2.get_laps_completed()
            print(f"✅ {skater2.name} Lap {laps2}: {self.predictor.format_time(time2)}")
            if skater2.finished:
                print(f"   🏁 Finished! Total: {self.predictor.format_time(skater2.finish_time)}")
            results.append('recorded')
        elif skater2 and skater2.finished:
            print(f"ℹ️  {skater2.name} has already finished (time not recorded)")
        
        return 'recorded' if results else None
    
    def run(self):
        """Run the interactive CLI."""
        self.race = self.setup_race()
        
        while not self.race.is_race_finished():
            self.clear_screen()
            self.print_header()
            self.display_race_status()
            
            result = self.input_lap_time()
            
            if result == 'quit':
                print("\nExiting race tracker...")
                break
        
        if self.race.is_race_finished():
            self.clear_screen()
            self.print_header()
            print("\n🏆 RACE COMPLETE! 🏆")
            self.display_race_status()
            
            # Show final results
            status = self.race.get_race_status()
            sorted_skaters = sorted(status['skaters'], key=lambda x: x['total_time'])
            
            print("\nFINAL RESULTS:")
            for i, skater_info in enumerate(sorted_skaters, 1):
                time = self.predictor.format_time(skater_info['total_time'])
                print(f"  {i}. {skater_info['name']:<20} {time}")
            
            if len(sorted_skaters) >= 2:
                winner_time = sorted_skaters[0]['total_time']
                second_time = sorted_skaters[1]['total_time']
                margin = second_time - winner_time
                print(f"\n  Winning margin: {self.predictor.format_time(margin)}")
            
            # Save results to competition
            race_distance = self.race.preset.name
            skater_data = [(s['name'], s['total_time'], 
                           self.race.get_skater_by_name(s['name']).lap_times) 
                          for s in sorted_skaters]
            self.competition.add_race_results(race_distance, skater_data)
            self.competition.save(self.competition_file)
            print("\n✅ Results saved to competition!")
            
            # Display updated leaderboard
            self.display_leaderboard(race_distance)
            
            # Ask if user wants another race
            print()
            response = input("Start another race? (y/n): ").strip().lower()
            if response == 'y':
                self.run()  # Start a new race


def main():
    """Main entry point for CLI."""
    cli = RaceCLI()
    cli.run()


if __name__ == "__main__":
    main()
