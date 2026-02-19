"""
Base UI class for race display operations shared between CLI and demo.
Provides common display methods for race status, results, and leaderboards.
"""
import os
from typing import Optional
from models.competition import Competition
from engine.predictor import PredictionEngine


class BaseRaceUI:
    """Base class for race display functionality."""
    
    def __init__(self, competition_file: str):
        """Initialize the base UI."""
        self.race = None
        self.predictor = PredictionEngine()
        self.competition_file = competition_file
        self.competition = Competition.load_or_create(competition_file, "Ice Skating Competition")
    
    def clear_screen(self):
        """Clear the terminal screen."""
        os.system('clear' if os.name != 'nt' else 'cls')
    
    def print_header(self):
        """Print application header."""
        print("=" * 70)
        print(" " * 15 + "🏁 ICE SKATING RACE PREDICTOR 🏁")
        print("=" * 70)
        print()
    
    def display_race_status(self):
        """Display current race status."""
        if not self.race:
            return
        
        print(f"\nRACE STATUS - {self.race.preset.name} ({self.race.total_laps} Laps)")
        
        # Display skater ID mapping if available (from CLI subclass)
        if hasattr(self, 'skater_map') and self.skater_map:
            print("\n💡 Quick Input: ", end="")
            print(" | ".join([f"{id}={name}" for id, name in sorted(self.skater_map.items())]))
        
        # Get leader reference from competition history
        leader_ref = self.competition.get_leader_reference(self.race.preset.name)
        if leader_ref:
            print(f"\n📊 Leader Reference: {leader_ref['name']} - {self.predictor.format_time(leader_ref['finish_time'])}")
        
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
    
    def display_final_results(self):
        """Display final race results."""
        status = self.race.get_race_status()
        sorted_skaters = sorted(status['skaters'], key=lambda x: x['total_time'])
        
        print("\nFINAL RESULTS:")
        for i, skater_info in enumerate(sorted_skaters, 1):
            time_str = self.predictor.format_time(skater_info['total_time'])
            print(f"  {i}. {skater_info['name']:<20} {time_str}")
        
        if len(sorted_skaters) >= 2:
            winner_time = sorted_skaters[0]['total_time']
            second_time = sorted_skaters[1]['total_time']
            margin = second_time - winner_time
            print(f"\n  Winning margin: {self.predictor.format_time(margin)}")
        
        return sorted_skaters
    
    def display_leaderboard(self, race_distance: Optional[str] = None):
        """Display competition leaderboard."""
        print("\n📊 LEADERBOARD")
        if race_distance:
            print(f"Distance: {race_distance}")
        
        leaderboard = self.competition.get_leaderboard(race_distance)
        
        if not leaderboard:
            print("No races completed yet.")
            return
        
        # Show current leader
        leader = leaderboard[0]
        print(f"👑 CURRENT LEADER: {leader['name']}")
        print(f"   Best Time: {self.predictor.format_time(leader['best_time'])}")
        print(f"   Wins: {leader['wins']} / {leader['races_completed']} races")
        
        # Show full leaderboard
        print(f"\n{'RANK':<6} {'SKATER':<20} {'BEST TIME':<15} {'AVG TIME':<15} {'RACES':<8}")
        print("-" * 70)
        
        for rank, stats in enumerate(leaderboard, 1):
            best_time = self.predictor.format_time(stats['best_time'])
            avg_time = self.predictor.format_time(stats['average_time'])
            races = f"{stats['races_completed']}"
            
            emoji = "👑" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "  "
            print(f"{emoji} {rank:<3} {stats['name']:<20} {best_time:<15} {avg_time:<15} {races:<8}")
