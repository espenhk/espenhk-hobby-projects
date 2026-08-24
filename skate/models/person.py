"""
Person profile storage for tracking skater history over time.
Each person is stored as a JSON file under `data/people/`.
"""
import json
import os
from dataclasses import asdict, dataclass, field
from typing import Optional

# Default people directory located under the skate package: skate/data/people
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DEFAULT_PEOPLE_DIR = os.path.join(BASE_DIR, 'data', 'people')


@dataclass
class Person:
    name: str
    slug: str
    history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, directory: str = None) -> str:
        if directory is None:
            directory = DEFAULT_PEOPLE_DIR
        os.makedirs(directory, exist_ok=True)
        filepath = os.path.join(directory, f"{self.slug}.json")
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        return filepath

    @classmethod
    def load(cls, filepath: str) -> Optional['Person']:
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath) as f:
                data = json.load(f)
            return cls(name=data['name'], slug=data['slug'], history=data.get('history', []))
        except Exception:
            return None

    @classmethod
    def list_people(cls, directory: str = None) -> list[dict]:
        if directory is None:
            directory = DEFAULT_PEOPLE_DIR
        if not os.path.exists(directory):
            return []
        people = []
        for filename in os.listdir(directory):
            if filename.endswith('.json'):
                filepath = os.path.join(directory, filename)
                p = cls.load(filepath)
                if p:
                    people.append({'name': p.name, 'slug': p.slug, 'filepath': filepath, 'filename': filename})
        return sorted(people, key=lambda x: x['name'])

    @classmethod
    def create(cls, name: str, slug: str | None = None) -> 'Person':
        if not slug:
            slug = name.lower().replace(' ', '_')
        return cls(name=name, slug=slug)

    def add_history_entry(self, entry: dict, directory: str = None) -> None:
        """Add a history entry to this person and save the file."""
        self.history.append(entry)
        self.save(directory)

    @classmethod
    def load_by_name(cls, name: str, directory: str = None) -> Optional['Person']:
        """Try to load a person by name (case-insensitive) or slug."""
        if directory is None:
            directory = DEFAULT_PEOPLE_DIR
        if not os.path.exists(directory):
            return None
        target_slug = name.lower().replace(' ', '_')
        for p in cls.list_people(directory):
            if p['slug'] == target_slug or p['name'].lower() == name.lower():
                return cls.load(p['filepath'])
        return None
