"""
Parse PDF race data into competition JSON format.

Converts lap-by-lap skating data from PDF documents into the JSON format
used by the competition tracking system.
"""
import datetime
import json
import os
import re
from typing import Any

# Optional: Camelot for lattice-based table extraction
try:
    import camelot
    HAS_CAMELOT = True
except Exception:
    HAS_CAMELOT = False

# Fallback: pdfplumber
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except Exception:
    HAS_PDFPLUMBER = False

def parse_time_to_seconds(s: str) -> float | None:
    """
    Parse a time string to seconds.
    Supports formats like:
    - "1:06.28", "1:09.195", "0:23.2"
    - "66.28", "23.2"
    Returns None for invalid tokens (e.g., "DQ", "", None).
    """
    if s is None:
        return None
    s = str(s).strip()
    if not s or s.upper() in {"DQ", "DNS", "DNF"}:
        return None
    # Normalize decimal separator
    s = s.replace(",", ".")
    # Try mm:ss(.xxx)
    m = re.match(r"^(\d+):(\d+(?:\.\d+)?)$", s)
    if m:
        minutes = int(m.group(1))
        seconds = float(m.group(2))
        return minutes * 60 + seconds
    # Try pure seconds
    try:
        return float(s)
    except ValueError:
        return None

def parse_date_from_header(text: str) -> str | None:
    """
    Extract date like "THU 19 FEB 2026" from PDF header text and return ISO datetime string.
    If time-of-day isn't present, default to "00:00:00" local.
    """
    if not text:
        return None
    # Match e.g. "THU 19 FEB 2026"
    m = re.search(r"\b(?:MON|TUE|WED|THU|FRI|SAT|SUN)\s+(\d{1,2})\s+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(20\d{2})\b", text, re.IGNORECASE)
    if m:
        day = int(m.group(1))
        mon_str = m.group(2).upper()
        year = int(m.group(3))
        mon_map = {"JAN":1,"FEB":2,"MAR":3,"APR":4,"MAY":5,"JUN":6,"JUL":7,"AUG":8,"SEP":9,"OCT":10,"NOV":11,"DEC":12}
        month = mon_map.get(mon_str, None)
        if month:
            dt = datetime.datetime(year, month, day, 0, 0, 0)
            return dt.isoformat()
    return None

def clean_header_names(cols: list[str]) -> list[str]:
    """
    Normalize column names for easier matching.
    """
    norm = []
    for c in cols:
        c = (c or "").strip()
        c = re.sub(r"\s+", " ", c)
        norm.append(c)
    return norm

def is_lap_col(colname: str) -> bool:
    """
    Identify lap-time columns by name heuristics.
    Looks for 'LapTime', 'Lap Time', or split blocks that contain lap times.
    """
    if not colname:
        return False
    cn = colname.lower()
    return ("lap time" in cn) or ("laptime" in cn) or (("split" in cn) and ("lap" in cn))

def is_split_col(colname: str) -> bool:
    if not colname:
        return False
    cn = colname.lower()
    return "split" in cn and "time" in cn

def find_name_col(cols: list[str]) -> int | None:
    for i, c in enumerate(cols):
        lc = c.lower()
        if "name" in lc:
            return i
    return None

def find_noc_col(cols: list[str]) -> int | None:
    for i, c in enumerate(cols):
        lc = c.lower()
        if "noc" in lc or "noccode" in lc:
            return i
    return None

def find_lane_col(cols: list[str]) -> int | None:
    for i, c in enumerate(cols):
        lc = c.lower()
        if "lane" in lc:
            return i
    return None

def find_final_time_col(cols: list[str]) -> int | None:
    """
    Typically the final time column is simply "Time".
    """
    for i, c in enumerate(cols):
        lc = c.lower()
        if lc == "time" or "final time" in lc:
            return i
    return None

def find_rank_col(cols: list[str]) -> int | None:
    for i, c in enumerate(cols):
        lc = c.lower()
        if "rank" in lc or lc == "position" or lc == "pos":
            return i
    return None

