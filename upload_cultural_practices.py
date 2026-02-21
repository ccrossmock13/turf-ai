#!/usr/bin/env python3
"""
Scrape cultural practices, irrigation, and fertility guides from
Virginia Golf BMP, Cornell Golf BMP, and Penn State Extension.
Upload to Pinecone for RAG retrieval.
"""
import os
import re
import json
import logging
import time
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

# Pages to scrape - organized by topic
PAGES = {
    # Virginia Golf BMP Guide - Cultural Practices
    "va_cultural_practices": {
        "url": "https://vgcsabmp.org/6-cultural-practices/",
        "source": "Virginia Golf Course BMP Guide - Cultural Practices",
        "type": "cultural_practices",
        "topics": ["mowing", "aerification", "topdressing", "overseeding", "rolling", "wetting agents", "plant growth regulators"]
    },
    # Virginia Golf BMP Guide - Irrigation
    "va_irrigation": {
        "url": "https://vgcsabmp.org/2-irrigation/",
        "source": "Virginia Golf Course BMP Guide - Irrigation",
        "type": "irrigation",
        "topics": ["irrigation", "water conservation", "drought", "ET", "soil moisture"]
    },
    # Virginia Golf BMP Guide - Nutrient Management
    "va_nutrient_management": {
        "url": "https://vgcsabmp.org/5-nutrient-management/",
        "source": "Virginia Golf Course BMP Guide - Nutrient Management",
        "type": "fertility",
        "topics": ["fertilization", "nitrogen", "phosphorus", "potassium", "soil testing", "micronutrients"]
    },
    # Cornell Golf BMP - Cultural Practices
    "cornell_cultural": {
        "url": "https://nysgolfbmp.cals.cornell.edu/7-cultural-practices/",
        "source": "Cornell Golf Course BMP Guide - Cultural Practices",
        "type": "cultural_practices",
        "topics": ["mowing", "organic matter", "topdressing", "cultivation", "species selection"]
    },
    # Cornell Golf BMP - Nutrient Management
    "cornell_nutrient": {
        "url": "https://nysgolfbmp.cals.cornell.edu/6-nutrient-management/",
        "source": "Cornell Golf Course BMP Guide - Nutrient Management",
        "type": "fertility",
        "topics": ["fertilization", "nitrogen", "phosphorus", "soil testing"]
    },
    # Cornell Golf BMP - Water Management
    "cornell_water": {
        "url": "https://nysgolfbmp.cals.cornell.edu/5-water-management/",
        "source": "Cornell Golf Course BMP Guide - Water Management",
        "type": "irrigation",
        "topics": ["irrigation", "water quality", "drainage", "stormwater"]
    },
    # Penn State - Fertilization Guide
    "psu_fertilization": {
        "url": "https://extension.psu.edu/turfgrass-fertilization-a-basic-guide-for-professional-turfgrass-managers",
        "source": "Penn State Extension - Turfgrass Fertilization Guide",
        "type": "fertility",
        "topics": ["fertilization", "nitrogen", "phosphorus", "potassium", "soil testing", "rates"]
    },
    # Penn State - Irrigation Principles
    "psu_irrigation": {
        "url": "https://extension.psu.edu/principles-of-turfgrass-irrigation",
        "source": "Penn State Extension - Turfgrass Irrigation Principles",
        "type": "irrigation",
        "topics": ["irrigation", "watering", "soil moisture", "ET", "scheduling"]
    },
    # Penn State - Thatch Management
    "psu_thatch": {
        "url": "https://extension.psu.edu/managing-thatch-in-lawns",
        "source": "Penn State Extension - Thatch Management",
        "type": "cultural_practices",
        "topics": ["thatch", "dethatching", "aerification", "topdressing"]
    },
    # Penn State - Lawn Management Through Seasons
    "psu_seasonal": {
        "url": "https://extension.psu.edu/lawn-management-through-the-seasons",
        "source": "Penn State Extension - Seasonal Lawn Management",
        "type": "cultural_practices",
        "topics": ["seasonal", "spring", "summer", "fall", "winter", "mowing", "fertilization"]
    },
    # Penn State - Shade Management
    "psu_shade": {
        "url": "https://extension.psu.edu/growing-turf-under-shaded-conditions",
        "source": "Penn State Extension - Turf Under Shade",
        "type": "cultural_practices",
        "topics": ["shade", "tree competition", "species selection", "cultural practices"]
    },
    # Penn State - Liming
    "psu_liming": {
        "url": "https://extension.psu.edu/liming-turfgrass-areas",
        "source": "Penn State Extension - Liming Turfgrass",
        "type": "fertility",
        "topics": ["liming", "pH", "soil acidity", "calcium", "magnesium"]
    },
    # Penn State - Water Quality
    "psu_water_quality": {
        "url": "https://extension.psu.edu/irrigation-water-quality-guidelines-for-turfgrass-sites",
        "source": "Penn State Extension - Irrigation Water Quality",
        "type": "irrigation",
        "topics": ["water quality", "salinity", "sodium", "bicarbonate", "irrigation"]
    },
    # NC State - Heat and Drought
    "ncstate_drought": {
        "url": "https://www.turffiles.ncsu.edu/2024/06/managing-landscape-turfgrasses-under-heat-and-drought-conditions/",
        "source": "NC State Extension - Heat and Drought Management",
        "type": "irrigation",
        "topics": ["drought", "heat stress", "irrigation", "water conservation"]
    },
}


