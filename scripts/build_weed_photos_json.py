#!/usr/bin/env python3
"""Build weed_photos.json from downloaded weed photos."""
import json
import os
from pathlib import Path

PHOTO_DIR = Path("static/weed-photos")

# Map slug to display name
SLUG_TO_NAME = {
    "Annual-Bluegrass": "Annual Bluegrass (Poa annua)",
    "Annual-Sedge": "Annual Sedge",
    "Barnyardgrass": "Barnyardgrass",
    "Bentgrass": "Bentgrass",
    "Black-Medic": "Black Medic",
    "Buckhorn-Plantain": "Buckhorn Plantain",
    "Canada-Thistle": "Canada Thistle",
    "Carolina-Geranium": "Carolina Geranium",
    "Carpetweed": "Carpetweed",
    "Common-Bermudagrass": "Common Bermudagrass",
    "Common-Chickweed": "Common Chickweed",
    "Common-Purslane": "Common Purslane",
    "Corn-Speedwell": "Corn Speedwell",
    "Crabgrass,-Smooth-and-Large": "Crabgrass (Smooth and Large)",
    "Crowfootgrass": "Crowfootgrass",
    "Dallisgrass": "Dallisgrass",
    "Dandelion": "Dandelion",
    "Dichondra": "Dichondra",
    "Dollarweed---Pennywort": "Dollarweed / Pennywort",
    "Doveweed": "Doveweed",
    "Field-Sandbur": "Field Sandbur",
    "Florida-Betony": "Florida Betony",
    "Florida-pusley": "Florida Pusley",
    "Foxtails": "Foxtails",
    "Globe-Sedge": "Globe Sedge",
    "Goosegrass": "Goosegrass",
    "Green-Kyllinga": "Green Kyllinga",
    "Ground-Ivy": "Ground Ivy (Creeping Charlie)",
    "Groundsel": "Groundsel",
    "Henbit": "Henbit",
    "Knotweed": "Knotweed",
    "Lawn-Burweed": "Lawn Burweed",
    "Morningglory": "Morningglory",
    "Mouse-ear-Chickweed": "Mouse-ear Chickweed",
    "Nimblewill": "Nimblewill",
    "Parsley-Piert": "Parsley-Piert",
    "Persian-Speedwell": "Persian Speedwell",
    "Purple-Nutsedge": "Purple Nutsedge",
    "Quackgrass": "Quackgrass",
    "Roughstalk-Bluegrass": "Roughstalk Bluegrass (Poa trivialis)",
    "Ryegrass,-Italian---Annual": "Italian / Annual Ryegrass",
    "Ryegrass,-Perennial": "Perennial Ryegrass",
    "Shepherd--s-Purse": "Shepherd's Purse",
    "Southern-Sandbur": "Southern Sandbur",
    "Spotted-Spurge---Prostrate-Spurge": "Spotted Spurge / Prostrate Spurge",
    "Thin-Paspalum---Bull-Paspalum": "Thin Paspalum / Bull Paspalum",
    "Torpedograss": "Torpedograss",
    "Tropical-Carpetgrass": "Tropical Carpetgrass",
    "Tropical-Signalgrass": "Tropical Signalgrass",
    "Virginia-buttonweed": "Virginia Buttonweed",
    "White-Clover": "White Clover",
    "Wild-Garlic": "Wild Garlic",
    "Wild-Violet": "Wild Violet",
    "Windmillgrass": "Windmillgrass",
    "Yellow-Nutsedge": "Yellow Nutsedge",
    "Yellow-Woodsorrel---Oxalis": "Yellow Woodsorrel / Oxalis",
}

# Get all downloaded files
downloaded = set(f.name for f in PHOTO_DIR.iterdir() if f.is_file())

# Build mapping: slug -> list of {filename, caption}
with open("weed_photo_urls.json") as f:
    url_map = json.load(f)

weed_photos = {}
for slug, urls in url_map.items():
    name = SLUG_TO_NAME.get(slug, slug.replace("-", " "))
    # Normalize slug to key format (lowercase, underscores)
    key = slug.lower().replace("-", "_").replace(",", "").replace("__", "_")
    # Clean up double underscores
    while "__" in key:
        key = key.replace("__", "_")

    photos = []
    for i, url in enumerate(urls):
        filename = url.split("/")[-1].lower()
        if filename in downloaded:
            caption = f"{name} — reference photo {i+1}"
            photos.append({"filename": filename, "caption": caption})

    if photos:
        weed_photos[key] = {"photos": photos}

with open("knowledge/weed_photos.json", "w") as f:
    json.dump(weed_photos, f, indent=2)

print(f"Created weed_photos.json with {len(weed_photos)} weeds, {sum(len(v['photos']) for v in weed_photos.values())} total photos")
print(f"\nWeeds with no photos (all 410 Gone):")
for slug in url_map:
    key = slug.lower().replace("-", "_").replace(",", "").replace("__", "_")
    while "__" in key:
        key = key.replace("__", "_")
    if key not in weed_photos:
        print(f"  {SLUG_TO_NAME.get(slug, slug)}")
