"""
Base UI class for race display operations shared between CLI and demo.
Provides common display methods for race status, results, and leaderboards.
"""

from engine.predictor import PredictionEngine
from models.competition import Competition


class BaseRaceUI:
    """Base class for race display functionality."""
    
    def __init__(self, competition_file: str):
        """Initialize the base UI."""
        self.race = None
        self.predictor = PredictionEngine()
        self.competition_file = competition_file
        self.competition = Competition.load_or_create(competition_file, "Ice Skating Competition")
    
    def _format_name(self, full_name: str) -> str:
        """Format full name to 'F.S. Name' format (first initial, second initial if present, last name).
        
        Examples: 'Anna Berg' -> 'A. Berg', 'Anna Beth Berg' -> 'A.B. Berg'
        """
        parts = full_name.strip().split()
        if len(parts) == 1:
            return full_name
        
        # Last part is always the last name
        last_name = parts[-1]
        
        # Format preceding names as initials
        initials = '.'.join([p[0] for p in parts[:-1]]) + '.'
        
        return f"{initials} {last_name}"
    
    def clear_screen(self):
        """Preserve terminal history by not clearing (just add spacing)."""
        print("\n" * 3)
    
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
            print("💡 Quick Input: ", end="")
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
        
        # Header with proper alignment - more spacing between time columns
        print(f"\n{'SKATER':<15} {'LAPS':<8} {'LAP TIME':<24}  {'TOTAL TIME':<24}  {'PRED FINISH':<24}")
        print("-" * 105)
        
        # Sort skaters by current time
        sorted_skaters = sorted(status['skaters'], 
                               key=lambda x: x['total_time'] if x['laps_completed'] > 0 else float('inf'))
        
        for skater_info in sorted_skaters:
            name = skater_info['name']
            laps = f"{skater_info['laps_completed']}/{self.race.total_laps}"
            
            if skater_info['finished']:
                formatted_name = self._format_name(name)
                total_time = self.predictor.format_time(skater_info['total_time'])
                print(f"{formatted_name:<15} {'DONE':<8} {'':<24}  {total_time:<24}  {'✓ FINISHED':<24}")
            else:
                # Get the skater object for access to lap_times
                skater = self.race.get_skater_by_name(name)
                
                # Lap time comparison (most recent lap vs leader's same lap)
                lap_time_str = ""
                if skater_info['laps_completed'] > 0:
                    recent_lap_time = skater.lap_times[-1]
                    lap_time_str = self.predictor.format_time(recent_lap_time)
                    if leader_ref and skater_info['laps_completed'] <= len(leader_ref.get('lap_times', [])):
                        lap_diff = self._get_individual_lap_difference(
                            recent_lap_time, 
                            leader_ref['lap_times'][skater_info['laps_completed'] - 1]
                        )
                        if lap_diff:
                            lap_time_str += f" {lap_diff}"
                else:
                    lap_time_str = "N/A"
                
                # Total time comparison (cumulative time vs leader at this lap)
                total_time_str = ""
                if skater_info['laps_completed'] > 0:
                    total_time = skater_info['total_time']
                    total_time_str = self.predictor.format_time(total_time)
                    if leader_ref:
                        lap_diff = self._get_lap_time_difference(total_time, leader_ref, skater_info['laps_completed'])
                        if lap_diff:
                            total_time_str += f" {lap_diff}"
                else:
                    total_time_str = "N/A"
                
                # Predicted finish comparison
                pred_finish_str = ""
                if skater_info['predicted_finish']:
                    pred_finish_str = self.predictor.format_time(skater_info['predicted_finish'])
                    if leader_ref:
                        pred_diff = self._get_pred_time_difference(skater_info['predicted_finish'], leader_ref)
                        if pred_diff:
                            pred_finish_str += f" {pred_diff}"
                else:
                    pred_finish_str = "N/A"
                
                formatted_name = self._format_name(name)
                print(f"{formatted_name:<15} {laps:<8} {lap_time_str:<24}  {total_time_str:<24}  {pred_finish_str:<24}")
        
        # Show comparison if there's a leader
        if len(sorted_skaters) >= 2 and sorted_skaters[0]['laps_completed'] > 0:
            gap, description = self.predictor.calculate_gap(
                self.race.get_skater_by_name(sorted_skaters[0]['name']),
                self.race.get_skater_by_name(sorted_skaters[1]['name'])
            )
            print(f"\n⏱️  {description}")
    
    def _compare_with_leader(self, skater, leader_ref) -> str | None:
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
    
    def _get_individual_lap_difference(self, current_lap_time, leader_lap_time) -> str | None:
        """
        Get the difference between current lap time and leader's lap time for that lap.
        
        Args:
            current_lap_time: Current lap time in seconds
            leader_lap_time: Leader's lap time for the same lap in seconds
            
        Returns:
            Colored string like " (-0.2s)" or None
        """
        diff = current_lap_time - leader_lap_time
        
        GREEN = '\033[92m'
        RED = '\033[91m'
        RESET = '\033[0m'
        
        if abs(diff) < 0.01:
            return ""
        elif diff < 0:
            return f"{GREEN}(-{abs(diff):.2f}s){RESET}"
        else:
            return f"{RED}(+{diff:.2f}s){RESET}"
    
    def _get_lap_time_difference(self, current_total_time, leader_ref, laps_completed) -> str | None:
        """
        Get the difference between current cumulative time and leader's cumulative time at same lap.
        
        Args:
            current_total_time: Current skater's total time
            leader_ref: Leader reference dict with lap_times
            laps_completed: Number of laps completed
            
        Returns:
            Colored string like " (-1.2s)" or None
        """
        if not leader_ref.get('lap_times') or laps_completed == 0:
            return None
        
        leader_time_at_lap = sum(leader_ref['lap_times'][:laps_completed])
        diff = current_total_time - leader_time_at_lap
        
        GREEN = '\033[92m'
        RED = '\033[91m'
        RESET = '\033[0m'
        
        if abs(diff) < 0.01:
            return ""
        elif diff < 0:
            return f" {GREEN}(-{abs(diff):.1f}s){RESET}"
        else:
            return f" {RED}(+{diff:.1f}s){RESET}"
    
    def _get_pred_time_difference(self, current_pred_time, leader_ref) -> str | None:
        """
        Get the difference between predicted finish time and leader's predicted time.
        
        Args:
            current_pred_time: Current skater's predicted finish time
            leader_ref: Leader reference dict with finish_time
            
        Returns:
            Colored string like " (-2.0s)" or None
        """
        if current_pred_time is None or leader_ref.get('finish_time') is None:
            return None
        
        leader_pred_time = leader_ref['finish_time']
        diff = current_pred_time - leader_pred_time
        
        GREEN = '\033[92m'
        RED = '\033[91m'
        RESET = '\033[0m'
        
        if abs(diff) < 0.01:
            return ""
        elif diff < 0:
            return f" {GREEN}(-{abs(diff):.1f}s){RESET}"
        else:
            return f" {RED}(+{diff:.1f}s){RESET}"
    
    def display_final_results(self):
        """Display final race results."""
        status = self.race.get_race_status()
        sorted_skaters = sorted(status['skaters'], key=lambda x: x['total_time'])
        
        print("\nFINAL RESULTS:")
        for i, skater_info in enumerate(sorted_skaters, 1):
            formatted_name = self._format_name(skater_info['name'])
            time_str = self.predictor.format_time(skater_info['total_time'])
            print(f"  {i}. {formatted_name:<15} {time_str}")
        
        if len(sorted_skaters) >= 2:
            winner_time = sorted_skaters[0]['total_time']
            second_time = sorted_skaters[1]['total_time']
            margin = second_time - winner_time
            print(f"\n  Winning margin: {self.predictor.format_time(margin)}")
        
        return sorted_skaters
    
    def display_leaderboard(self, race_distance: str | None = None):
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
        print(f"\n{'RANK':<6} {'SKATER':<15} {'BEST TIME':<15} {'AVG TIME':<15} {'RACES':<8}")
        print("-" * 65)
        
        for rank, stats in enumerate(leaderboard, 1):
            formatted_name = self._format_name(stats['name'])
            best_time = self.predictor.format_time(stats['best_time'])
            avg_time = self.predictor.format_time(stats['average_time'])
            races = f"{stats['races_completed']}"
            
            emoji = "👑" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "  "
            print(f"{emoji} {rank:<3} {formatted_name:<15} {best_time:<15} {avg_time:<15} {races:<8}")
