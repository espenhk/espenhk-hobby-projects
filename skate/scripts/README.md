parse_pdf.py
=============

Purpose
-------
Parse lap-by-lap PDF race result sheets into the competition JSON format used by the project.

Quick start
-----------
1. Install Python dependencies (recommended in a venv):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Place the PDF in `data/downloads/` (the script will pick the first PDF by default) or supply a path.

3. Run the script:

```bash
# Use first PDF found in data/downloads/
python3 parse_pdf.py

# Use a specific filename from data/downloads/
python3 parse_pdf.py "2026 Olympics mens 1500m skating lap by lap.pdf"

# Use an absolute path and custom output
python3 parse_pdf.py /home/me/Downloads/race.pdf -o data/competitions/mens_1500m.json
```

Notes
-----
- The script tries `camelot` first (lattice mode) and falls back to `pdfplumber`.
- `camelot` requires `ghostscript` and optional OpenCV; installing `camelot-py[cv]` may need extra system packages.
- If you only need the fallback, `pdfplumber` is lighter-weight.

Example output location
-----------------------
`data/competitions/<pdf_basename>.json`

If you want, I can:
- Add more heuristics for different table formats
- Add an automated test for an example PDF (if you provide one)
- Make the script stricter about field validation
