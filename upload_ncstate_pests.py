#!/usr/bin/env python3
"""
Scrape NC State TurfFiles insect/pest pages and upload to Pinecone.
Also downloads reference photos.
"""
import os
import re
import json
import logging
import time
from pathlib import Path
from dotenv import load_dotenv
import openai
from pinecone import Pinecone

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
MIN_CHUNK_SIZE = 200
BATCH_SIZE = 50
PHOTO_DIR = Path("static/pest-photos")
PHOTO_DIR.mkdir(parents=True, exist_ok=True)

# All pest pages from NC State TurfFiles
PEST_PAGES = {
    "annual_bluegrass_weevil": {
        "name": "Annual Bluegrass Weevil",
        "url": "https://www.turffiles.ncsu.edu/insects/annual-bluegrass-weevil-in-turf/"
    },
    "chinch_bug": {
        "name": "Chinch Bug",
        "url": "https://www.turffiles.ncsu.edu/insects/chinch-bug-in-turf/"
    },
    "crane_fly_larvae": {
        "name": "Crane Fly Larvae",
        "url": "https://www.turffiles.ncsu.edu/insects/crane-fly-larvae-in-turf/"
    },
    "cutworm": {
        "name": "Cutworm",
        "url": "https://www.turffiles.ncsu.edu/insects/cutworm-in-turf/"
    },
    "fall_armyworm": {
        "name": "Fall Armyworm",
        "url": "https://www.turffiles.ncsu.edu/insects/fall-armyworm-in-turf/"
    },
    "fire_ants": {
        "name": "Fire Ants",
        "url": "https://www.turffiles.ncsu.edu/insects/fire-ants-in-turf/"
    },
    "green_june_beetle": {
        "name": "Green June Beetle",
        "url": "https://www.turffiles.ncsu.edu/green-june-beetles/"
    },
    "ground_pearls": {
        "name": "Ground Pearls",
        "url": "https://www.turffiles.ncsu.edu/insects/ground-pearls-in-turf/"
    },
    "hunting_billbug": {
        "name": "Hunting Billbug",
        "url": "https://www.turffiles.ncsu.edu/insects/hunting-billbug-in-turf/"
    },
    "japanese_beetle": {
        "name": "Japanese Beetle",
        "url": "https://www.turffiles.ncsu.edu/insects/japanese-beetle-in-turf/"
    },
    "mole_cricket": {
        "name": "Mole Cricket",
        "url": "https://www.turffiles.ncsu.edu/insects/mole-cricket-in-turf/"
    },
    "nematodes": {
        "name": "Nematodes",
        "url": "https://www.turffiles.ncsu.edu/insects/nematodes-in-turf/"
    },
    "sod_webworm": {
        "name": "Sod Webworm",
        "url": "https://www.turffiles.ncsu.edu/insects/sod-webworm-in-turf/"
    },
    "white_grubs": {
        "name": "White Grubs",
        "url": "https://www.turffiles.ncsu.edu/insects/white-grubs-in-turf/"
    },
    "bermudagrass_mites": {
        "name": "Bermudagrass Mites",
        "url": "https://www.turffiles.ncsu.edu/bermudagrass-mites/"
    },
    "zoysiagrass_mites": {
        "name": "Zoysiagrass Mites",
        "url": "https://www.turffiles.ncsu.edu/zoysiagrass-mites/"
    },
    "twolined_spittlebug": {
        "name": "Twolined Spittlebug",
        "url": "https://www.turffiles.ncsu.edu/insects/twolined-spittlebug-in-turf/"
    },
    "rhodesgrass_mealybug": {
        "name": "Rhodesgrass Mealybug",
        "url": "https://www.turffiles.ncsu.edu/insects/rhodesgrass-mealybug-in-turf/"
    },
    "sugarcane_beetle": {
        "name": "Sugarcane Beetle",
        "url": "https://www.turffiles.ncsu.edu/insects/sugarcane-beetles-in-turf/"
    },
    "earthworm": {
        "name": "Earthworm",
        "url": "https://www.turffiles.ncsu.edu/insects/earthworm-in-turf/"
    },
    "moles": {
        "name": "Moles",
        "url": "https://www.turffiles.ncsu.edu/insects/moles-in-turf/"
    },
    "voles": {
        "name": "Voles",
        "url": "https://www.turffiles.ncsu.edu/insects/voles-in-turf/"
    },
    "clover_mite": {
        "name": "Clover Mite",
        "url": "https://www.turffiles.ncsu.edu/insects/clover-mite-in-turf/"
    },
    "millipedes": {
        "name": "Millipedes",
        "url": "https://www.turffiles.ncsu.edu/insects/millipedes-in-turf/"
    },
    "springtails": {
        "name": "Springtails",
        "url": "https://www.turffiles.ncsu.edu/insects/springtails-in-turf/"
    },
    "wireworms": {
        "name": "Wireworms",
        "url": "https://www.turffiles.ncsu.edu/wireworms/"
    },
    "crayfish": {
        "name": "Crayfish",
        "url": "https://www.turffiles.ncsu.edu/insects/crayfish-in-turf/"
    },
    "nuisance_ants": {
        "name": "Nuisance Ants",
        "url": "https://www.turffiles.ncsu.edu/insects/formica-ants-in-turf/"
    },
    "ground_nesting_bees": {
        "name": "Ground-Nesting Bees",
        "url": "https://www.turffiles.ncsu.edu/insects/bees-in-turf/"
    },
    "cicada_killer_wasp": {
        "name": "Cicada Killer Wasp",
        "url": "https://www.turffiles.ncsu.edu/insects/cicada-killer-wasps-in-turf/"
    },
    "scoliid_wasp": {
        "name": "Scoliid Wasp",
        "url": "https://www.turffiles.ncsu.edu/insects/scoliid-wasp-in-turf/"
    },
    "hornets": {
        "name": "Hornets",
        "url": "https://www.turffiles.ncsu.edu/insects/hornets-in-turf/"
    },
    "yellowjacket": {
        "name": "Yellowjacket",
        "url": "https://www.turffiles.ncsu.edu/insects/yellowjacket-in-turf/"
    },
}


