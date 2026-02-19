"""
Competition management for tracking multiple races and maintaining leaderboards.
"""
import json
import os
from datetime import datetime
from typing import List, Optional, Dict
from dataclasses import dataclass, field, asdict


@dataclass
class RaceResult:
    """Result from a single race."""
    skater_name: str
    finish_time: float  # in seconds
    lap_times: List[float]  # individual lap times
    race_distance: str  # e.g., "1500m"
    date: str  # ISO format
    position: int  # 1st, 2nd, etc.
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'RaceResult':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class Competition:
    """Manages a competition with multiple races and leaderboards."""
    name: str
    results: List[RaceResult] = field(default_factory=list)
    
    def add_race_results(self, race_distance: str, skater_data: List[tuple]):
        """
        Add results from a completed race.
        
        Args:
            race_distance: Distance of the race (e.g., "1500m")
            skater_data: List of (skater_name, finish_time, lap_times) tuples, sorted by finish time
        """
        date = datetime.now().isoformat()
        
        for position, (skater_name, finish_time, lap_times) in enumerate(skater_data, start=1):
            result = RaceResult(
                skater_name=skater_name,
                finish_time=finish_time,
                lap_times=lap_times,
                race_distance=race_distance,
                date=date,
                position=position
            )
            self.results.append(result)
    
    def get_leaderboard(self, race_distance: Optional[str] = None) -> List[Dict]:
        """
        Get leaderboard showing best times for each skater.
        
        Args:
            race_distance: Filter by specific distance, or None for all distances
            
        Returns:
            List of dicts with skater stats, sorted by best time
        """
        # Filter results by distance if specified
        filtered_results = [r for r in self.results 
                           if race_distance is None or r.race_distance == race_distance]
        
        if not filtered_results:
            return []
        
        # Group by skater and find their best time
        skater_stats = {}
        for result in filtered_results:
            name = result.skater_name
            if name not in skater_stats:
                skater_stats[name] = {
                    'name': name,
                    'best_time': result.finish_time,
                    'best_date': result.date,
                    'races_completed': 0,
                    'wins': 0,
                    'total_time': 0.0
                }
            
            stats = skater_stats[name]
            stats['races_completed'] += 1
            stats['total_time'] += result.finish_time
            
            if result.finish_time < stats['best_time']:
                stats['best_time'] = result.finish_time
                stats['best_date'] = result.date
            
            if result.position == 1:
                stats['wins'] += 1
        
        # Calculate average times
        for stats in skater_stats.values():
            stats['average_time'] = stats['total_time'] / stats['races_completed']
        
        # Sort by best time
        leaderboard = sorted(skater_stats.values(), key=lambda x: x['best_time'])
        
        return leaderboard
    
    def get_current_leader(self, race_distance: Optional[str] = None) -> Optional[Dict]:
        """
        Get the current leader (best time overall).
        
        Args:
            race_distance: Filter by specific distance, or None for all distances
            
        Returns:
            Dict with leader stats or None
        """
        leaderboard = self.get_leaderboard(race_distance)
        return leaderboard[0] if leaderboard else None
    
    def get_recent_races(self, limit: int = 5) -> List[Dict]:
        """
        Get recent race results.
        
        Args:
            limit: Maximum number of races to return
            
        Returns:
            List of race result dicts
        """
        # Group results by date (same race)
        races_by_date = {}
        for result in self.results:
            if result.date not in races_by_date:
                races_by_date[result.date] = []
            races_by_date[result.date].append(result)
        
        # Sort by date descending
        sorted_dates = sorted(races_by_date.keys(), reverse=True)
        
        recent = []
        for date in sorted_dates[:limit]:
            race_results = sorted(races_by_date[date], key=lambda x: x.position)
            if race_results:
                recent.append({
                    'date': date,
                    'distance': race_results[0].race_distance,
                    'results': [{'name': r.skater_name, 'time': r.finish_time, 'position': r.position} 
                               for r in race_results]
                })
        
        return recent
    
    def save(self, filepath: str):
        """Save competition to JSON file."""
        data = {
            'name': self.name,
            'results': [r.to_dict() for r in self.results]
        }
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load(cls, filepath: str) -> Optional['Competition']:
        """Load competition from JSON file."""
        if not os.path.exists(filepath):
            return None
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            results = [RaceResult.from_dict(r) for r in data.get('results', [])]
            return cls(name=data['name'], results=results)
        except (json.JSONDecodeError, KeyError):
            return None
    
    def get_leader_reference(self, race_distance: str) -> Optional[Dict]:
        """
        Get the best race (fastest time) for comparison during live races.
        
        Args:
            race_distance: The race distance to get leader reference for
            
        Returns:
            Dict with leader's name, lap_times, and finish_time or None
        """
        distance_results = [r for r in self.results if r.race_distance == race_distance]
        
        if not distance_results:
            return None
        
        # Find the result with the best (lowest) finish time
        best_result = min(distance_results, key=lambda r: r.finish_time)
        
        return {
            'name': best_result.skater_name,
            'lap_times': best_result.lap_times,
            'finish_time': best_result.finish_time,
            'date': best_result.date
        }
    
    @classmethod
    def load_or_create(cls, filepath: str, name: str) -> 'Competition':
        """Load existing competition or create new one."""
        comp = cls.load(filepath)
        if comp is None:
            comp = cls(name=name)
        return comp
    
    @classmethod
    def list_competitions(cls, directory: str = 'data/competitions') -> List[Dict[str, str]]:
        """
        List all available competitions in a directory.
        
        Args:
            directory: Directory to search for competition files
            
        Returns:
            List of dicts with 'name' and 'filepath'
        """
        if not os.path.exists(directory):
            return []
        
        competitions = []
        for filename in os.listdir(directory):
            if filename.endswith('.json'):
                filepath = os.path.join(directory, filename)
                comp = cls.load(filepath)
                if comp:
                    competitions.append({
                        'name': comp.name,
                        'filepath': filepath,
                        'filename': filename
                    })
        
        return sorted(competitions, key=lambda x: x['name'])
    
    @classmethod
    def list_competitions_by_distance(cls, race_distance: str, directory: str = 'data/competitions') -> List[Dict]:
        """
        List competitions that have results for a specific distance.
        
        Args:
            race_distance: Race distance to filter by (e.g., "1500m")
            directory: Directory to search for competition files
            
        Returns:
            List of dicts with competition info and stats
        """
        all_comps = cls.list_competitions(directory)
        matching = []
        
        for comp_info in all_comps:
            comp = cls.load(comp_info['filepath'])
            if comp:
                # Check if this competition has results for this distance
                distance_results = [r for r in comp.results if r.race_distance == race_distance]
                if distance_results:
                    leader = comp.get_current_leader(race_distance)
                    matching.append({
                        'name': comp.name,
                        'filepath': comp_info['filepath'],
                        'filename': comp_info['filename'],
                        'race_count': len(set(r.date for r in distance_results)),
                        'leader': leader['name'] if leader else None,
                        'best_time': leader['best_time'] if leader else None
                    })
        
        return matching
