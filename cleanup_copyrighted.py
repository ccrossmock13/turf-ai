"""
Cleanup script - deletes copyrighted content from Pinecone index.
Uses the same search queries as the audit to find the same vectors.
"""

import os
from dotenv import load_dotenv
from pinecone import Pinecone
from openai import OpenAI

load_dotenv()

# Patterns to match in source names (case-insensitive)
PATTERNS_TO_REMOVE = [
    # Journals
    "agronomy journal",
    "hortsci",
    "crop science",
    "crop forage",
    "intl turfgrass soc",
    "weed science",
    "plant disease",
    "agriculture 10",

    # Magazines
    "golf course architecture",
    "golfdom",
    "gcm magazine",
    "gcm aug",
    "gcm june",
    "gcm jan",
    "carolina gcsa",

    # Books
    "turf+book",
    "turf book",
    "textbook",
    "handbook",

    # Thesis
    "bauer_samuel",
    "bauer samuel",
    "thesis",
    "dissertation",

    # Unknown files to remove
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

# Use SAME queries as audit + extras to find all content
SEARCH_TERMS = [
    # From audit script
    "fungicide disease control",
    "herbicide weed management",
    "insecticide pest control",
    "bentgrass putting green",
    "bermudagrass fairway",
    "fertilizer nitrogen",
    "irrigation water",
    "mowing height",
    "dollar spot brown patch",
    "plant growth regulator",
    "turfgrass research journal",
    "textbook chapter turf",
    "thesis dissertation",
    "warm season grass",
    "cool season turfgrass",
    # Extra targeted queries
    "bermudagrass mowing heights adaptable",
    "bunker maintenance sand drainage",
    "golf course architecture design holes",
    "superintendent management GCM",
    "trinexapac ethyl primo maxx",
    "poa annua weed control ecology",
    "azoxystrobin fungicide distribution",
    "golfer perceptions quality",
    "ultradwarf bermuda putting",
    "topdressing sand particle size",
    "thatch control cultivation",
    "root zone construction",
    "greens management practices",
    "fairway renovation",
    "sports turf management",
]


def cleanup():
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index(os.getenv("PINECONE_INDEX", "turf-research"))
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    print("\n" + "=" * 50)
    print("CLEANUP - REMOVING COPYRIGHTED CONTENT")
    print("=" * 50)

    stats = index.describe_index_stats()
    print(f"\nVectors before: {stats.total_vector_count:,}")

    print(f"\nSearching with {len(SEARCH_TERMS)} queries...")

    ids_to_delete = set()  # Use set to avoid duplicates
    sources_found = {}

    for i, term in enumerate(SEARCH_TERMS):
        try:
            resp = client.embeddings.create(input=term, model="text-embedding-3-small")
            embedding = resp.data[0].embedding

            # Get more results per query
            results = index.query(vector=embedding, top_k=200, include_metadata=True)

            for match in results.get('matches', []):
                vec_id = match['id']
                if vec_id in ids_to_delete:
                    continue

                source = match.get('metadata', {}).get('source', '').lower()

                for pattern in PATTERNS_TO_REMOVE:
                    if pattern in source:
                        ids_to_delete.add(vec_id)
                        orig = match.get('metadata', {}).get('source', 'Unknown')
                        sources_found[orig] = sources_found.get(orig, 0) + 1
                        break

            if (i + 1) % 5 == 0:
                print(f"  Progress: {i+1}/{len(SEARCH_TERMS)} queries, {len(ids_to_delete)} vectors found")

        except Exception as e:
            print(f"  Error on '{term[:30]}': {e}")

    print(f"\n  Completed: {len(ids_to_delete)} vectors to delete")

    if not ids_to_delete:
        print("\n✓ No copyrighted content found!")
        return

    print(f"\nSources to remove ({len(sources_found)} unique):")
    print("-" * 40)
    for src, count in sorted(sources_found.items()):
        print(f"  • {src}: {count} chunks")

    print("-" * 40)
    resp = input("\nDelete all these? (yes/no): ")
    if resp.lower() != 'yes':
        print("Cancelled.")
        return

    # Delete in batches
    ids_list = list(ids_to_delete)
    print(f"\nDeleting {len(ids_list)} vectors...")

    for i in range(0, len(ids_list), 100):
        batch = ids_list[i:i+100]
        try:
            index.delete(ids=batch)
            print(f"  Deleted batch {i//100 + 1}: {len(batch)} vectors")
        except Exception as e:
            print(f"  Error deleting batch: {e}")

    # Verify
    stats = index.describe_index_stats()
    print(f"\nVectors after: {stats.total_vector_count:,}")
    print("\n✓ Cleanup complete!")
    print("  Run 'python audit_index.py' to verify.\n")


if __name__ == "__main__":
    cleanup()
