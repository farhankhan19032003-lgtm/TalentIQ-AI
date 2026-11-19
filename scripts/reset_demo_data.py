"""Wipe the database and the uploaded files, then load ONLY the synthetic sample data (no real resumes can survive this).

    python scripts/reset_demo_data.py                 # Docker Compose stack (default): removes the DB volume and uploads, restarts, loads the 50-resume pack
    python scripts/reset_demo_data.py --local         # local run: deletes backend/talentiq.db and backend/storage/uploads/* (stop the backend first), then you start it and run load_samples.py
    python scripts/reset_demo_data.py --set demo      # load the curated 15-resume demo set instead of the pack
    python scripts/reset_demo_data.py --yes           # do not ask for confirmation

Standard library only. Docker mode runs `docker compose down -v`, which deletes EVERY row and uploaded file of this compose project.
"""
import argparse
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def wait_for(base: str, seconds: int = 240) -> None:
    """Block until the API answers /api/health (the first start also builds the image, so allow several minutes)."""
    end = time.time() + seconds
    while time.time() < end:
        try:
            with urllib.request.urlopen(base + "/api/health", timeout=3):
                return
        except Exception:
            time.sleep(3)
    sys.exit(f"the app did not become ready at {base} within {seconds}s")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--local", action="store_true", help="reset the local SQLite database and upload folder instead of the Docker stack")
    ap.add_argument("--set", choices=["pack50", "demo"], default="pack50", help="which synthetic set to load afterwards (default: pack50)")
    ap.add_argument("--base", default="http://localhost:8080")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    a = ap.parse_args()
    where = "the local database file and uploads" if a.local else "the Docker database volume and uploads"
    if not a.yes and input(f"This DELETES ALL data in {where}. Type 'reset' to continue: ").strip() != "reset":
        sys.exit("aborted, nothing deleted")
    if a.local:
        for f in (ROOT / "backend").glob("talentiq.db*"):
            f.unlink()
            print("deleted", f.relative_to(ROOT))
        up = ROOT / "backend" / "storage" / "uploads"
        for f in up.glob("*"):
            if f.name != ".gitkeep":
                shutil.rmtree(f) if f.is_dir() else f.unlink()
        print("local data wiped. Start the backend, then run: python scripts/load_samples.py --base http://localhost:8000 --" + ("pack50" if a.set == "pack50" else "demo") + " --run")
        return
    run(["docker", "compose", "down", "-v"])
    run(["docker", "compose", "up", "-d", "--build"])
    wait_for(a.base)
    run([sys.executable, "scripts/load_samples.py", "--base", a.base, "--" + ("pack50" if a.set == "pack50" else "demo"), "--run"])


if __name__ == "__main__":
    main()
