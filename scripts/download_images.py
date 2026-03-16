"""
Download representative images for each seeded case from the Radiopaedia CDN
and store them under static/images/.

Run once from the project root:
    python scripts/download_images.py

The script is idempotent — it skips files that already exist.
"""

import os
import urllib.request
from pathlib import Path

# CDN image URL → local filename
IMAGES = [
    (
        "https://prod-images-static.radiopaedia.org/images/31127369/7a2d8584ede11f0f8a8ce28f60cb09_gallery.jpeg",
        "leiomyosarcoma.jpeg",
    ),
    (
        "https://prod-images-static.radiopaedia.org/images/74247943/dr-gallery.jpg",
        "mca_infarct.jpg",
    ),
    (
        "https://prod-images-static.radiopaedia.org/images/74189328/158f4a1963cfcbc8b4a98d9bd4938f03e5670534b83118abb7d7c3987b6e8cd9_gallery.jpeg",
        "lung_adenocarcinoma.jpeg",
    ),
    (
        "https://prod-images-static.radiopaedia.org/images/73769637/dr-gallery.jpg",
        "trigeminal_neuralgia.jpg",
    ),
    (
        "https://prod-images-static.radiopaedia.org/images/74182875/5e8c4e15d13cab8ea8ff02f7349da84696f2b6e0a9288039e6f51cf084f5643e_gallery.jpeg",
        "croup.jpeg",
    ),
    (
        "https://prod-images-static.radiopaedia.org/images/73968924/ef314b4b32c153d55cc4e265130decdb8bb4ab86532dc9a152e0167cbbf014c1_gallery.jpeg",
        "abdominal_compartment.jpeg",
    ),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://radiopaedia.org/",
}

dest_dir = Path(__file__).parent.parent / "static" / "images"
dest_dir.mkdir(parents=True, exist_ok=True)


def download(url: str, filename: str) -> None:
    dest = dest_dir / filename
    if dest.exists():
        print(f"  skip   {filename} (already exists)")
        return
    print(f"  fetch  {filename} …", end="", flush=True)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        dest.write_bytes(resp.read())
    print(f" {dest.stat().st_size // 1024} KB")


if __name__ == "__main__":
    print(f"Downloading {len(IMAGES)} images to {dest_dir}\n")
    errors = []
    for url, filename in IMAGES:
        try:
            download(url, filename)
        except Exception as exc:
            print(f" ERROR: {exc}")
            errors.append(filename)

    print()
    if errors:
        print(f"Failed: {errors}")
        print("Re-run the script, or download these manually.")
    else:
        print("All images ready.")
