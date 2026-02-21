"""
Fast audit script - samples the index to find sources.
"""

import os
from collections import defaultdict
from dotenv import load_dotenv
from pinecone import Pinecone
from openai import OpenAI

load_dotenv()

COPYRIGHTED_KEYWORDS = [
    'journal', 'textbook', 'book', 'chapter', 'article',
    'thesis', 'dissertation', 'hortsci', 'agronomy',
    'crop science', 'plant disease', 'weed science',
    'intl turfgrass soc'
]

PUBLIC_KEYWORDS = [
    'epa', 'usda', 'extension', '.edu', 'ntep', 'university',
    'label', 'sds', 'msds', 'specimen', 'usga', 'gcsaa'
]

MANUFACTURER_KEYWORDS = [
    'bayer', 'syngenta', 'basf', 'corteva', 'pbi gordon', 'nufarm',
    'fmc', 'quali-pro', 'primesource', 'solution sheet', 'envu'
]

SEARCH_QUERIES = [
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
]


def categorize(source: str, doc_type: str) -> str:
    s = source.lower()
    if any(k in s for k in COPYRIGHTED_KEYWORDS):
        return 'COPYRIGHTED'
    if any(k in s for k in PUBLIC_KEYWORDS) or doc_type == 'pesticide_label':
        return 'PUBLIC'
    if any(k in s for k in MANUFACTURER_KEYWORDS):
        return 'MANUFACTURER'
    return 'UNKNOWN'


def audit():
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index(os.getenv("PINECONE_INDEX", "turf-research"))
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    stats = index.describe_index_stats()
    print("\n" + "=" * 60)
    print("PINECONE INDEX AUDIT")
    print("=" * 60)
    print(f"\nTotal vectors: {stats.total_vector_count:,}")

    print("\nSampling index...")

    sources = defaultdict(lambda: {'count': 0, 'type': None, 'sample': ''})
    seen_ids = set()

    for query in SEARCH_QUERIES:
        try:
            resp = client.embeddings.create(input=query, model="text-embedding-3-small")
            results = index.query(vector=resp.data[0].embedding, top_k=100, include_metadata=True)

            for m in results.get('matches', []):
                if m['id'] in seen_ids:
                    continue
                seen_ids.add(m['id'])

                meta = m.get('metadata', {})
                src = meta.get('source', 'Unknown')
                sources[src]['count'] += 1
                sources[src]['type'] = meta.get('type', 'unknown')
                if not sources[src]['sample']:
                    sources[src]['sample'] = meta.get('text', '')[:100]

            print(f"  {query[:30]}... ({len(seen_ids)} unique)")
        except Exception as e:
            print(f"  Error: {e}")

    # Categorize
    categories = defaultdict(list)
    for src, info in sources.items():
        cat = categorize(src, info['type'])
        categories[cat].append({'name': src, 'type': info['type'], 'chunks': info['count']})

    # Display
    print("\n" + "=" * 60)

    print("\n❌ LIKELY COPYRIGHTED:")
    print("-" * 40)
    if categories['COPYRIGHTED']:
        for s in sorted(categories['COPYRIGHTED'], key=lambda x: x['name']):
            print(f"  • {s['name']}")
            print(f"    Type: {s['type']} | Chunks: {s['chunks']}")
    else:
        print("  ✓ None found!")

    print("\n❓ UNKNOWN:")
    print("-" * 40)
    if categories['UNKNOWN']:
        for s in sorted(categories['UNKNOWN'], key=lambda x: x['name']):
            print(f"  • {s['name']}")
            print(f"    Type: {s['type']} | Chunks: {s['chunks']}")
    else:
        print("  ✓ None found!")

    print("\n⚠️  MANUFACTURER:")
    print("-" * 40)
    if categories['MANUFACTURER']:
        for s in sorted(categories['MANUFACTURER'], key=lambda x: x['name']):
            print(f"  • {s['name']}")
    else:
        print("  (none)")

    print("\n✅ PUBLIC:")
    print("-" * 40)
    if categories['PUBLIC']:
        for s in sorted(categories['PUBLIC'], key=lambda x: x['name']):
            print(f"  • {s['name']}")
    else:
        print("  (none)")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  ❌ Copyrighted:  {len(categories['COPYRIGHTED']):3} sources")
    print(f"  ❓ Unknown:      {len(categories['UNKNOWN']):3} sources")
    print(f"  ⚠️  Manufacturer: {len(categories['MANUFACTURER']):3} sources")
    print(f"  ✅ Public:       {len(categories['PUBLIC']):3} sources")
    print(f"  TOTAL SAMPLED:  {len(sources):3} sources")
    print("=" * 60)

    if categories['COPYRIGHTED']:
        print("\n⚠️  Run: python cleanup_copyrighted.py")
    print("")


if __name__ == "__main__":
    audit()