def camelot_extract(pdf_path: str) -> list[dict[str, Any]]:
    tables = camelot.read_pdf(pdf_path, flavor="lattice", pages="all")
    rows = []
    for t in tables:
        df = t.df
        # First row as header; sometimes headers repeat, we try to collapse
        headers = clean_header_names(list(df.iloc[0]))
        # Identify relevant columns
        name_idx = find_name_col(headers)
        noc_idx = find_noc_col(headers)
        lane_idx = find_lane_col(headers)
        time_idx = find_final_time_col(headers)
        rank_idx = find_rank_col(headers)

        # Collect lap columns in reading order
        lap_col_indices = []
        split_col_indices = []
        for i, h in enumerate(headers):
            if is_lap_col(h):
                lap_col_indices.append(i)
            elif is_split_col(h):
                split_col_indices.append(i)

        # Process data rows
        for r in range(1, len(df)):
            row = list(df.iloc[r])
            # Skip blank rows
            if name_idx is not None:
                name_val = row[name_idx].strip()
                if not name_val:
                    continue
            else:
                # No name column; skip
                continue

            item = {
                "name": name_val,
                "noc": row[noc_idx].strip() if noc_idx is not None else None,
                "lane": row[lane_idx].strip() if lane_idx is not None else None,
                "final_time_str": row[time_idx].strip() if time_idx is not None else None,
                "rank_str": row[rank_idx].strip() if rank_idx is not None else None,
                "lap_values": [],
                "split_values": []
            }

            # Extract lap times
            for li in lap_col_indices:
                val = row[li].strip()
                # Many C77A tables show "Split Time (Rank) | LapTime" in the cell; take last number
                # Try to find the last numeric in the string
                nums = re.findall(r"\d+:\d+\.\d+|\d+\.\d+|\d+", val.replace(",", "."))
                if nums:
                    # choose last as lap time candidate
                    lap_s = nums[-1]
                    item["lap_values"].append(parse_time_to_seconds(lap_s))
                else:
                    item["lap_values"].append(parse_time_to_seconds(val))

            # Extract splits if needed
            for si in split_col_indices:
                val = row[si].strip()
                nums = re.findall(r"\d+:\d+\.\d+|\d+\.\d+|\d+", val.replace(",", "."))
                if nums:
                    # choose first as cumulative split candidate
                    split_s = nums[0]
                    item["split_values"].append(parse_time_to_seconds(split_s))
                else:
                    item["split_values"].append(parse_time_to_seconds(val))

            rows.append(item)
    return rows

def pdfplumber_extract(pdf_path: str) -> dict[str, Any]:
    rows = []
    header_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Accumulate header text to parse date
            header_text += "\n" + (page.extract_text() or "")
            # Find tables
            for table in page.extract_tables():
                if not table:
                    continue
                headers = clean_header_names(table[0])
                name_idx = find_name_col(headers)
                noc_idx = find_noc_col(headers)
                lane_idx = find_lane_col(headers)
                time_idx = find_final_time_col(headers)
                rank_idx = find_rank_col(headers)
                lap_col_indices = []
                split_col_indices = []
                for i, h in enumerate(headers):
                    if is_lap_col(h):
                        lap_col_indices.append(i)
                    elif is_split_col(h):
                        split_col_indices.append(i)
                # If no obvious lap columns, attempt heuristic: columns with "(Lap" or ending with "Lap"
                if not lap_col_indices:
                    for i, h in enumerate(headers):
                        if re.search(r"\bLap\b|\(Lap", h, re.IGNORECASE):
                            lap_col_indices.append(i)

                for r in range(1, len(table)):
                    row = table[r]
                    # guard against short rows
                    if name_idx is None or name_idx >= len(row):
                        continue
                    name_val = (row[name_idx] or "").strip()
                    if not name_val:
                        continue
                    item = {
                        "name": name_val,
                        "noc": (row[noc_idx] or "").strip() if (noc_idx is not None and noc_idx < len(row)) else None,
                        "lane": (row[lane_idx] or "").strip() if (lane_idx is not None and lane_idx < len(row)) else None,
                        "final_time_str": (row[time_idx] or "").strip() if (time_idx is not None and time_idx < len(row)) else None,
                        "rank_str": (row[rank_idx] or "").strip() if (rank_idx is not None and rank_idx < len(row)) else None,
                        "lap_values": [],
                        "split_values": []
                    }
                    # Lap values
                    for li in lap_col_indices:
                        if li >= len(row):
                            continue
                        val = (row[li] or "").strip()
                        nums = re.findall(r"\d+:\d+\.\d+|\d+\.\d+|\d+", val.replace(",", "."))
                        if nums:
                            lap_s = nums[-1]
                            item["lap_values"].append(parse_time_to_seconds(lap_s))
                        else:
                            item["lap_values"].append(parse_time_to_seconds(val))
                    # Split values
                    for si in split_col_indices:
                        if si >= len(row):
                            continue
                        val = (row[si] or "").strip()
                        nums = re.findall(r"\d+:\d+\.\d+|\d+\.\d+|\d+", val.replace(",", "."))
                        if nums:
                            split_s = nums[0]
                            item["split_values"].append(parse_time_to_seconds(split_s))
                        else:
                            item["split_values"].append(parse_time_to_seconds(val))

                    rows.append(item)
    return {"rows": rows, "header_text": header_text}

