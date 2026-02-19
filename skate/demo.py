"""
Automated demo of live race tracking with pre-determined times.
Uses the shared BaseRaceUI for display while automating lap time inputs.
"""
import time
from models.skater import Skater
from models.race import Race
from models.race_preset import RacePreset
from ui.base_ui import BaseRaceUI


class RaceDemo(BaseRaceUI):
    """Automated demo of live race tracking."""
    
    def __init__(self):
        """Initialize the demo."""
        super().__init__('data/competitions/demo_competition.json')
    
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
        lap_times = [
            (23.5, 23.2),   # Lap 1 (300m)
            (31.3, 31.4),   # Lap 2 (400m)
            (31.6, 31.5),   # Lap 3 (400m)
            (31.8, 31.7),   # Lap 4 (400m) - final
        ]
        
        # Record each lap with 3 second delays
        for lap_num, (time1, time2) in enumerate(lap_times, 1):
            self._record_lap_times(time1, time2, lap_num)
        
        # Display final results
        self._show_final_results()
    
    def _record_lap_times(self, time1, time2, lap_num):
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
    
    def _show_final_results(self):
        """Display final race results and save to competition."""
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
        print("\n✅ Results saved to demo_competition.json!")
        
        # Display leaderboard
        self.display_leaderboard(race_distance)


def run_demo():
    """Entry point for the demo."""
    demo = RaceDemo()
    demo.run_demo()


if __name__ == "__main__":
    run_demo()
