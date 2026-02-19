"""
Demo script showing live race tracking with automatic time inputs.
Simulates the interactive race_predictor.py experience with automatic inputs
and 3-second delays between each lap time.
"""
import os
import time
from models.skater import Skater
from models.race import Race
from models.race_preset import RacePreset
from models.competition import Competition
from engine.predictor import PredictionEngine


class RaceDemo:
    """Automated demo of live race tracking."""
    
    def __init__(self):
        """Initialize the demo."""
        self.race = None
        self.predictor = PredictionEngine()
        self.competition_file = 'data/competitions/demo_competition.json'
        self.competition = Competition.load_or_create(
            self.competition_file, 
            "Demo Competition"
        )
        
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
        print(f"\nRACE STATUS - {self.race.preset.name} ({self.race.total_laps} Laps)")
        
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
        
        print(f"\n{'SKATER':<20} {'LAPS':<8} {'TIME':<15} {'AVG LAP':<15} {'PRED FINISH':<15}")
        print("-" * 90)
        
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
                
                print(f"{name:<20} {laps:<8} {total_time:<15} {avg_lap:<15} {pred_finish:<15}")
        
        # Show comparison if there's a leader
        if len(sorted_skaters) >= 2 and sorted_skaters[0]['laps_completed'] > 0:
            gap, description = self.predictor.calculate_gap(
                self.race.get_skater_by_name(sorted_skaters[0]['name']),
                self.race.get_skater_by_name(sorted_skaters[1]['name'])
            )
            print(f"\n⏱️  {description}")
    
    def record_lap_times(self, time1, time2, lap_num):
        """Record lap times for both skaters with simulated input."""
        self.clear_screen()
        self.print_header()
        self.display_race_status()
        
        print("\nINPUT LAP TIME")
        print("-" * 70)
        print(f"Input: {time1:.2f} {time2:.2f}")
        print()
        
        skaters = self.race.skaters
        
        # Record times for both skaters
        if not skaters[0].finished:
            self.race.add_lap_time(skaters[0].name, time1)
            print(f"✅ {skaters[0].name} Lap {skaters[0].get_laps_completed()}: {self.predictor.format_time(time1)}")
            if skaters[0].finished:
                print(f"   🏁 Finished! Total: {self.predictor.format_time(skaters[0].finish_time)}")
        
        if not skaters[1].finished:
            self.race.add_lap_time(skaters[1].name, time2)
            print(f"✅ {skaters[1].name} Lap {skaters[1].get_laps_completed()}: {self.predictor.format_time(time2)}")
            if skaters[1].finished:
                print(f"   🏁 Finished! Total: {self.predictor.format_time(skaters[1].finish_time)}")
        
        # Wait 3 seconds before next input
        time.sleep(3)
    
    def display_final_results(self):
        """Display final race results."""
        self.clear_screen()
        self.print_header()
        print("\n🏆 RACE COMPLETE! 🏆")
        self.display_race_status()
        
        # Show final results
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
        
        # Save results to competition
        race_distance = self.race.preset.name
        skater_data = [(s['name'], s['total_time'], 
                       self.race.get_skater_by_name(s['name']).lap_times) 
                      for s in sorted_skaters]
        self.competition.add_race_results(race_distance, skater_data)
        self.competition.save(self.competition_file)
        print("\n✅ Results saved to demo_competition.json!")
        
        # Display leaderboard
        self.display_leaderboard(race_distance)
    
    def display_leaderboard(self, race_distance=None):
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
    
    def run_demo(self):
        """Run a demonstration race with automatic inputs."""
        self.clear_screen()
        self.print_header()
        
        print("RACE SETUP")
        print("-" * 70)
        
        # Load a race preset (1500m)
        preset = RacePreset.load_preset("1500m")
        if not preset:
            print("❌ Failed to load race preset")
            return
        
        print(f"\n✓ Loaded {preset.name} race:")
        print(f"  Total distance: {preset.total_distance}m")
        print(f"  Laps: {preset.total_laps}")
        print(f"  First lap: {preset.get_lap_distance(1)}m")
        print(f"  Remaining laps: {preset.lap_distance}m")
        print()
        
        # Create skaters
        skater1 = Skater(name="Erik Hoff")
        skater2 = Skater(name="Anna Berg")
        print(f"Skaters: {skater1.name} vs {skater2.name}")
        
        # Create race
        self.race = Race(preset=preset, skaters=[skater1, skater2])
        
        print("\nStarting automated demo in 3 seconds...")
        time.sleep(3)
        
        # Define lap times for the demo
        # Lap 1 (300m - shorter first lap)
        lap_times = [
            (23.5, 23.2),   # Lap 1
            (31.3, 31.4),   # Lap 2
            (31.6, 31.5),   # Lap 3
            (31.8, 31.7),   # Lap 4 (final)
        ]
        
        # Record each lap with 3 second delays
        for lap_num, (time1, time2) in enumerate(lap_times, 1):
            self.record_lap_times(time1, time2, lap_num)
        
        # Display final results
        self.display_final_results()


def run_demo():
    """Entry point for the demo."""
    demo = RaceDemo()
    demo.run_demo()


if __name__ == "__main__":
    run_demo()
