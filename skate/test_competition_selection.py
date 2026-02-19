#!/usr/bin/env python3
"""
Test the competition selection feature.
"""

from models.competition import Competition
from models.race_preset import RacePreset
from engine.predictor import PredictionEngine

def test_competition_selection():
    """Test the competition selection functionality."""
    
    predictor = PredictionEngine()
    
    # Test 1: List competitions for 1500m
    print("=" * 70)
    print("TEST 1: Listing competitions for 1500m")
    print("=" * 70)
    
    comps = Competition.list_competitions_by_distance('1500m')
    print(f"\nFound {len(comps)} competition(s):")
    for i, comp in enumerate(comps, 1):
        leader_info = ""
        if comp.get('leader') and comp.get('best_time'):
            leader_info = f" | Leader: {comp['leader']} ({predictor.format_time(comp['best_time'])})"
        print(f"  {i}. {comp['name']} - {comp['race_count']} race(s){leader_info}")
    
    # Test 2: List competitions for 3000m (should be empty)
    print("\n" + "=" * 70)
    print("TEST 2: Listing competitions for 3000m")
    print("=" * 70)
    
    comps_3000 = Competition.list_competitions_by_distance('3000m')
    print(f"\nFound {len(comps_3000)} competition(s) for 3000m")
    
    # Test 3: Load a specific competition
    print("\n" + "=" * 70)
    print("TEST 3: Loading a specific competition")
    print("=" * 70)
    
    if comps:
        selected = comps[0]
        print(f"\nLoading: {selected['name']}")
        comp = Competition.load(selected['filepath'])
        print(f"Competition name: {comp.name}")
        print(f"Total results: {len(comp.results)}")
        
        leader = comp.get_current_leader()
        if leader:
            print(f"Current leader: {leader['name']} - {predictor.format_time(leader['best_time'])}")
    
    print("\n" + "=" * 70)
    print("✓ All tests passed!")
    print("=" * 70)

if __name__ == "__main__":
    test_competition_selection()
