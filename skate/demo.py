"""
Demo script showing programmatic usage of the race predictor.
This demonstrates the API without requiring interactive input.
"""
from models.skater import Skater
from models.race import Race
from models.race_preset import RacePreset
from engine.predictor import PredictionEngine


def run_demo():
    """Run a demonstration race."""
    print("=" * 70)
    print(" " * 15 + "🏁 RACE PREDICTOR DEMO 🏁")
    print("=" * 70)
    print()
    
    # Load a race preset (1500m)
    preset = RacePreset.load_preset("1500m")
    if not preset:
        print("❌ Failed to load race preset")
        return
    
    # Create two skaters
    skater1 = Skater(name="Erik Hoff")
    skater2 = Skater(name="Anna Berg")
    
    race = Race(preset=preset, skaters=[skater1, skater2])
    predictor = PredictionEngine()
    
    print(f"Setting up a {preset.name} race ({preset.total_distance}m)")
    print(f"Laps: {preset.total_laps} (First lap: {preset.get_lap_distance(1)}m, then {preset.lap_distance}m)")
    print(f"Skaters: {skater1.name} vs {skater2.name}")
    print()
    
    # Simulate lap times
    print("=" * 70)
    print("SIMULATING RACE...")
    print("=" * 70)
    print()
    
    # Lap 1 (300m - shorter first lap)
    print("LAP 1 (300m):")
    race.add_lap_time("Erik Hoff", 23.5)  # Shorter lap
    race.add_lap_time("Anna Berg", 23.2)
    print(f"  {skater1.name}: {predictor.format_time(23.5)}")
    print(f"  {skater2.name}: {predictor.format_time(23.2)}")
    
    gap, desc = predictor.calculate_gap(skater1, skater2)
    print(f"  Gap: {desc}")
    print()
    
    # Lap 2 (400m)
    print("LAP 2 (400m):")
    race.add_lap_time("Erik Hoff", 31.3)
    race.add_lap_time("Anna Berg", 31.4)
    print(f"  {skater1.name}: {predictor.format_time(31.3)}")
    print(f"  {skater2.name}: {predictor.format_time(31.4)}")
    print(f"  Current leader: {race.get_current_leader().name}")
    print()
    
    # Show predictions after 2 laps
    print("PREDICTIONS AFTER 2 LAPS:")
    print("-" * 70)
    pred1 = skater1.predict_finish_time(preset)
    pred2 = skater2.predict_finish_time(preset)
    
    print(f"  {skater1.name}:")
    print(f"    Current time: {predictor.format_time(skater1.get_total_time())}")
    print(f"    Average lap: {predictor.format_time(skater1.get_average_lap_time())}")
    print(f"    Predicted finish: {predictor.format_time(pred1)}")
    print()
    print(f"  {skater2.name}:")
    print(f"    Current time: {predictor.format_time(skater2.get_total_time())}")
    print(f"    Average lap: {predictor.format_time(skater2.get_average_lap_time())}")
    print(f"    Predicted finish: {predictor.format_time(pred2)}")
    print()
    
    predicted_winner = race.get_predicted_winner()
    print(f"  Predicted winner: {predicted_winner.name}")
    print()
    
    # Complete remaining laps (3-4)
    print("=" * 70)
    print("COMPLETING REMAINING LAPS...")
    print("=" * 70)
    print()
    
    # Lap 3 (400m)
    race.add_lap_time("Erik Hoff", 31.6)
    race.add_lap_time("Anna Berg", 31.5)
    print(f"Lap 3 (400m): {skater1.name} {predictor.format_time(31.6)}, "
          f"{skater2.name} {predictor.format_time(31.5)}")
    
    # Lap 4 (400m) - Final lap
    race.add_lap_time("Erik Hoff", 31.8)
    race.add_lap_time("Anna Berg", 31.7)
    print(f"Lap 4 (400m): {skater1.name} {predictor.format_time(31.8)}, "
          f"{skater2.name} {predictor.format_time(31.7)}")
    print()
    
    # Final results
    print("=" * 70)
    print(" " * 25 + "🏆 FINAL RESULTS 🏆")
    print("=" * 70)
    print()
    
    status = race.get_race_status()
    sorted_skaters = sorted(status['skaters'], key=lambda x: x['total_time'])
    
    for i, skater_info in enumerate(sorted_skaters, 1):
        time = predictor.format_time(skater_info['total_time'])
        avg = predictor.format_time(skater_info['average_lap'])
        print(f"{i}. {skater_info['name']:<20} {time}")
        print(f"   Average lap time: {avg}")
        if i == 1:
            print(f"   🥇 WINNER!")
        print()
    
    if len(sorted_skaters) >= 2:
        winner_time = sorted_skaters[0]['total_time']
        second_time = sorted_skaters[1]['total_time']
        margin = second_time - winner_time
        print(f"Winning margin: {predictor.format_time(margin)}")
    
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
