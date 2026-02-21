#!/usr/bin/env python3
"""
Scrape all 56 GreenCast weed pages using Playwright and upload to Pinecone.
Strips Syngenta product recommendations - keeps only weed science
(identification, cultural management, life cycle, distribution).
"""
import os
import re
import hashlib
import logging
import time
import json
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

WEED_SLUGS = [
    "Annual-Bluegrass","Annual-Sedge","Barnyardgrass","Bentgrass","Black-Medic",
    "Buckhorn-Plantain","Canada-Thistle","Carolina-Geranium","Carpetweed",
    "Common-Bermudagrass","Common-Chickweed","Common-Purslane","Corn-Speedwell",
    "Crabgrass,-Smooth-and-Large","Crowfootgrass","Dallisgrass","Dandelion",
    "Dichondra","Dollarweed---Pennywort","Doveweed","Field-Sandbur","Florida-Betony",
    "Florida-pusley","Foxtails","Globe-Sedge","Goosegrass","Green-Kyllinga",
    "Ground-Ivy","Groundsel","Henbit","Knotweed","Lawn-Burweed","Morningglory",
    "Mouse-ear-Chickweed","Nimblewill","Parsley-Piert","Persian-Speedwell",
    "Purple-Nutsedge","Quackgrass","Roughstalk-Bluegrass","Ryegrass,-Italian---Annual",
    "Ryegrass,-Perennial","Shepherd--s-Purse","Southern-Sandbur",
    "Spotted-Spurge---Prostrate-Spurge","Thin-Paspalum---Bull-Paspalum",
    "Torpedograss","Tropical-Carpetgrass","Tropical-Signalgrass",
    "Virginia-buttonweed","White-Clover","Wild-Garlic","Wild-Violet",
    "Windmillgrass","Yellow-Nutsedge","Yellow-Woodsorrel---Oxalis"
]

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


def scrape_all_weeds():
    """Use Playwright to scrape all weed pages."""
    from playwright.sync_api import sync_playwright

    weeds = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for i, slug in enumerate(WEED_SLUGS):
            url = f"https://www.greencastonline.com/weedguide/{slug}"
            name = SLUG_TO_NAME.get(slug, slug.replace("-", " "))
            try:
                page.goto(url, wait_until="networkidle", timeout=15000)
                page.wait_for_timeout(3000)  # Extra wait for JS render

                text = page.inner_text("body")
                if not text or len(text) < 50:
                    logger.warning(f"  [{i+1}/56] EMPTY: {name}")
                    continue

                # Strip product options section
                prod_idx = text.find("Product Options:")
                if prod_idx > 0:
                    text = text[:prod_idx]

                # Strip header junk
                print_idx = text.find("Print Page")
                if print_idx > 0:
                    text = text[print_idx + len("Print Page"):]

                # Clean up
                text = re.sub(r'\$\(document\)[\s\S]*?\}\);', '', text)
                text = re.sub(r'SHARE:.*', '', text)
                text = re.sub(r'//document ready', '', text)
                text = re.sub(r'\n{3,}', '\n\n', text).strip()

                if len(text) < 50:
                    logger.warning(f"  [{i+1}/56] TOO SHORT after cleaning: {name}")
                    continue

                weeds[slug] = text[:5000]
                logger.info(f"  [{i+1}/56] OK: {name} ({len(text)} chars)")

            except Exception as e:
                logger.error(f"  [{i+1}/56] ERROR: {name} - {e}")

        browser.close()

    return weeds


