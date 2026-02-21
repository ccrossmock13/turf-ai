#!/usr/bin/env python3
"""
Scrape nematode guides and abiotic disorder guides from university extension sources.
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

# Pages to scrape
PAGES = {
    # === NEMATODE GUIDES ===

    # UF IFAS - Nematode Management for Golf Courses (best single source)
    "uf_nematode_golf": {
        "url": "https://ask.ifas.ufl.edu/publication/in124",
        "source": "UF IFAS - Nematode Management on Golf Courses in Florida",
        "type": "nematode_guide",
        "topics": ["nematodes", "sting nematode", "lance nematode", "root-knot nematode", "nematicide", "golf course"]
    },
    # UC IPM - Turfgrass Nematodes (7 species)
    "ucipm_nematodes": {
        "url": "https://ipm.ucanr.edu/agriculture/turfgrass/nematodes/",
        "source": "UC IPM - Turfgrass Nematodes",
        "type": "nematode_guide",
        "topics": ["nematodes", "lesion nematode", "ring nematode", "root-knot nematode", "sting nematode", "stubby root nematode", "spiral nematode"]
    },
    # Penn State - Nematode Pest Profiles (13 genera, thresholds)
    "psu_nematodes": {
        "url": "https://turfpestlab.psu.edu/pest-profiles/nematodes/",
        "source": "Penn State Turfgrass Pest Lab - Nematodes",
        "type": "nematode_guide",
        "topics": ["nematodes", "thresholds", "ring nematode", "stunt nematode", "lance nematode", "spiral nematode", "root-knot nematode"]
    },
    # UMass - Nematodes on Golf Greens (threshold table)
    "umass_nematodes": {
        "url": "https://www.umass.edu/agriculture-food-environment/turf/fact-sheets/nematodes-on-golf-greens",
        "source": "UMass Extension - Nematodes on Golf Greens",
        "type": "nematode_guide",
        "topics": ["nematodes", "thresholds", "soil sampling", "golf greens"]
    },
    # NC State - Nematodes in Turf (chemical control table)
    "ncstate_nematodes": {
        "url": "https://content.ces.ncsu.edu/nematodes-in-turf-1",
        "source": "NC State Extension - Nematodes in Turf",
        "type": "nematode_guide",
        "topics": ["nematodes", "sting nematode", "root-knot nematode", "lance nematode", "nematicide"]
    },
    # UF IFAS - Nematode Management in Residential Lawns (grass susceptibility)
    "uf_nematode_lawns": {
        "url": "https://ask.ifas.ufl.edu/publication/NG039",
        "source": "UF IFAS - Nematode Management in Residential Lawns",
        "type": "nematode_guide",
        "topics": ["nematodes", "bermudagrass", "zoysiagrass", "st augustine", "grass susceptibility"]
    },
    # LSU - Turfgrass Nematodes (southern US focus)
    "lsu_nematodes": {
        "url": "https://www.lsuagcenter.com/topics/lawn_garden/commercial_horticulture/turfgrass/turfgrass-insects/nematodes",
        "source": "LSU AgCenter - Turfgrass Nematodes",
        "type": "nematode_guide",
        "topics": ["nematodes", "sting nematode", "stubby-root nematode", "ring nematode", "southern turf"]
    },
    # UF Featured Creatures - Sting Nematode
    "uf_sting_nematode": {
        "url": "https://ask.ifas.ufl.edu/publication/IN395",
        "source": "UF IFAS - Sting Nematode (Belonolaimus longicaudatus)",
        "type": "nematode_guide",
        "topics": ["sting nematode", "nematodes", "identification", "biology"]
    },
    # UF Featured Creatures - Lance Nematode
    "uf_lance_nematode": {
        "url": "https://ask.ifas.ufl.edu/publication/IN390",
        "source": "UF IFAS - Lance Nematode (Hoplolaimus galeatus)",
        "type": "nematode_guide",
        "topics": ["lance nematode", "nematodes", "identification", "biology"]
    },
    # UF Featured Creatures - Stubby-Root Nematode
    "uf_stubbyroot_nematode": {
        "url": "https://ask.ifas.ufl.edu/publication/IN617",
        "source": "UF IFAS - Stubby-Root Nematode (Trichodorus obtusus)",
        "type": "nematode_guide",
        "topics": ["stubby-root nematode", "nematodes", "identification", "biology"]
    },

    # === ABIOTIC DISORDER GUIDES ===

    # K-State Turf Diagnostic Guide - Abiotic section (18 disorders)
    "kstate_abiotic": {
        "url": "https://www.k-state.edu/turf/resources/diagnostic-guide/index.html",
        "source": "Kansas State University - Turf Diagnostic Guide",
        "type": "abiotic_disorders",
        "topics": ["abiotic disorders", "winter desiccation", "frost", "drought stress", "black layer", "shade", "chemical injury", "compaction"]
    },
    # Penn State - Winterkill of Turfgrasses (4 types of cold injury)
    "psu_winterkill": {
        "url": "https://extension.psu.edu/winterkill-of-turfgrasses",
        "source": "Penn State Extension - Winterkill of Turfgrasses",
        "type": "abiotic_disorders",
        "topics": ["winterkill", "desiccation", "cold injury", "ice encasement", "crown hydration"]
    },
    # MSU - Winterkill of Turfgrass (species hardiness rankings)
    "msu_winterkill": {
        "url": "https://www.canr.msu.edu/resources/winterkill-of-turfgrass",
        "source": "MSU Extension - Winterkill of Turfgrass",
        "type": "abiotic_disorders",
        "topics": ["winterkill", "desiccation", "cold injury", "poa annua", "ice sheets"]
    },
    # Oklahoma State - Salinity Management
    "okstate_salinity": {
        "url": "https://extension.okstate.edu/fact-sheets/salinity-management-in-home-lawns.html",
        "source": "Oklahoma State Extension - Salinity Management in Lawns",
        "type": "abiotic_disorders",
        "topics": ["salinity", "salt damage", "salt tolerance", "leaching", "soil amendment"]
    },
    # Colorado State - Salt-Affected Sites
    "costate_salt": {
        "url": "https://extension.colostate.edu/resource/growing-turfgrass-on-salt-affected-sites/",
        "source": "Colorado State Extension - Growing Turfgrass on Salt-Affected Sites",
        "type": "abiotic_disorders",
        "topics": ["salinity", "salt tolerance", "species selection", "soil reclamation"]
    },
    # Maryland - Chemical Injury to Lawns
    "umd_chemical_injury": {
        "url": "https://extension.umd.edu/resource/chemical-injury-lawns",
        "source": "University of Maryland Extension - Chemical Injury to Lawns",
        "type": "abiotic_disorders",
        "topics": ["chemical injury", "herbicide damage", "fertilizer burn", "pesticide injury"]
    },
    # Oklahoma State - Shade Management
    "okstate_shade": {
        "url": "https://extension.okstate.edu/fact-sheets/managing-turfgrass-in-the-shade-in-oklahoma.html",
        "source": "Oklahoma State Extension - Managing Turfgrass in Shade",
        "type": "abiotic_disorders",
        "topics": ["shade stress", "tree competition", "species selection", "light requirements"]
    },
    # Minnesota - Winter Desiccation
    "umn_desiccation": {
        "url": "https://turf.umn.edu/news/winter-desiccation-turfgrass",
        "source": "University of Minnesota - Winter Desiccation of Turfgrass",
        "type": "abiotic_disorders",
        "topics": ["winter desiccation", "cold injury", "drying", "wind damage"]
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
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                text = page.inner_text("body")
                if not text or len(text) < 100:
                    logger.warning(f"  [{i+1}/{len(PAGES)}] EMPTY: {key}")
                    continue

                # Try to find main content area
                for marker in ["Skip to content", "Main Content", "Skip to main content"]:
                    idx = text.find(marker)
                    if idx >= 0:
                        text = text[idx + len(marker):]

                # Remove footer/nav junk
                for footer in ["Share This Article", "© 20", "Privacy Policy", "Footer", "SHARE THIS",
                               "Was the information on this page helpful", "N.C. Cooperative Extension",
                               "Penn State Extension", "Skip to toolbar", "Related Resources",
                               "Sign up for our newsletter", "Subscribe", "Back to top",
                               "Additional Resources", "Tags:", "Filed Under"]:
                    idx = text.find(footer)
                    if idx > 500:
                        text = text[:idx]

                text = re.sub(r'\n{3,}', '\n\n', text).strip()

                # Cap at 20000 chars for long publications
                results[key] = text[:20000]
                logger.info(f"  [{i+1}/{len(PAGES)}] OK: {key} ({len(text)} chars)")

            except Exception as e:
                logger.error(f"  [{i+1}/{len(PAGES)}] ERROR: {key} - {e}")

        browser.close()

    return results


def clean_text(text):
    """Remove unnecessary content."""
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
    logger.info("=== Scraping nematode & abiotic disorder guides ===")
    pages = scrape_all_pages()
    logger.info(f"\nScraped {len(pages)} pages successfully")

    with open("nematode_abiotic_scraped_data.json", "w") as f:
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

    # Summary
    nematode_count = sum(1 for k in pages if PAGES[k]['type'] == 'nematode_guide')
    abiotic_count = sum(1 for k in pages if PAGES[k]['type'] == 'abiotic_disorders')
    logger.info(f"Nematode guides: {nematode_count} pages")
    logger.info(f"Abiotic disorder guides: {abiotic_count} pages")


if __name__ == "__main__":
    main()
