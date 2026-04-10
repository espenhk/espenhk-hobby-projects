from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from shutil import copy2

LOGGER = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Publish approved Gold output into foundry-exchange.",
    )
    parser.add_argument("--source", required=True, help="Source Gold JSON path")
    parser.add_argument("--destination", required=True, help="Destination publish path")
    args = parser.parse_args()

    source = Path(args.source)
    destination = Path(args.destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    copy2(source, destination)
    LOGGER.info("Published Gold output from %s to %s", source, destination)

    metadata = {
        "published_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "destination": str(destination),
        "approval_status": "approved",
    }
    metadata_path = destination.with_suffix(destination.suffix + ".metadata.json")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    LOGGER.info("Wrote publish metadata contract to %s", metadata_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
