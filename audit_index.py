"""
Audit script to analyze what's in the Pinecone index.
Scans the ENTIRE index and categorizes by copyright risk.
"""

import os
from collections import defaultdict
from dotenv import load_dotenv
from pinecone import Pinecone
from openai import OpenAI

load_dotenv()

# Copyright risk categories
PUBLIC_DOMAIN_KEYWORDS = [
    'epa', 'usda', 'extension', '.edu', 'ntep', 'university',
    'label', 'sds', 'msds', 'specimen', 'usga', 'gcsaa',
    'state of', 'department of agriculture'
]

LIKELY_COPYRIGHTED_KEYWORDS = [
    'journal', 'textbook', 'book', 'chapter', 'article',
    'thesis', 'dissertation', 'hortsci', 'agronomy journal',
    'crop science', 'plant disease', 'weed science',
    'intl turfgrass soc'
]

MANUFACTURER_KEYWORDS = [
    'bayer', 'syngenta', 'basf', 'corteva', 'pbi gordon', 'nufarm',
    'fmc', 'quali-pro', 'primesource', 'solution sheet', 'brochure',
    'envu', 'target specialty'
]


def categorize_source(source_name: str, doc_type: str) -> str:
    """Categorize a source by copyright risk."""
    name_lower = source_name.lower()

    # Check for likely copyrighted first (higher priority)
    if any(kw in name_lower for kw in LIKELY_COPYRIGHTED_KEYWORDS):
        return 'COPYRIGHTED'

    # Check for public domain indicators
    if any(kw in name_lower for kw in PUBLIC_DOMAIN_KEYWORDS):
        return 'PUBLIC'

    # EPA labels are public
    if doc_type == 'pesticide_label':
        return 'PUBLIC'

    # NTEP is public
    if doc_type == 'research_trial' or 'ntep' in name_lower:
        return 'PUBLIC'

    # Manufacturer content
    if any(kw in name_lower for kw in MANUFACTURER_KEYWORDS):
        return 'MANUFACTURER'

    # Default to unknown
    return 'UNKNOWN'