def build_results(rows: list[dict[str, Any]], event_name: str, date_iso: str | None) -> dict[str, Any]:
    """
    Convert extracted rows to the requested JSON structure.
    - skater_name from item["name"]
    - finish_time from final_time_str -> seconds
    - lap_times: prefer item["lap_values"] (take first 4). If missing, derive from split_values (differences).
    - position: prefer rank_str if present and numeric; else compute by sorting finish_time.
    - race_distance: fixed "1500m"
    - date: date_iso (same for all entries if only date is known)
    """
    # First pass: parse finish_time and store
    results = []
    for item in rows:
        finish_time = parse_time_to_seconds(item.get("final_time_str"))
        rank = None
        rank_str = (item.get("rank_str") or "").strip()
        if rank_str:
            try:
                rank = int(re.findall(r"\d+", rank_str)[0])
            except Exception:
                rank = None

        # Lap selection:
        lap_values = [lv for lv in item.get("lap_values", []) if lv is not None]
        if len(lap_values) >= 4:
            lap_times = lap_values[:4]
        elif item.get("split_values"):
            splits = [sv for sv in item["split_values"] if sv is not None]
            # Compute differences to get laps; Expect 4 segments for 1500m: 300m opening, then three 400m laps
            lap_times = []
            if splits:
                # If splits has cumulative at 300, 700, 1100, 1500 -> four laps: split[0], diff[1]-[0], diff[2]-[1], diff[3]-[2]
                # Otherwise, do best effort on available
                if len(splits) >= 1:
                    lap_times.append(splits[0])
                for i in range(1, min(4, len(splits))):
                    lap_times.append(max(0.0, splits[i] - splits[i-1]))
                # Pad if fewer than 4
                while len(lap_times) < 4 and finish_time is not None:
                    # Use average of remaining time
                    remaining = finish_time - sum(lap_times) if finish_time is not None else 0.0
                    lap_times.append(max(0.0, remaining))
            else:
                lap_times = []
        else:
            lap_times = []

        results.append({
            "skater_name": item.get("name"),
            "finish_time": finish_time,
            "lap_times": lap_times,
            "race_distance": "1500m",
            "date": date_iso,
            "position": rank
        })

    # If positions are missing, compute them by sorting by finish_time (ascending), ignoring None and DQs
    if any(r["position"] is None for r in results):
        valid = [(i, r["finish_time"]) for i, r in enumerate(results) if r["finish_time"] is not None]
        # Sort by finish_time
        valid_sorted = sorted(valid, key=lambda x: x[1])
        # Assign positions starting at 1
        for pos, (idx, _) in enumerate(valid_sorted, start=1):
            results[idx]["position"] = pos

    return {"name": event_name, "results": results}

def main(pdf_path: str, out_path: str):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    extracted_rows = []
    header_text = ""

    if HAS_CAMELOT:
        try:
            extracted_rows = camelot_extract(pdf_path)
        except Exception as e:
            print(f"Camelot parsing failed: {e}. Falling back to pdfplumber.")
    if not extracted_rows and HAS_PDFPLUMBER:
        pl = pdfplumber_extract(pdf_path)
        extracted_rows = pl["rows"]
        header_text = pl["header_text"]
    elif not HAS_PDFPLUMBER and not extracted_rows:
        raise RuntimeError("No table extraction library available. Install camelot-py or pdfplumber.")

    # Event name and date
    # Event name fallback
    event_name = "Men’s 1500m Distance Analysis"
    # Try to get date from header text; else None
    date_iso = parse_date_from_header(header_text) if header_text else None
    # If still None, default to None (consumer can fill later)
    result_json = build_results(extracted_rows, event_name, date_iso)

    # Write JSON
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result_json, f, ensure_ascii=False, indent=2)

    print(f"Wrote {out_path} with {len(result_json['results'])} results.")

if __name__ == "__main__":
    import argparse

    # Resolve project-relative data directories (script lives in skate/scripts)
    SCRIPTDIR = os.path.dirname(os.path.abspath(__file__))
    BASEDIR = os.path.dirname(SCRIPTDIR)  # skate/
    DEFAULT_DOWNLOADS = os.path.join(BASEDIR, "data", "downloads")
    DEFAULT_COMPETITIONS = os.path.join(BASEDIR, "data", "competitions")

    parser = argparse.ArgumentParser(
        description="Parse a lap-by-lap PDF into competition JSON.\nIf no PDF is given, the first PDF in data/downloads will be used."
    )
    parser.add_argument("pdf", nargs="?", help="Path to PDF file or filename located in data/downloads")
    parser.add_argument("-o", "--out", help="Output JSON path (default: data/competitions/<pdfname>.json)")
    args = parser.parse_args()

    # Determine pdf_path
    if args.pdf:
        pdf_path = args.pdf
        if not os.path.isabs(pdf_path) and not os.path.exists(pdf_path):
            # assume file lives in data/downloads
            pdf_path = os.path.join(DEFAULT_DOWNLOADS, args.pdf)
    else:
        # choose first PDF in downloads dir
        if not os.path.isdir(DEFAULT_DOWNLOADS):
            raise FileNotFoundError(f"Downloads directory not found: {DEFAULT_DOWNLOADS}")
        pdfs = [p for p in os.listdir(DEFAULT_DOWNLOADS) if p.lower().endswith('.pdf')]
        if not pdfs:
            raise FileNotFoundError(f"No PDF files found in {DEFAULT_DOWNLOADS}. Provide a PDF path as an argument.")
        pdf_path = os.path.join(DEFAULT_DOWNLOADS, pdfs[0])

    # Determine out_path
    if args.out:
        out_path = args.out
    else:
        base = os.path.splitext(os.path.basename(pdf_path))[0]
        # ensure competitions dir exists
        os.makedirs(DEFAULT_COMPETITIONS, exist_ok=True)
        out_path = os.path.join(DEFAULT_COMPETITIONS, f"{base}.json")

    main(pdf_path, out_path)