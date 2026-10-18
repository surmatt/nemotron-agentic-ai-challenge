"""Copy the scan pages and site screenshots that the video uses into video/public.

Run from the repository root after the site stage:

    uv run python video/scripts/prepare_assets.py

Scans come from data/raw/britannica (National Library of Scotland, CC0 1.0).
The script enlarges each page 3 times with Lanczos resampling. It does not change the content.
Screenshots come from artifacts/site through headless Google Chrome.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
PUBLIC = REPO / "video" / "public"
SCANS = {
    # name: (file in data/raw/britannica, expected image sha256)
    "scan-0523": ("page-0523-a583606e375a.jpg", "a583606e375ad92d79af8ad8b4fabc4fa22632e6ccbeea6e20f0fa47a27e2858"),
    "scan-1805": ("page-1805-226885408318.jpg", "2268854083181b93f7bf134647f2e3214aacdd4ce0279092f4743cf113d32abd"),
    "scan-2473": ("page-2473-b849fb7f25f2.jpg", "b849fb7f25f25b39685069d12c13b17d47169beeea958446bdff439c230a0f65"),
}
SITE_PAGES = {
    # name: (page in artifacts/site, window height)
    "site-index": ("index.html", 1000),
    "site-scan-1805": ("scans/1805.html", 2600),
    "site-entry-E0245": ("entries/E0245.html", 2200),
}
# The agent page is long; Chrome renders a blank frame at its anchors. Cut one run out of it instead.
AGENT_RUN = ("site-agent-q07", "2026-10-18T131943Z-q07-william", 1400)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def prepare_scans() -> dict[str, dict]:
    out = {}
    for name, (filename, expected) in SCANS.items():
        source = REPO / "data" / "raw" / "britannica" / filename
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != expected:
            raise ValueError(f"{filename}: sha256 {digest} does not match {expected}")
        image = Image.open(source).convert("RGB")
        large = image.resize((image.width * 3, image.height * 3), Image.Resampling.LANCZOS)
        target = PUBLIC / "scans" / f"{name}.jpg"
        target.parent.mkdir(parents=True, exist_ok=True)
        large.save(target, quality=92)
        out[name] = {"source": filename, "source_sha256": digest, "width": large.width, "height": large.height}
    return out


def screenshot(name: str, url: str, height: int) -> int:
    target = PUBLIC / "site" / f"{name}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    # Chrome can exit with a non-zero code after it writes the screenshot. Check the file instead.
    result = subprocess.run([CHROME, "--headless=new", "--hide-scrollbars", "--force-device-scale-factor=1",
                             "--virtual-time-budget=10000", f"--window-size=1600,{height}",
                             f"--screenshot={target}", url],
                            capture_output=True, text=True, timeout=60)
    if not target.exists():
        raise RuntimeError(f"{name}: no screenshot (exit {result.returncode}): {result.stderr[-500:]}")
    return result.returncode


def agent_run_page(anchor: str, folder: Path) -> Path:
    site = REPO / "artifacts" / "site"
    page = (site / "agent.html").read_text()
    match = re.search(rf'<h2 id="{re.escape(anchor)}">.*?(?=<h2 id=|</body>)', page, re.S)
    if not match:
        raise ValueError(f"agent.html has no run {anchor}")
    css = (site / "style.css").as_uri()
    path = folder / "agent-run.html"
    path.write_text(f'<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="{css}">'
                    f"<body>{match.group(0)}</body>")
    return path


def prepare_screenshots() -> dict[str, dict]:
    out = {}
    for name, (page, height) in SITE_PAGES.items():
        code = screenshot(name, (REPO / "artifacts" / "site" / page).as_uri(), height)
        out[name] = {"page": page, "width": 1600, "height": height, "chrome_exit_code": code}
    name, anchor, height = AGENT_RUN
    with tempfile.TemporaryDirectory() as folder:
        code = screenshot(name, agent_run_page(anchor, Path(folder)).as_uri(), height)
    out[name] = {"page": f"agent.html#{anchor} (section only)", "width": 1600, "height": height,
                 "chrome_exit_code": code}
    return out


def main() -> None:
    manifest = {"scans": prepare_scans(), "screenshots": prepare_screenshots()}
    (PUBLIC / "assets.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
