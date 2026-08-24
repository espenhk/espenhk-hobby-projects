"""
Prediction engine for race finish times and analysis.
"""
from models.skater import Skater


class PredictionEngine:
    """Advanced prediction algorithms for race outcomes."""
    
    @staticmethod
    def predict_finish_time_simple(skater: Skater, total_laps: int) -> float | None:
        """
        Simple average-based prediction.
        
        Args:
            skater: Skater to predict for
            total_laps: Total laps in race
            
        Returns:
            Predicted finish time in seconds or None
        """
        return skater.predict_finish_time(total_laps)
    
    @staticmethod
    def predict_finish_time_weighted(skater: Skater, total_laps: int, 
                                     recent_weight: float = 0.6) -> float | None:
        """
        Weighted prediction giving more importance to recent laps.
        
        Args:
            skater: Skater to predict for
            total_laps: Total laps in race
            recent_weight: Weight for recent laps (0-1)
            
        Returns:
            Predicted finish time in seconds or None
        """
        if skater.finished:
            return skater.finish_time
        
        if not skater.lap_times:
            return None
        
        laps_completed = len(skater.lap_times)
        laps_remaining = total_laps - laps_completed
        
        if laps_completed == 0:
            return None
        
        # Calculate weighted average (more weight on recent laps)
        if laps_completed == 1:
            avg_lap = skater.lap_times[0]
        else:
            # Split into first half and second half
            mid_point = laps_completed // 2
            early_laps = skater.lap_times[:mid_point] if mid_point > 0 else []
            recent_laps = skater.lap_times[mid_point:]
            
            early_avg = sum(early_laps) / len(early_laps) if early_laps else 0
            recent_avg = sum(recent_laps) / len(recent_laps) if recent_laps else 0
            
            # Weighted average
            avg_lap = (1 - recent_weight) * early_avg + recent_weight * recent_avg
        
        current_time = sum(skater.lap_times)
        predicted_remaining = avg_lap * laps_remaining
        
        return current_time + predicted_remaining
    
    @staticmethod
    def predict_with_fatigue(skater: Skater, total_laps: int, 
                            fatigue_factor: float = 0.005) -> float | None:
        """
        Predict with fatigue factor (times get slower over race).
        
        Args:
            skater: Skater to predict for
            total_laps: Total laps in race
            fatigue_factor: Factor for lap time increase per lap (default 0.5%)
            
        Returns:
            Predicted finish time in seconds or None
        """
        if skater.finished:
            return skater.finish_time
        
        avg_lap = skater.get_average_lap_time()
        if avg_lap is None:
            return None
        
        laps_completed = skater.get_laps_completed()
        laps_remaining = total_laps - laps_completed
        current_time = skater.get_total_time()
        
        # Calculate remaining time with progressive fatigue
        predicted_remaining = 0.0
        for i in range(laps_remaining):
            lap_num = laps_completed + i + 1
            # Each lap gets slightly slower
            lap_time = avg_lap * (1 + fatigue_factor * lap_num)
            predicted_remaining += lap_time
        
        return current_time + predicted_remaining
    
    @staticmethod
    def calculate_gap(skater1: Skater, skater2: Skater) -> tuple[float, str]:
        """
        Calculate time gap between two skaters.
        
        Args:
            skater1: First skater
            skater2: Second skater
            
        Returns:
            Tuple of (gap in seconds, description)
        """
        time1 = skater1.get_total_time()
        time2 = skater2.get_total_time()
        
        gap = abs(time1 - time2)
        
        if time1 < time2:
            leader = skater1.name
            trailer = skater2.name
        else:
            leader = skater2.name
            trailer = skater1.name
        
        description = f"{trailer} is {gap:.3f}s behind {leader}"
        
        return gap, description
    
    @staticmethod
    def format_time(seconds: float) -> str:
        """
        Format seconds to MM:SS.mmm format.
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted time string
        """
        if seconds is None:
            return "N/A"
        
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        
        if minutes > 0:
            return f"{minutes}:{remaining_seconds:06.3f}"
        else:
            return f"{remaining_seconds:.3f}s"
    
    @staticmethod
    def parse_time_input(time_str: str) -> float | None:
        """
        Parse time input from various formats.
        Supports: MM:SS.mmm, SS.mmm, SS
        
        Args:
            time_str: Time string to parse
            
        Returns:
            Time in seconds or None if invalid
        """
        try:
            time_str = time_str.strip()
            
            # Check for MM:SS.mmm format
            if ':' in time_str:
                parts = time_str.split(':')
                if len(parts) == 2:
                    minutes = int(parts[0])
                    seconds = float(parts[1])
                    return minutes * 60 + seconds
            else:
                # Just seconds
                return float(time_str)
        except (ValueError, IndexError):
            return None
        
        return None
