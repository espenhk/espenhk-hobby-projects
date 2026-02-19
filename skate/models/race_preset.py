"""
Race preset management for loading predefined race configurations.
"""
import json
import os
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class LapInfo:
    """Information about a single lap."""
    lap_number: int
    distance: int  # in meters


@dataclass
class RacePreset:
    """Preset configuration for a race distance."""
    name: str
    total_distance: int  # in meters
    lap_distance: int  # standard lap distance (usually 400m)
    laps: List[LapInfo]
    
    @property
    def total_laps(self) -> int:
        """Get total number of laps."""
        return len(self.laps)
    
    def get_lap_distance(self, lap_number: int) -> Optional[int]:
        """
        Get distance for a specific lap.
        
        Args:
            lap_number: Lap number (1-indexed)
            
        Returns:
            Distance in meters or None if lap not found
        """
        for lap in self.laps:
            if lap.lap_number == lap_number:
                return lap.distance
        return None
    
    @classmethod
    def from_file(cls, filepath: str) -> 'RacePreset':
        """
        Load a race preset from a JSON file.
        
        Args:
            filepath: Path to the preset file
            
        Returns:
            RacePreset instance
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        laps = [LapInfo(lap_number=lap['lap'], distance=lap['distance']) 
                for lap in data['laps']]
        
        return cls(
            name=data['name'],
            total_distance=data['total_distance'],
            lap_distance=data['lap_distance'],
            laps=laps
        )
    
    @classmethod
    def load_preset(cls, preset_name: str) -> Optional['RacePreset']:
        """
        Load a preset by name from the presets directory.
        
        Args:
            preset_name: Name of the preset (e.g., "1500m")
            
        Returns:
            RacePreset instance or None if not found
        """
        # Get the presets directory
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        presets_dir = os.path.join(current_dir, 'presets')
        
        # Try to load the preset
        filepath = os.path.join(presets_dir, f"{preset_name}.json")
        
        if not os.path.exists(filepath):
            return None
        
        return cls.from_file(filepath)
    
    @classmethod
    def list_available_presets(cls) -> List[str]:
        """
        List all available race presets.
        
        Returns:
            List of preset names (without .json extension)
        """
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        presets_dir = os.path.join(current_dir, 'presets')
        
        if not os.path.exists(presets_dir):
            return []
        
        presets = []
        for filename in os.listdir(presets_dir):
            if filename.endswith('.json'):
                presets.append(filename[:-5])  # Remove .json extension
        
        return sorted(presets)
