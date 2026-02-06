"""
Script to remove copyrighted content from Pinecone index.
Uses metadata filtering to find ALL matching vectors.
Run locally with your API keys.
"""

import os
from dotenv import load_dotenv
from pinecone import Pinecone
from openai import OpenAI

load_dotenv()

# Partial matches - will match if source contains these strings (case-insensitive)
PARTIAL_MATCHES = [
    "agronomy journal",
    "hortsci",
    "turf+book",
    "turf book",
    "bauer_samuel",
    "intl turfgrass soc",
    "wet.2021",
    "textbook",
    "journal article",
]


def cleanup_index():
    """Remove copyrighted sources from Pinecone index using comprehensive scan."""

    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index(os.getenv("PINECONE_INDEX", "turf-research"))
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    print("\n" + "=" * 60)
    print("PINECONE CLEANUP - REMOVING COPYRIGHTED CONTENT")
    print("=" * 60)

    # Get index stats
    stats = index.describe_index_stats()
    total_vectors = stats.total_vector_count
    print(f"\nTotal vectors in index: {total_vectors:,}")

    if total_vectors == 0:
        print("Index is empty!")
        return

    # We'll scan the entire index by listing all vector IDs
    print("\nScanning entire index for copyrighted content...")
    print("This may take a moment...\n")

    ids_to_delete = []
    deleted_by_source = {}

    # List all vectors in the index
    # Pinecone list() returns paginated results
    try:
        # Get all vector IDs
        all_ids = []
        for ids_batch in index.list():
            all_ids.extend(ids_batch)

        print(f"Found {len(all_ids)} vector IDs to check")

        # Fetch vectors in batches to check metadata
        batch_size = 100
        checked = 0

        for i in range(0, len(all_ids), batch_size):
            batch_ids = all_ids[i:i + batch_size]

            # Fetch the vectors with metadata
            fetch_result = index.fetch(ids=batch_ids)

            for vec_id, vec_data in fetch_result.vectors.items():
                metadata = vec_data.metadata or {}
                source = metadata.get('source', '').lower()

                # Check if source matches any copyrighted pattern
                should_delete = False
                for pattern in PARTIAL_MATCHES:
                    if pattern in source:
                        should_delete = True
                        break

                if should_delete:
                    ids_to_delete.append(vec_id)
                    original_source = metadata.get('source', 'Unknown')
                    if original_source not in deleted_by_source:
                        deleted_by_source[original_source] = 0
                    deleted_by_source[original_source] += 1

            checked += len(batch_ids)
            if checked % 500 == 0:
                print(f"  Checked {checked}/{len(all_ids)} vectors...")

    except Exception as e:
        print(f"Error scanning index: {e}")
        print("\nFalling back to search-based method...")

        # Fallback to search-based method with many queries
        search_queries = [
            "bermudagrass mowing heights",
            "turfgrass textbook",
            "journal article research",
            "agronomy study",
            "hortscience publication",
            "turfgrass society research",
            "weed technology",
            "thesis dissertation turf",
            "bentgrass management",
            "warm season grass",
            "cool season turfgrass",
            "fertilizer nitrogen",
            "disease control fungicide",
            "putting green maintenance",
            "golf course turf",
            "sports field management",
            "lawn care practices",
            "soil amendment",
            "irrigation scheduling",
            "mowing frequency height",
        ]

        all_matches = []

        for query in search_queries:
            try:
                response = client.embeddings.create(
                    input=query,
                    model="text-embedding-3-small"
                )
                embedding = response.data[0].embedding

                results = index.query(
                    vector=embedding,
                    top_k=500,
                    include_metadata=True
                )

                all_matches.extend(results.get('matches', []))
            except Exception as e:
                print(f"  Error searching '{query}': {e}")

        # Deduplicate and check
        seen_ids = set()
        for match in all_matches:
            if match['id'] in seen_ids:
                continue
            seen_ids.add(match['id'])

            metadata = match.get('metadata', {})
            source = metadata.get('source', '').lower()

            for pattern in PARTIAL_MATCHES:
                if pattern in source:
                    ids_to_delete.append(match['id'])
                    original_source = metadata.get('source', 'Unknown')
                    if original_source not in deleted_by_source:
                        deleted_by_source[original_source] = 0
                    deleted_by_source[original_source] += 1
                    break

    print(f"\nFound {len(ids_to_delete)} vectors to delete")

    if not ids_to_delete:
        print("No matching vectors found to delete.")
        print("\nYour index appears clean of the targeted copyrighted content.")
        return

    # Show what we're deleting
    print("\nSources being removed:")
    print("-" * 40)
    for source, count in sorted(deleted_by_source.items()):
        print(f"  • {source}: {count} chunks")

    # Confirm before deleting
    print("\n" + "=" * 60)
    response = input("Proceed with deletion? (yes/no): ")

    if response.lower() != 'yes':
        print("Aborted. No changes made.")
        return

    # Delete in batches of 100
    print("\nDeleting vectors...")
    batch_size = 100

    for i in range(0, len(ids_to_delete), batch_size):
        batch = ids_to_delete[i:i + batch_size]
        try:
            index.delete(ids=batch)
            print(f"  Deleted batch {i // batch_size + 1} ({len(batch)} vectors)")
        except Exception as e:
            print(f"  Error deleting batch: {e}")

    # Get new stats
    stats = index.describe_index_stats()
    print(f"\nTotal vectors after cleanup: {stats.total_vector_count:,}")

    print("\n" + "=" * 60)
    print("CLEANUP COMPLETE")
    print("=" * 60)
    print(f"\nRemoved {len(ids_to_delete)} vectors from {len(deleted_by_source)} sources")
    print("\nSources removed:")
    for source in sorted(deleted_by_source.keys()):
        print(f"  ✓ {source}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    cleanup_index()