def audit_pinecone_index():
    """Scan entire Pinecone index and audit all documents."""

    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index(os.getenv("PINECONE_INDEX", "turf-research"))

    # Get index stats
    stats = index.describe_index_stats()
    total_vectors = stats.total_vector_count

    print("\n" + "=" * 70)
    print("PINECONE INDEX AUDIT - FULL SCAN")
    print("=" * 70)
    print(f"\nTotal vectors in index: {total_vectors:,}")

    if total_vectors == 0:
        print("\nIndex is empty!")
        return

    sources = defaultdict(lambda: {'count': 0, 'type': None, 'sample_text': ''})

    print("\nScanning entire index...")
    print("This may take a moment for large indexes...\n")

    try:
        # List all vector IDs
        all_ids = []
        for ids_batch in index.list():
            all_ids.extend(ids_batch)

        print(f"Found {len(all_ids)} vectors to scan")

        # Fetch in batches
        batch_size = 100
        checked = 0

        for i in range(0, len(all_ids), batch_size):
            batch_ids = all_ids[i:i + batch_size]
            fetch_result = index.fetch(ids=batch_ids)

            for vec_id, vec_data in fetch_result.vectors.items():
                metadata = vec_data.metadata or {}
                source = metadata.get('source', 'Unknown')
                doc_type = metadata.get('type', 'unknown')
                text = metadata.get('text', '')[:200]

                sources[source]['count'] += 1
                sources[source]['type'] = doc_type
                if not sources[source]['sample_text']:
                    sources[source]['sample_text'] = text

            checked += len(batch_ids)
            if checked % 1000 == 0:
                print(f"  Scanned {checked}/{len(all_ids)} vectors...")

        print(f"  Scanned {checked}/{len(all_ids)} vectors... Done!")

    except Exception as e:
        print(f"Error with full scan: {e}")
        print("Falling back to sample-based audit...")

        # Fallback to sampling
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        sample_queries = [
            "fungicide disease control bentgrass",
            "herbicide weed control bermuda",
            "insecticide pest management turf",
            "irrigation water management golf",
            "fertilizer nitrogen application",
            "mowing height putting green",
            "soil testing amendment",
            "turfgrass research journal",
            "plant growth regulator primo",
            "dollar spot brown patch anthracnose"
        ]

        all_matches = []
        for query in sample_queries:
            try:
                response = client.embeddings.create(
                    input=query,
                    model="text-embedding-3-small"
                )
                embedding = response.data[0].embedding
                results = index.query(
                    vector=embedding,
                    top_k=200,
                    include_metadata=True
                )
                all_matches.extend(results.get('matches', []))
            except Exception as e:
                print(f"  Error: {e}")

        seen_ids = set()
        for match in all_matches:
            if match['id'] in seen_ids:
                continue
            seen_ids.add(match['id'])

            metadata = match.get('metadata', {})
            source = metadata.get('source', 'Unknown')
            doc_type = metadata.get('type', 'unknown')
            text = metadata.get('text', '')[:200]

            sources[source]['count'] += 1
            sources[source]['type'] = doc_type
            if not sources[source]['sample_text']:
                sources[source]['sample_text'] = text

    # Categorize and display
    categorized = defaultdict(list)

    for source, info in sources.items():
        category = categorize_source(source, info['type'])
        categorized[category].append({
            'name': source,
            'type': info['type'],
            'chunks': info['count'],
            'sample': info['sample_text'][:100]
        })

    # Print results by category
    print(f"\n" + "=" * 70)
    print(f"FOUND {len(sources)} UNIQUE SOURCES")
    print("=" * 70)

    # COPYRIGHTED - show first
    print("\n❌ LIKELY COPYRIGHTED (should remove):")
    print("-" * 50)
    if categorized['COPYRIGHTED']:
        for src in sorted(categorized['COPYRIGHTED'], key=lambda x: x['name']):
            print(f"  • {src['name']}")
            print(f"    Type: {src['type']} | Chunks: {src['chunks']}")
    else:
        print("  ✓ None found!")

    # UNKNOWN
    print("\n❓ UNKNOWN (review manually):")
    print("-" * 50)
    if categorized['UNKNOWN']:
        for src in sorted(categorized['UNKNOWN'], key=lambda x: x['name']):
            print(f"  • {src['name']}")
            print(f"    Type: {src['type']} | Chunks: {src['chunks']}")
    else:
        print("  ✓ None found!")

    # MANUFACTURER
    print("\n⚠️  MANUFACTURER (usually OK, verify terms):")
    print("-" * 50)
    if categorized['MANUFACTURER']:
        for src in sorted(categorized['MANUFACTURER'], key=lambda x: x['name']):
            print(f"  • {src['name']}")
            print(f"    Type: {src['type']} | Chunks: {src['chunks']}")
    else:
        print("  (none found)")

    # PUBLIC DOMAIN
    print("\n✅ PUBLIC DOMAIN / LOW RISK:")
    print("-" * 50)
    if categorized['PUBLIC']:
        for src in sorted(categorized['PUBLIC'], key=lambda x: x['name']):
            print(f"  • {src['name']}")
            print(f"    Type: {src['type']} | Chunks: {src['chunks']}")
    else:
        print("  (none found)")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    copyrighted_chunks = sum(s['chunks'] for s in categorized['COPYRIGHTED'])
    unknown_chunks = sum(s['chunks'] for s in categorized['UNKNOWN'])
    manufacturer_chunks = sum(s['chunks'] for s in categorized['MANUFACTURER'])
    public_chunks = sum(s['chunks'] for s in categorized['PUBLIC'])

    print(f"  ❌ Copyrighted:  {len(categorized['COPYRIGHTED']):3} sources ({copyrighted_chunks:,} chunks)")
    print(f"  ❓ Unknown:      {len(categorized['UNKNOWN']):3} sources ({unknown_chunks:,} chunks)")
    print(f"  ⚠️  Manufacturer: {len(categorized['MANUFACTURER']):3} sources ({manufacturer_chunks:,} chunks)")
    print(f"  ✅ Public:       {len(categorized['PUBLIC']):3} sources ({public_chunks:,} chunks)")
    print(f"  ─────────────────────────────────")
    print(f"  TOTAL:          {len(sources):3} sources ({total_vectors:,} chunks)")
    print("=" * 70)

    if categorized['COPYRIGHTED']:
        print("\n⚠️  ACTION REQUIRED: Run cleanup_copyrighted.py to remove copyrighted content")

    print("")

    return {
        'total_vectors': total_vectors,
        'sources': len(sources),
        'categories': {k: len(v) for k, v in categorized.items()}
    }


if __name__ == "__main__":
    audit_pinecone_index()
