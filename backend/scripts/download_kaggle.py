"""Download curated Kaggle 5G datasets into backend/data/kaggle/."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "data" / "kaggle" / "datasets.json"
OUT_DIR = ROOT / "data" / "kaggle"


def load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def list_datasets() -> None:
    cat = load_catalog()
    print("Kaggle datasets:\n")
    for i, ds in enumerate(cat["datasets"], 1):
        print(f"  {i}. {ds['name']}")
        print(f"     slug: {ds['slug']}")
        print(f"     use:  {ds['use_case']}")
        print(f"     url:  {ds['url']}\n")
    print("External (not Kaggle):\n")
    for ext in cat.get("external_alternatives", []):
        print(f"  - {ext['name']}: {ext['url']}")


def download(slug: str | None = None, all_datasets: bool = False) -> list[Path]:
    cat = load_catalog()
    slugs = [d["slug"] for d in cat["datasets"]] if all_datasets else [slug]
    if not slugs or slugs == [None]:
        print("Usage: python download_kaggle.py list")
        print("       python download_kaggle.py download <slug>")
        print("       python download_kaggle.py download --all")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []

    for s in slugs:
        if not s:
            continue
        target = OUT_DIR / s.split("/")[-1]
        target.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {s} -> {target} ...")
        try:
            subprocess.run(
                ["kaggle", "datasets", "download", "-d", s, "-p", str(target), "--unzip"],
                check=True,
            )
            downloaded.append(target)
            print(f"  OK: {target}")
        except FileNotFoundError:
            print(
                "ERROR: Kaggle CLI not found. Run: pip install kaggle\n"
                "Then add API token from https://www.kaggle.com/settings -> Create New Token\n"
                "Save as ~/.kaggle/kaggle.json (Linux/Mac) or %USERPROFILE%\\.kaggle\\kaggle.json"
            )
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"  FAILED: {s} (accept dataset rules on Kaggle website first)")
            print(f"  {e}")

    return downloaded


def main() -> None:
    if len(sys.argv) < 2:
        list_datasets()
        return

    cmd = sys.argv[1].lower()
    if cmd == "list":
        list_datasets()
    elif cmd == "download":
        if len(sys.argv) > 2 and sys.argv[2] == "--all":
            download(all_datasets=True)
        elif len(sys.argv) > 2:
            download(slug=sys.argv[2])
        else:
            print("Provide slug or --all")
            sys.exit(1)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
