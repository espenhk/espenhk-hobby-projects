import json
import os
from datetime import datetime

# Resolve paths relative to the script location so the script works when
# executed from the workspace root or other working directories.
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
INPATH = os.path.join(BASE_DIR, 'data', 'competitions', 'parsed_competition.json')
OUTPATH = os.path.join(BASE_DIR, 'data', 'competitions', 'parsed_competition_fixed.json')

with open(INPATH) as f:
    data = json.load(f)

race_distance = data.get('race_distance')
date = data.get('date', datetime.now().isoformat())

fixed = {
    'name': data.get('name', 'Parsed Competition'),
    'results': []
}

for r in data.get('results', []):
    fixed_result = {
        'skater_name': r.get('skater_name') or r.get('name'),
        'finish_time': r.get('finish_time'),
        'lap_times': r.get('lap_times', []),
        'race_distance': r.get('race_distance') or race_distance,
        'date': r.get('date') or date,
        'position': r.get('position')
    }
    fixed['results'].append(fixed_result)

with open(OUTPATH, 'w') as f:
    json.dump(fixed, f, indent=2)

print(f"Wrote fixed competition file: {OUTPATH}")
