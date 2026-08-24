#!/usr/bin/env python3
"""Create person profiles and populate their history from a competition JSON file.
Usage: python3 populate_people_from_competition.py data/competitions/parsed_competition_fixed.json
"""
import argparse
import json
import os
import sys

# Ensure package imports work when script is invoked directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.person import Person


def populate(filepath: str):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    with open(filepath) as f:
        data = json.load(f)

    results = data.get('results', [])
    created = 0

    for r in results:
        name = r.get('skater_name') or r.get('name')
        if not name:
            continue

        person = Person.load_by_name(name)
        entry = {
            'date': r.get('date') or data.get('date'),
            'distance': r.get('race_distance') or data.get('race_distance'),
            'finish_time': r.get('finish_time'),
            'lap_times': r.get('lap_times', []),
            'position': r.get('position')
        }

        if person:
            person.add_history_entry(entry)
        else:
            p = Person.create(name)
            p.add_history_entry(entry)
            created += 1

    print(f"Populated people from {filepath}. New profiles created: {created}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('competition_file')
    args = parser.parse_args()
    populate(args.competition_file)


if __name__ == '__main__':
    main()
