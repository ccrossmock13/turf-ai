"""
Fast cleanup script - uses targeted searches to find and remove copyrighted content.
"""

import os
from dotenv import load_dotenv
from pinecone import Pinecone
from openai import OpenAI

load_dotenv()

# Patterns to match (case-insensitive)
PATTERNS_TO_REMOVE = [
    # Journals
    "agronomy journal",
    "hortsci",
    "crop science",
    "crop forage",
    "intl turfgrass soc",
    "weed science",
    "plant disease",
    "agriculture 10 00043",

    # Magazines (copyrighted publications)
    "golf course architecture",
    "golfdom",
    "gcm magazine",
    "gcm aug",
    "gcm june",
    "gcm jan",
    "carolina gcsa",

    # Books/Textbooks
    "turf+book",
    "turf book",
    "textbook",
    "handbook",

    # Thesis/Dissertations
    "bauer_samuel",
    "bauer samuel",
    "thesis",
    "dissertation",

    # Unknown/suspicious
    "wet.2021",
    "180828190356",
    "2016jun",
    "2019nov",
    "2024jan",
    "2025jan",
    "42085ceb",
    "4a385771f05e",
    "novembergolfflipbook",
]

# Direct search terms to find the content
SEARCH_TERMS = [
    "bermudagrass mowing heights adaptable",
    "bentgrass putting green management",
    "turfgrass textbook chapter",
    "journal article research study",
    "thesis dissertation turf",
    "agronomy hortscience publication",
    "warm season grass selection",
    "cool season turfgrass varieties",
    "nitrogen fertilizer application rates",
    "disease control fungicide timing",
    "weed management herbicide",
    "root mass canopy photosynthesis",
    "golfer perceptions turfgrass quality",
    "thatch control velvet bentgrass",
    "topdressing sand characteristics",
    "trinexapac ethyl lightweight rolling ultradwarf",
    "poa annua ecology biology integrated weed",
    "bunker maintenance sand",
    "golf course architecture design",
    "superintendent management practices",
    "azoxystrobin distribution mowing",
    "golf course sustainability",
    "clipping collection practices",
    "turfgrass quality perceptions",
    "crop forage management",
]


def cleanup():
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index(os.getenv("PINECONE_INDEX", "turf-research"))
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    print("\n" + "=" * 50)
    print("FAST CLEANUP - COPYRIGHTED CONTENT")
    print("=" * 50)

    stats = index.describe_index_stats()
    print(f"\nVectors before: {stats.total_vector_count:,}")

    print("\nSearching for copyrighted content...")

    ids_to_delete = []
    sources_found = {}

    for term in SEARCH_TERMS:
        try:
            resp = client.embeddings.create(input=term, model="text-embedding-3-small")
            embedding = resp.data[0].embedding

            results = index.query(vector=embedding, top_k=100, include_metadata=True)

            for match in results.get('matches', []):
                vec_id = match['id']
                if vec_id in [d for d in ids_to_delete]:
                    continue

                source = match.get('metadata', {}).get('source', '').lower()

                for pattern in PATTERNS_TO_REMOVE:
                    if pattern in source:
                        ids_to_delete.append(vec_id)
                        orig = match.get('metadata', {}).get('source', 'Unknown')
                        sources_found[orig] = sources_found.get(orig, 0) + 1
                        break

            print(f"  Searched: {term[:40]}... Found {len(ids_to_delete)} total")

        except Exception as e:
            print(f"  Error: {e}")

    if not ids_to_delete:
        print("\n✓ No copyrighted content found!")
        return

    print(f"\nFound {len(ids_to_delete)} vectors to delete:")
    for src, count in sorted(sources_found.items()):
        print(f"  • {src}: {count}")

    resp = input("\nDelete these? (yes/no): ")
    if resp.lower() != 'yes':
        print("Cancelled.")
        return

    # Delete
    print("\nDeleting...")
    for i in range(0, len(ids_to_delete), 100):
        batch = ids_to_delete[i:i+100]
        index.delete(ids=batch)
        print(f"  Deleted {min(i+100, len(ids_to_delete))}/{len(ids_to_delete)}")

    stats = index.describe_index_stats()
    print(f"\nVectors after: {stats.total_vector_count:,}")
    print("Done!\n")


if __name__ == "__main__":
    cleanup()
