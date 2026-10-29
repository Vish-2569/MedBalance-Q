"""Package evidence/ and docs/ into a timestamped zip for judges."""
from __future__ import annotations

import datetime
import pathlib
import zipfile
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIRS = ["evidence", "docs"]
OUT_DIR = ROOT / "evidence"


def main() -> None:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUT_DIR / f"medbalance_evidence_{ts}.zip"
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    count = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirname in DIRS:
            src = ROOT / dirname
            if not src.exists():
                print(f"  skip {dirname}/ (not found)")
                continue
            for p in sorted(src.rglob("*")):
                if p.is_file() and ".zip" not in p.suffixes:
                    arcname = p.relative_to(ROOT)
                    zf.write(p, arcname)
                    count += 1

        screenshots = ROOT / "screenshots"
        if screenshots.exists():
            for p in sorted(screenshots.rglob("*")):
                if p.is_file():
                    zf.write(p, p.relative_to(ROOT))
                    count += 1

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"Packaged {count} files -> {out_path.name} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
