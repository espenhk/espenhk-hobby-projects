"""
Unit tests for the Ice Skating Race Predictor.
"""
import unittest
from models.skater import Skater
from models.race import Race
from engine.predictor import PredictionEngine


class TestSkater(unittest.TestCase):
    """Test cases for Skater class."""
    
    def test_skater_creation(self):
        """Test creating a skater."""
        skater = Skater(name="John Doe")
        self.assertEqual(skater.name, "John Doe")
        self.assertEqual(len(skater.lap_times), 0)
        self.assertFalse(skater.finished)
    
    def test_add_lap_times(self):
        """Test adding lap times."""
        skater = Skater(name="Jane Smith")
        skater.add_lap_time(30.5)
        skater.add_lap_time(31.2)
        
        self.assertEqual(len(skater.lap_times), 2)
        self.assertEqual(skater.get_laps_completed(), 2)
    
    def test_average_lap_time(self):
        """Test average lap time calculation."""
        skater = Skater(name="Test")
        skater.add_lap_time(30.0)
        skater.add_lap_time(32.0)
        skater.add_lap_time(31.0)
        
        avg = skater.get_average_lap_time()
        self.assertEqual(avg, 31.0)
    
    def test_predict_finish_time(self):
        """Test finish time prediction."""
        skater = Skater(name="Test")
        skater.add_lap_time(30.0)
        skater.add_lap_time(30.0)
        
        # Predict for 5 laps total
        predicted = skater.predict_finish_time(5)
        # 2 laps done (60s), 3 laps remaining (90s) = 150s
        self.assertEqual(predicted, 150.0)


class TestRace(unittest.TestCase):
    """Test cases for Race class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.skater1 = Skater(name="Alice")
        self.skater2 = Skater(name="Bob")
        self.race = Race(total_laps=5, skaters=[self.skater1, self.skater2])
    
    def test_race_creation(self):
        """Test creating a race."""
        self.assertEqual(self.race.total_laps, 5)
        self.assertEqual(len(self.race.skaters), 2)
    
    def test_add_lap_time(self):
        """Test adding lap time through race."""
        result = self.race.add_lap_time("Alice", 30.5)
        self.assertTrue(result)
        self.assertEqual(self.skater1.get_laps_completed(), 1)
    
    def test_get_current_leader(self):
        """Test getting current leader."""
        self.race.add_lap_time("Alice", 30.0)
        self.race.add_lap_time("Bob", 31.0)
        
        leader = self.race.get_current_leader()
        self.assertEqual(leader.name, "Alice")
    
    def test_race_finished(self):
        """Test race finish detection."""
        # Complete all laps for both skaters
        for _ in range(5):
            self.race.add_lap_time("Alice", 30.0)
            self.race.add_lap_time("Bob", 31.0)
        
        self.assertTrue(self.race.is_race_finished())


class TestPredictionEngine(unittest.TestCase):
    """Test cases for PredictionEngine."""
    
    def test_parse_time_input(self):
        """Test time input parsing."""
        predictor = PredictionEngine()
        
        # Test MM:SS.mmm format
        time1 = predictor.parse_time_input("1:30.500")
        self.assertEqual(time1, 90.5)
        
        # Test SS.mmm format
        time2 = predictor.parse_time_input("45.250")
        self.assertEqual(time2, 45.25)
        
        # Test invalid format
        time3 = predictor.parse_time_input("invalid")
        self.assertIsNone(time3)
    
    def test_format_time(self):
        """Test time formatting."""
        predictor = PredictionEngine()
        
        # Test with minutes
        formatted1 = predictor.format_time(90.5)
        self.assertEqual(formatted1, "1:30.500")
        
        # Test without minutes
        formatted2 = predictor.format_time(45.25)
        self.assertEqual(formatted2, "45.250s")
    
    def test_calculate_gap(self):
        """Test gap calculation between skaters."""
        predictor = PredictionEngine()
        
        skater1 = Skater(name="Fast")
        skater1.add_lap_time(30.0)
        
        skater2 = Skater(name="Slow")
        skater2.add_lap_time(32.0)
        
        gap, description = predictor.calculate_gap(skater1, skater2)
        self.assertEqual(gap, 2.0)
        self.assertIn("Slow", description)
        self.assertIn("behind", description)


def run_tests():
    """Run all tests."""
    print("Running Ice Skating Race Predictor Tests...")
    print("=" * 70)
    
    unittest.main(argv=[''], exit=False, verbosity=2)


if __name__ == "__main__":
    run_tests()
