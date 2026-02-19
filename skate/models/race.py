"""
Race management module for tracking race state and skaters.
"""
from typing import List, Optional, Tuple
from models.skater import Skater
from models.race_preset import RacePreset


class Race:
    """Manages a skating race with multiple skaters."""
    
    def __init__(self, preset: RacePreset, skaters: List[Skater]):
        """
        Initialize a race.
        
        Args:
            preset: RacePreset defining the race distance and lap configuration
            skaters: List of skaters in the race
        """
        self.preset = preset
        self.total_laps = preset.total_laps
        self.skaters = skaters
        self.race_active = True
        
    def add_lap_time(self, skater_name: str, lap_time: float) -> bool:
        """
        Add a lap time for a specific skater.
        
        Args:
            skater_name: Name of the skater
            lap_time: Lap time in seconds
            
        Returns:
            True if successful, False if skater not found
        """
        skater = self.get_skater_by_name(skater_name)
        if skater:
            skater.add_lap_time(lap_time)
            
            # Check if skater finished
            if skater.get_laps_completed() >= self.total_laps:
                skater.mark_finished(skater.get_total_time())
            
            return True
        return False
    
    def get_skater_by_name(self, name: str) -> Optional[Skater]:
        """
        Get a skater by name.
        
        Args:
            name: Skater name
            
        Returns:
            Skater object or None if not found
        """
        for skater in self.skaters:
            if skater.name.lower() == name.lower():
                return skater
        return None
    
    def get_current_leader(self) -> Optional[Skater]:
        """
        Get the current race leader based on total elapsed time.
        
        Returns:
            Leading skater or None if no laps completed
        """
        active_skaters = [s for s in self.skaters if s.get_laps_completed() > 0]
        
        if not active_skaters:
            return None
        
        # Sort by total time (lower is better)
        return min(active_skaters, key=lambda s: s.get_total_time())
    
    def get_predicted_winner(self) -> Optional[Skater]:
        """
        Get the predicted winner based on projected finish times.
        
        Returns:
            Predicted winner or None if no predictions available
        """
        predictions = []
        for skater in self.skaters:
            pred_time = skater.predict_finish_time(self.preset)
            if pred_time is not None:
                predictions.append((skater, pred_time))
        
        if not predictions:
            return None
        
        # Sort by predicted time (lower is better)
        return min(predictions, key=lambda x: x[1])[0]
    
    def get_race_status(self) -> dict:
        """
        Get comprehensive race status.
        
        Returns:
            Dictionary with race status information
        """
        leader = self.get_current_leader()
        predicted_winner = self.get_predicted_winner()
        
        status = {
            'total_laps': self.total_laps,
            'active': self.race_active,
            'leader': leader.name if leader else None,
            'leader_time': leader.get_total_time() if leader else None,
            'predicted_winner': predicted_winner.name if predicted_winner else None,
            'skaters': []
        }
        
        for skater in self.skaters:
            skater_info = {
                'name': skater.name,
                'laps_completed': skater.get_laps_completed(),
                'total_time': skater.get_total_time(),
                'average_lap': skater.get_average_lap_time(),
                'predicted_finish': skater.predict_finish_time(self.preset),
                'finished': skater.finished
            }
            status['skaters'].append(skater_info)
        
        return status
    
    def is_race_finished(self) -> bool:
        """
        Check if the race is finished (all skaters completed).
        
        Returns:
            True if all skaters have finished
        """
        return all(skater.finished for skater in self.skaters)
    
    def get_comparison(self, skater_name: str) -> Optional[dict]:
        """
        Get comparison of a skater with the current leader.
        
        Args:
            skater_name: Name of skater to compare
            
        Returns:
            Dictionary with comparison data or None
        """
        skater = self.get_skater_by_name(skater_name)
        leader = self.get_current_leader()
        
        if not skater or not leader or skater == leader:
            return None
        
        time_diff = skater.get_total_time() - leader.get_total_time()
        
        return {
            'skater': skater.name,
            'leader': leader.name,
            'time_difference': time_diff,
            'behind': time_diff > 0
        }
