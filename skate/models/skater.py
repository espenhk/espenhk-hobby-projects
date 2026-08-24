"""
Skater data model for tracking individual skater performance.
"""
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.race_preset import RacePreset


@dataclass
class Skater:
    """Represents a skater in a race."""
    
    name: str
    bib_number: int | None = None
    lap_times: list[float] = field(default_factory=list)
    finished: bool = False
    finish_time: float | None = None
    
    # Future features - historical data
    personal_best: float | None = None
    season_best: float | None = None
    
    def add_lap_time(self, lap_time: float) -> None:
        """
        Add a lap time for this skater.
        
        Args:
            lap_time: Lap time in seconds
        """
        self.lap_times.append(lap_time)
    
    def get_total_time(self) -> float:
        """
        Get the total elapsed time for completed laps.
        
        Returns:
            Total time in seconds
        """
        return sum(self.lap_times)
    
    def get_average_lap_time(self) -> float | None:
        """
        Calculate average lap time.
        
        Returns:
            Average lap time in seconds, or None if no laps completed
        """
        if not self.lap_times:
            return None
        return sum(self.lap_times) / len(self.lap_times)
    
    def get_laps_completed(self) -> int:
        """
        Get number of laps completed.
        
        Returns:
            Number of laps completed
        """
        return len(self.lap_times)
    
    def mark_finished(self, finish_time: float) -> None:
        """
        Mark the skater as finished.
        
        Args:
            finish_time: Final finish time in seconds
        """
        self.finished = True
        self.finish_time = finish_time
    
    def predict_finish_time(self, preset: 'RacePreset') -> float | None:
        """
        Predict finish time based on current average pace, accounting for variable lap distances.
        
        Args:
            preset: RacePreset with lap distance configuration
            
        Returns:
            Predicted finish time in seconds, or None if no data
        """
        if self.finished:
            return self.finish_time
        
        if not self.lap_times:
            return None
        
        laps_completed = self.get_laps_completed()
        current_time = self.get_total_time()
        
        # Calculate average speed (meters per second) based on completed laps
        total_distance_covered = sum(
            preset.get_lap_distance(i) or 0 
            for i in range(1, laps_completed + 1)
        )
        
        if total_distance_covered == 0:
            return None
        
        avg_speed = total_distance_covered / current_time  # m/s
        
        # Calculate remaining distance
        remaining_distance = sum(
            preset.get_lap_distance(i) or 0 
            for i in range(laps_completed + 1, preset.total_laps + 1)
        )
        
        # Predict remaining time
        predicted_remaining = remaining_distance / avg_speed
        
        return current_time + predicted_remaining
    
    def __str__(self) -> str:
        """String representation of skater."""
        status = "FINISHED" if self.finished else f"Lap {len(self.lap_times)}"
        return f"{self.name} - {status}"
