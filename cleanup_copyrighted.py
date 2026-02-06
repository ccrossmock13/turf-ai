"""
Script to remove copyrighted content from Pinecone index.
Run locally with your API keys.
"""

import os
from dotenv import load_dotenv
from pinecone import Pinecone
from openai import OpenAI

load_dotenv()

# Sources to remove - these are copyrighted
SOURCES_TO_REMOVE = [
    "Agronomy Journal 2025 Chen Finer Topdressing Sand Affects Creeping Bentgrass Quality And Surface Characteristics 2",
    "Hortsci Article P1323",
    "Hortsci Article P1545",
    "Hortsci Article P1745",
    "Turf+Book",
    "15C11B43F066Efd06E763E7Beb667Db5Fcaa624C.8",
    "2019May",
    "250828081809",
    "Bauer_Samuel_May2011",
    "Unknown - Bauer_Samuel_May2011",
    "hortsci-article-p1545.pdf",
    "Intl Turfgrass Soc Res J - 2024 - Amundsen - Management costs influence golfer perceptions of turfgrass quality and.pdf",
    "Intl Turfgrass Soc Res J 2024 Amundsen Management Costs Influence Golfer Perceptions Of Turfgrass Quality And",
    "wet.2021.106.pdf",
]

# Partial matches - will match if source contains these strings
PARTIAL_MATCHES = [
    "Agronomy Journal",
    "Hortsci Article",
    "hortsci-article",
    "Turf+Book",
    "Bauer_Samuel",
    "Intl Turfgrass Soc",
    "wet.2021",
]


def cleanup_index():
    """Remove copyrighted sources from Pinecone index."""

    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index(os.getenv("PINECONE_INDEX", "turf-research"))
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    print("\n" + "=" * 60)
    print("PINECONE CLEANUP - REMOVING COPYRIGHTED CONTENT")
    print("=" * 60)

    # Get index stats
    stats = index.describe_index_stats()
    print(f"\nTotal vectors before cleanup: {stats.total_vector_count:,}")

    # Track what we delete
    deleted_ids = []
    deleted_by_source = {}

    # Search for each source using various queries
    search_queries = [
        "turfgrass management bentgrass",
        "fertilizer nitrogen application",
        "topdressing sand quality",
        "thatch control velvet",
        "creeping bentgrass putting green",
        "turfgrass research study",
        "golf course maintenance",
        "plant growth regulator",
        "disease control fungicide",
        "soil amendment organic",
    ]

    print("\nSearching for vectors to remove...")

    all_matches = []

    for query in search_queries:
        try:
            # Get embedding
            response = client.embeddings.create(
                input=query,
                model="text-embedding-3-small"
            )
            embedding = response.data[0].embedding

            # Query with high top_k to find as many as possible
            results = index.query(
                vector=embedding,
                top_k=200,
                include_metadata=True
            )

            all_matches.extend(results.get('matches', []))

        except Exception as e:
            print(f"  Error searching '{query}': {e}")

    # Deduplicate
    seen_ids = set()
    unique_matches = []
    for match in all_matches:
        if match['id'] not in seen_ids:
            seen_ids.add(match['id'])
            unique_matches.append(match)

    print(f"Found {len(unique_matches)} unique vectors to check")

    # Check each match against our removal list
    ids_to_delete = []

    for match in unique_matches:
        metadata = match.get('metadata', {})
        source = metadata.get('source', '')

        should_delete = False

        # Check exact matches
        if source in SOURCES_TO_REMOVE:
            should_delete = True

        # Check partial matches
        for partial in PARTIAL_MATCHES:
            if partial.lower() in source.lower():
                should_delete = True
                break

        if should_delete:
            ids_to_delete.append(match['id'])
            if source not in deleted_by_source:
                deleted_by_source[source] = 0
            deleted_by_source[source] += 1

    print(f"\nFound {len(ids_to_delete)} vectors to delete")

    if not ids_to_delete:
        print("No matching vectors found to delete.")
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
