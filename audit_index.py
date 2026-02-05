"""
Audit script to analyze what's in the Pinecone index.
Lists all unique sources and categorizes them by copyright risk.
"""

import os
from collections import defaultdict
from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()

# Copyright risk categories
PUBLIC_DOMAIN_KEYWORDS = [
    'epa', 'usda', 'extension', '.edu', 'ntep', 'state', 'university',
    'label', 'sds', 'msds', 'specimen'
]

LIKELY_COPYRIGHTED_KEYWORDS = [
    'journal', 'textbook', 'book', 'chapter', 'article'
]

MANUFACTURER_KEYWORDS = [
    'bayer', 'syngenta', 'basf', 'corteva', 'pbi gordon', 'nufarm',
    'fmc', 'quali-pro', 'primesource', 'solution sheet', 'brochure'
]


def categorize_source(source_name: str, doc_type: str) -> str:
    """Categorize a source by copyright risk."""
    name_lower = source_name.lower()

    # Check for public domain indicators
    if any(kw in name_lower for kw in PUBLIC_DOMAIN_KEYWORDS):
        return 'PUBLIC'

    # EPA labels are public
    if doc_type == 'pesticide_label':
        return 'PUBLIC'

    # NTEP is public
    if doc_type == 'research_trial' or 'ntep' in name_lower:
        return 'PUBLIC'

    # Check for likely copyrighted
    if any(kw in name_lower for kw in LIKELY_COPYRIGHTED_KEYWORDS):
        return 'COPYRIGHTED'

    # Manufacturer content
    if any(kw in name_lower for kw in MANUFACTURER_KEYWORDS):
        return 'MANUFACTURER'

    # Default to unknown
    return 'UNKNOWN'


def audit_pinecone_index():
    """Query Pinecone and audit all indexed documents."""

    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index(os.getenv("PINECONE_INDEX", "turf-research"))

    # Get index stats
    stats = index.describe_index_stats()
    total_vectors = stats.total_vector_count

    print("\n" + "=" * 70)
    print("PINECONE INDEX AUDIT")
    print("=" * 70)
    print(f"\nTotal vectors in index: {total_vectors:,}")

    if total_vectors == 0:
        print("\nIndex is empty!")
        return

    # Sample vectors to get unique sources
    # We'll do multiple queries with random vectors to sample the index
    sources = defaultdict(lambda: {'count': 0, 'type': None, 'sample_text': ''})

    print("\nSampling index to identify sources...")

    # Query with a zero vector to get random results
    # Do multiple queries to get broader coverage
    import random

    all_matches = []

    # Try to get a representative sample
    sample_queries = [
        "fungicide disease control",
        "herbicide weed control",
        "insecticide pest management",
        "bentgrass management",
        "bermuda grass care",
        "dollar spot brown patch",
        "irrigation water management",
        "fertilizer nitrogen application",
        "mowing height frequency",
        "soil testing amendment"
    ]

    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    for query in sample_queries:
        try:
            # Get embedding
            response = client.embeddings.create(
                input=query,
                model="text-embedding-3-small"
            )
            embedding = response.data[0].embedding

            # Query Pinecone
            results = index.query(
                vector=embedding,
                top_k=100,
                include_metadata=True
            )

            all_matches.extend(results.get('matches', []))
        except Exception as e:
            print(f"  Error querying '{query}': {e}")

    # Process all matches
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
            'chunks_sampled': info['count'],
            'sample': info['sample_text'][:100]
        })

    # Print results by category
    print(f"\nUnique sources found in sample: {len(sources)}")
    print("\n" + "-" * 70)

    # PUBLIC DOMAIN
    print("\n✅ PUBLIC DOMAIN / LOW RISK:")
    print("-" * 40)
    if categorized['PUBLIC']:
        for src in sorted(categorized['PUBLIC'], key=lambda x: x['name']):
            print(f"  • {src['name']}")
            print(f"    Type: {src['type']} | Chunks: {src['chunks_sampled']}")
    else:
        print("  (none found in sample)")

    # MANUFACTURER
    print("\n⚠️  MANUFACTURER CONTENT (usually freely distributed but check):")
    print("-" * 40)
    if categorized['MANUFACTURER']:
        for src in sorted(categorized['MANUFACTURER'], key=lambda x: x['name']):
            print(f"  • {src['name']}")
            print(f"    Type: {src['type']} | Chunks: {src['chunks_sampled']}")
    else:
        print("  (none found in sample)")

    # COPYRIGHTED
    print("\n❌ LIKELY COPYRIGHTED (review carefully):")
    print("-" * 40)
    if categorized['COPYRIGHTED']:
        for src in sorted(categorized['COPYRIGHTED'], key=lambda x: x['name']):
            print(f"  • {src['name']}")
            print(f"    Type: {src['type']} | Chunks: {src['chunks_sampled']}")
            print(f"    Sample: {src['sample'][:80]}...")
    else:
        print("  (none found in sample)")

    # UNKNOWN
    print("\n❓ UNKNOWN (needs manual review):")
    print("-" * 40)
    if categorized['UNKNOWN']:
        for src in sorted(categorized['UNKNOWN'], key=lambda x: x['name']):
            print(f"  • {src['name']}")
            print(f"    Type: {src['type']} | Chunks: {src['chunks_sampled']}")
    else:
        print("  (none found in sample)")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Public/Low Risk:    {len(categorized['PUBLIC']):3} sources")
    print(f"  Manufacturer:       {len(categorized['MANUFACTURER']):3} sources")
    print(f"  Likely Copyrighted: {len(categorized['COPYRIGHTED']):3} sources")
    print(f"  Unknown:            {len(categorized['UNKNOWN']):3} sources")
    print(f"  TOTAL:              {len(sources):3} sources")
    print("=" * 70)

    # Recommendations
    print("\nRECOMMENDATIONS:")
    if categorized['COPYRIGHTED']:
        print("  ⚠️  Review 'COPYRIGHTED' sources - consider removing")
    if categorized['UNKNOWN']:
        print("  ⚠️  Manually review 'UNKNOWN' sources to categorize")
    if categorized['MANUFACTURER']:
        print("  ℹ️  Manufacturer content is usually OK (they want distribution)")
        print("      but verify you're not violating any specific terms")

    print("\nNote: This is a sample-based audit. Run with --full for complete scan.")
    print("=" * 70 + "\n")

    return {
        'total_vectors': total_vectors,
        'sources_sampled': len(sources),
        'categories': {k: len(v) for k, v in categorized.items()}
    }


if __name__ == "__main__":
    audit_pinecone_index()