def clean_text(text):
    """Remove Syngenta product references and brand names."""
    brand_patterns = [
        r'(?i)syngenta\b', r'(?i)greencast\b', r'(?i)\bmonument\b(?! valley)',
        r'(?i)\btenacity\b', r'(?i)\brecognition\b', r'(?i)\bturflon\b',
        r'(?i)\brevolver\b', r'(?i)\bdismiss\b', r'(?i)\bbarricade\b',
        r'(?i)\baccelaim\b', r'(?i)\bfusilade\b', r'(?i)\bsedgehammer\b',
        r'(?i)\bsureseal\b', r'(?i)\btriumph\b', r'(?i)\bheritage\b(?! (?:cultivar|variety))',
        r'(?i)GreenTrust\s*365\b', r'(?i)Performance\s*Guarantee',
        r'(?i)FIFRA Section 2\(ee\)[\s\S]*?(?:\.|$)',
    ]
    for pat in brand_patterns:
        text = re.sub(pat, '', text)
    text = re.sub(r'\s{2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
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
    """Embed a batch of texts."""
    try:
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
        return [item.embedding for item in response.data]
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return None


def build_weed_document(name, text):
    """Build a clean weed document for Pinecone."""
    doc = f"Weed: {name}\n\n{text}"
    return clean_text(doc)


def main():
    # Step 1: Scrape all weed pages
    logger.info("=== Scraping 56 GreenCast weed pages ===")
    weeds = scrape_all_weeds()
    logger.info(f"\nScraped {len(weeds)} weeds successfully")

    # Save scraped data for reference
    with open("weed_scraped_data.json", "w") as f:
        json.dump(weeds, f, indent=2)
    logger.info("Saved scraped data to weed_scraped_data.json")

    if not weeds:
        logger.error("No weeds scraped! Exiting.")
        return

    # Step 2: Connect to Pinecone
    openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index("turf-research")

    # Step 3: Build vectors
    all_vectors = []
    for slug, text in weeds.items():
        name = SLUG_TO_NAME.get(slug, slug.replace("-", " "))
        doc_text = build_weed_document(name, text)
        chunks = smart_chunk(doc_text)
        if not chunks:
            chunks = [doc_text]

        logger.info(f"  {name}: {len(chunks)} chunks ({len(doc_text)} chars)")

        key = slug.lower().replace("-", "_").replace(",", "").replace("__", "_")
        while "__" in key:
            key = key.replace("__", "_")

        base_id = f"greencast-weed-{key}"
        for i, chunk in enumerate(chunks):
            vector_id = f"{base_id}-{i}"

            # Try to extract weed family and life cycle from text
            weed_family = ""
            life_cycle = ""
            scientific_name = ""
            fm = re.search(r'Weed Family:\s*(.+?)(?:\n|$)', text)
            if fm: weed_family = fm.group(1).strip()
            lm = re.search(r'Life Cycle:\s*(.+?)(?:\n|$)', text)
            if lm: life_cycle = lm.group(1).strip()
            sm = re.search(r'Scientific Name:\s*(.+?)(?:\n|$)', text)
            if sm: scientific_name = sm.group(1).strip()

            metadata = {
                'text': chunk,
                'source': f"GreenCast Weed Guide - {name}",
                'type': 'weed_guide',
                'weed_name': name.lower(),
            }
            if weed_family: metadata['weed_family'] = weed_family
            if life_cycle: metadata['life_cycle'] = life_cycle
            if scientific_name: metadata['scientific_name'] = scientific_name

            all_vectors.append({
                'id': vector_id,
                'chunk': chunk,
                'metadata': metadata
            })

    logger.info(f"\nTotal vectors to upload: {len(all_vectors)}")

    # Step 4: Embed and upsert
    uploaded = 0
    for batch_start in range(0, len(all_vectors), BATCH_SIZE):
        batch = all_vectors[batch_start:batch_start + BATCH_SIZE]
        texts = [v['chunk'] for v in batch]

        embeddings = embed_texts(openai_client, texts)
        if not embeddings:
            logger.error(f"Failed to embed batch starting at {batch_start}")
            continue

        upsert_batch = []
        for v, embedding in zip(batch, embeddings):
            upsert_batch.append({
                'id': v['id'],
                'values': embedding,
                'metadata': v['metadata']
            })

        try:
            index.upsert(vectors=upsert_batch)
            uploaded += len(upsert_batch)
            logger.info(f"  Upserted batch: {uploaded}/{len(all_vectors)} vectors")
        except Exception as e:
            logger.error(f"Upsert error: {e}")

        time.sleep(0.5)

    logger.info(f"\nDone! Uploaded {uploaded} vectors for {len(weeds)} weeds.")


if __name__ == "__main__":
    main()