def scrape_all_pests():
    """Use Playwright to scrape all pest pages and extract photos."""
    from playwright.sync_api import sync_playwright
    import urllib.request

    pests = {}
    all_photos = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for i, (key, pest) in enumerate(PEST_PAGES.items()):
            url = pest["url"]
            name = pest["name"]
            try:
                page.goto(url, wait_until="networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                # Extract text
                text = page.inner_text("body")
                if not text or len(text) < 50:
                    logger.warning(f"  [{i+1}/{len(PEST_PAGES)}] EMPTY: {name}")
                    continue

                # Clean up - remove nav/footer junk
                # Find the main content start
                for marker in ["Description", "Biology", "Identification", "Life Cycle", name]:
                    idx = text.find(marker)
                    if idx > 0 and idx < 500:
                        text = text[idx:]
                        break

                # Remove footer
                for footer in ["SHARE THIS", "NC State Extension", "Was the information", "Let us know", "N.C. Cooperative Extension"]:
                    idx = text.find(footer)
                    if idx > 0:
                        text = text[:idx]

                text = re.sub(r'\n{3,}', '\n\n', text).strip()

                if len(text) < 50:
                    logger.warning(f"  [{i+1}/{len(PEST_PAGES)}] TOO SHORT: {name}")
                    continue

                pests[key] = text[:5000]

                # Extract photo URLs
                photos = page.eval_on_selector_all(
                    "img[src*='content.ces.ncsu.edu']",
                    "els => els.map(e => e.src)"
                )
                if not photos:
                    photos = page.eval_on_selector_all(
                        "img[src*='media/images']",
                        "els => els.map(e => e.src)"
                    )
                # Filter to actual pest photos (not logos/banners)
                photos = [p for p in photos if 'content.ces.ncsu.edu/media/images' in p]
                if photos:
                    all_photos[key] = photos[:3]  # Max 3 photos per pest

                logger.info(f"  [{i+1}/{len(PEST_PAGES)}] OK: {name} ({len(text)} chars, {len(photos)} photos)")

            except Exception as e:
                logger.error(f"  [{i+1}/{len(PEST_PAGES)}] ERROR: {name} - {e}")

        browser.close()

    # Download photos
    logger.info(f"\n=== Downloading photos ===")
    photo_map = {}
    for key, urls in all_photos.items():
        name = PEST_PAGES[key]["name"]
        downloaded = []
        for j, url in enumerate(urls):
            # Create a clean filename
            ext = url.split('.')[-1].lower()
            if ext not in ('jpg', 'jpeg', 'png', 'gif'):
                ext = 'jpg'
            filename = f"{key.replace('_', '-')}-{j+1}.{ext}"
            dest = PHOTO_DIR / filename
            if dest.exists():
                downloaded.append(filename)
                continue
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = resp.read()
                dest.write_bytes(data)
                downloaded.append(filename)
                logger.info(f"  OK: {filename} ({len(data)//1024}KB)")
            except Exception as e:
                logger.warning(f"  FAIL: {filename} - {e}")

        if downloaded:
            photo_map[key] = {
                "photos": [
                    {"filename": fn, "caption": f"{name} — reference photo {j+1}"}
                    for j, fn in enumerate(downloaded)
                ]
            }

    # Save photo mapping
    with open("knowledge/pest_photos.json", "w") as f:
        json.dump(photo_map, f, indent=2)
    logger.info(f"Saved pest_photos.json: {len(photo_map)} pests with photos")

    return pests


def clean_text(text):
    """Remove product brand references."""
    brand_patterns = [
        r'(?i)syngenta\b', r'(?i)\bmerit\b', r'(?i)\bacelepryn\b',
        r'(?i)\bscimitar\b', r'(?i)\bmeridian\b', r'(?i)\btrilogy\b',
        r'(?i)\bdursban\b', r'(?i)\btalstar\b', r'(?i)\bbifenthrin\b',
        r'(?i)GreenTrust\s*365\b', r'(?i)Performance\s*Guarantee',
    ]
    for pat in brand_patterns:
        text = re.sub(pat, '', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()


def smart_chunk(text, max_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into overlapping chunks at sentence boundaries."""
    if len(text) <= max_size:
        return [text]
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 > max_size and len(current) >= MIN_CHUNK_SIZE:
            chunks.append(current.strip())
            words = current.split()
            overlap_text = ' '.join(words[-20:]) if len(words) > 20 else current
            current = overlap_text + " " + sentence
        else:
            current = (current + " " + sentence).strip()
    if current.strip() and len(current.strip()) >= MIN_CHUNK_SIZE:
        chunks.append(current.strip())
    elif current.strip() and chunks:
        chunks[-1] += " " + current.strip()
    return chunks


def embed_texts(client, texts):
    try:
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
        return [item.embedding for item in response.data]
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return None


def main():
    logger.info("=== Scraping NC State TurfFiles pest pages ===")
    pests = scrape_all_pests()
    logger.info(f"\nScraped {len(pests)} pests successfully")

    with open("pest_scraped_data.json", "w") as f:
        json.dump(pests, f, indent=2)

    if not pests:
        logger.error("No pests scraped!")
        return

    # Connect to Pinecone
    openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index("turf-research")

    # Build vectors
    all_vectors = []
    for key, text in pests.items():
        name = PEST_PAGES[key]["name"]
        doc_text = f"Turf Pest/Insect: {name}\n\n{clean_text(text)}"
        chunks = smart_chunk(doc_text)
        if not chunks:
            chunks = [doc_text]

        logger.info(f"  {name}: {len(chunks)} chunks ({len(doc_text)} chars)")

        base_id = f"ncstate-pest-{key}"
        for i, chunk in enumerate(chunks):
            metadata = {
                'text': chunk,
                'source': f"NC State TurfFiles - {name}",
                'type': 'pest_guide',
                'pest_name': name.lower(),
            }
            all_vectors.append({
                'id': f"{base_id}-{i}",
                'chunk': chunk,
                'metadata': metadata
            })

    logger.info(f"\nTotal vectors: {len(all_vectors)}")

    # Embed and upsert
    uploaded = 0
    for batch_start in range(0, len(all_vectors), BATCH_SIZE):
        batch = all_vectors[batch_start:batch_start + BATCH_SIZE]
        texts = [v['chunk'] for v in batch]
        embeddings = embed_texts(openai_client, texts)
        if not embeddings:
            continue
        upsert_batch = [
            {'id': v['id'], 'values': emb, 'metadata': v['metadata']}
            for v, emb in zip(batch, embeddings)
        ]
        try:
            index.upsert(vectors=upsert_batch)
            uploaded += len(upsert_batch)
            logger.info(f"  Upserted: {uploaded}/{len(all_vectors)}")
        except Exception as e:
            logger.error(f"Upsert error: {e}")
        time.sleep(0.5)

    logger.info(f"\nDone! {uploaded} vectors for {len(pests)} pests.")


if __name__ == "__main__":
    main()