def scrape_all_pages():
    """Use Playwright to scrape all pages."""
    from playwright.sync_api import sync_playwright

    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for i, (key, info) in enumerate(PAGES.items()):
            url = info["url"]
            try:
                page.goto(url, wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(2000)

                text = page.inner_text("body")
                if not text or len(text) < 100:
                    logger.warning(f"  [{i+1}/{len(PAGES)}] EMPTY: {key}")
                    continue

                # Clean up navigation/footer
                # Try to find main content
                for marker in ["Skip to content", "Main Content"]:
                    idx = text.find(marker)
                    if idx >= 0:
                        text = text[idx + len(marker):]

                # Remove footer junk
                for footer in ["Share This Article", "© 20", "Privacy Policy", "Footer", "SHARE THIS",
                               "Was the information on this page helpful", "N.C. Cooperative Extension",
                               "Penn State Extension", "Skip to toolbar"]:
                    idx = text.find(footer)
                    if idx > 500:
                        text = text[:idx]

                text = re.sub(r'\n{3,}', '\n\n', text).strip()

                # Cap at 15000 chars for long BMP guides
                results[key] = text[:15000]
                logger.info(f"  [{i+1}/{len(PAGES)}] OK: {key} ({len(text)} chars)")

            except Exception as e:
                logger.error(f"  [{i+1}/{len(PAGES)}] ERROR: {key} - {e}")

        browser.close()

    return results


def clean_text(text):
    """Remove unnecessary content."""
    # Remove navigation elements
    text = re.sub(r'(?i)table of contents.*?\n', '', text)
    text = re.sub(r'(?i)menu\s*\n', '', text)
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
    try:
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
        return [item.embedding for item in response.data]
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return None


def main():
    logger.info("=== Scraping cultural practices, irrigation & fertility guides ===")
    pages = scrape_all_pages()
    logger.info(f"\nScraped {len(pages)} pages successfully")

    with open("cultural_scraped_data.json", "w") as f:
        json.dump(pages, f, indent=2)

    if not pages:
        logger.error("No pages scraped!")
        return

    # Connect
    openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index("turf-research")

    # Build vectors
    all_vectors = []
    for key, text in pages.items():
        info = PAGES[key]
        doc_text = clean_text(text)
        chunks = smart_chunk(doc_text)
        if not chunks:
            chunks = [doc_text]

        logger.info(f"  {info['source']}: {len(chunks)} chunks ({len(doc_text)} chars)")

        base_id = f"guide-{key}"
        for i, chunk in enumerate(chunks):
            metadata = {
                'text': chunk,
                'source': info['source'],
                'type': info['type'],
            }
            if info.get('topics'):
                metadata['topics'] = ', '.join(info['topics'])

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

    logger.info(f"\nDone! {uploaded} vectors for {len(pages)} pages.")
    logger.info(f"Topics covered: cultural practices, irrigation, fertility/nutrient management")


if __name__ == "__main__":
    main()
