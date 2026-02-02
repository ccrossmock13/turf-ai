"""
Knowledge Base Builder for Greenside Turf AI
Scans PDF folders, extracts text, chunks, embeds, and uploads to Pinecone.
Tracks indexed files to avoid duplicates.
"""

import os
import json
import hashlib
import time
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import PyPDF2
import openai
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
CHUNK_SIZE = 800  # Characters per chunk
CHUNK_OVERLAP = 150  # Overlap between chunks for context
MIN_CHUNK_SIZE = 200  # Minimum chunk size to keep
MAX_CHUNKS_PER_DOC = 50  # Limit chunks per document
EMBEDDING_MODEL = "text-embedding-3-small"
BATCH_SIZE = 50  # Vectors per upsert batch

# Data directory for tracking
DATA_DIR = os.environ.get('DATA_DIR', 'data' if os.path.exists('data') else '.')
INDEX_TRACKER_FILE = os.path.join(DATA_DIR, 'indexed_files.json')

# PDF source folders with their types
PDF_FOLDERS = {
    'static/product-labels': 'pesticide_label',
    'static/epa_labels': 'pesticide_label',
    'static/solution-sheets': 'solution_sheet',
    'static/spray-programs': 'spray_program',
    'static/ntep-pdfs': 'research_trial',
    'static/pdfs': 'general',
}


class IndexTracker:
    """Tracks which files have been indexed to avoid duplicates."""

    def __init__(self, tracker_file: str = INDEX_TRACKER_FILE):
        self.tracker_file = tracker_file
        self.indexed = self._load()

    def _load(self) -> Dict:
        """Load the tracking file."""
        if os.path.exists(self.tracker_file):
            try:
                with open(self.tracker_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading tracker: {e}")
        return {'files': {}, 'last_run': None, 'stats': {}}

    def _save(self):
        """Save the tracking file."""
        os.makedirs(os.path.dirname(self.tracker_file) or '.', exist_ok=True)
        with open(self.tracker_file, 'w') as f:
            json.dump(self.indexed, f, indent=2)

    def get_file_hash(self, filepath: str) -> str:
        """Get MD5 hash of file for change detection."""
        hasher = hashlib.md5()
        with open(filepath, 'rb') as f:
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()

    def is_indexed(self, filepath: str) -> bool:
        """Check if file has been indexed (and hasn't changed)."""
        if filepath not in self.indexed['files']:
            return False

        stored_hash = self.indexed['files'][filepath].get('hash')
        current_hash = self.get_file_hash(filepath)
        return stored_hash == current_hash

    def mark_indexed(self, filepath: str, chunks: int, vectors: List[str]):
        """Mark a file as indexed."""
        self.indexed['files'][filepath] = {
            'hash': self.get_file_hash(filepath),
            'indexed_at': datetime.now().isoformat(),
            'chunks': chunks,
            'vector_ids': vectors
        }
        self._save()

    def update_stats(self, stats: Dict):
        """Update run statistics."""
        self.indexed['last_run'] = datetime.now().isoformat()
        self.indexed['stats'] = stats
        self._save()

    def get_stats(self) -> Dict:
        """Get current stats."""
        total_files = len(self.indexed['files'])
        total_chunks = sum(f.get('chunks', 0) for f in self.indexed['files'].values())
        return {
            'total_files': total_files,
            'total_chunks': total_chunks,
            'last_run': self.indexed.get('last_run')
        }


def extract_text_from_pdf(filepath: str) -> Tuple[str, int]:
    """Extract text from a PDF file."""
    try:
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip(), len(reader.pages)
    except Exception as e:
        logger.error(f"Error extracting text from {filepath}: {e}")
        return "", 0


def clean_text(text: str) -> str:
    """Clean extracted text."""
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove page numbers and headers that repeat
    text = re.sub(r'Page \d+ of \d+', '', text)
    # Remove URLs (keep for metadata but not in chunks)
    text = re.sub(r'http[s]?://\S+', '', text)
    return text.strip()


def smart_chunk(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split text into chunks with overlap, trying to break at sentence boundaries.
    """
    if len(text) < chunk_size:
        return [text] if len(text) > MIN_CHUNK_SIZE else []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunk = text[start:]
            if len(chunk) > MIN_CHUNK_SIZE:
                chunks.append(chunk)
            break

        # Try to find a sentence boundary near the end
        search_start = max(start + chunk_size - 100, start)
        search_text = text[search_start:end + 50]

        # Look for sentence endings
        best_break = -1
        for pattern in ['. ', '.\n', '? ', '! ', '\n\n']:
            idx = search_text.rfind(pattern)
            if idx > best_break:
                best_break = idx

        if best_break > 0:
            end = search_start + best_break + 1

        chunk = text[start:end].strip()
        if len(chunk) > MIN_CHUNK_SIZE:
            chunks.append(chunk)

        start = end - overlap

    return chunks[:MAX_CHUNKS_PER_DOC]


def detect_document_type(filepath: str, text: str) -> str:
    """Detect the type of document based on path and content."""
    filepath_lower = filepath.lower()
    text_lower = text[:2000].lower()

    # Check folder-based type first
    for folder, doc_type in PDF_FOLDERS.items():
        if folder in filepath_lower:
            return doc_type

    # Content-based detection
    if 'label' in filepath_lower or 'epa reg' in text_lower:
        return 'pesticide_label'
    elif 'ntep' in filepath_lower or 'trial' in text_lower:
        return 'research_trial'
    elif 'spray program' in text_lower or 'agronomic' in text_lower:
        return 'spray_program'
    elif any(w in text_lower for w in ['fungicide', 'herbicide', 'insecticide']):
        return 'pesticide_product'

    return 'general'


def extract_metadata(filepath: str, text: str) -> Dict:
    """Extract rich metadata from document."""
    filename = os.path.basename(filepath)
    text_lower = text[:3000].lower()

    metadata = {
        'source': filename,
        'filepath': filepath,
    }

    # Detect grass types mentioned
    grass_types = []
    for grass in ['bentgrass', 'bermuda', 'zoysia', 'bluegrass', 'fescue', 'poa', 'paspalum', 'centipede', 'st. augustine']:
        if grass in text_lower or grass in filename.lower():
            grass_types.append(grass)
    if grass_types:
        metadata['grass_types'] = ', '.join(grass_types)

    # Detect products mentioned
    products = []
    product_list = ['heritage', 'lexicon', 'daconil', 'banner', 'primo', 'tenacity',
                    'barricade', 'dimension', 'acelepryn', 'specticle', 'monument']
    for product in product_list:
        if product in text_lower:
            products.append(product)
    if products:
        metadata['products'] = ', '.join(products)

    # Detect diseases mentioned
    diseases = []
    disease_list = ['dollar spot', 'brown patch', 'pythium', 'anthracnose',
                    'fairy ring', 'snow mold', 'gray leaf spot']
    for disease in disease_list:
        if disease in text_lower:
            diseases.append(disease)
    if diseases:
        metadata['diseases'] = ', '.join(diseases)

    # Detect regions
    regions = []
    region_patterns = ['northeast', 'southeast', 'midwest', 'southwest', 'northwest',
                       'transition zone', 'gulf coast', 'pacific']
    for region in region_patterns:
        if region in text_lower or region in filename.lower():
            regions.append(region)
    if regions:
        metadata['regions'] = ', '.join(regions)

    return metadata


def embed_texts(openai_client, texts: List[str]) -> List[List[float]]:
    """Embed multiple texts in a batch."""
    try:
        response = openai_client.embeddings.create(
            input=texts,
            model=EMBEDDING_MODEL
        )
        return [item.embedding for item in response.data]
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return []


def process_pdf(
    filepath: str,
    openai_client,
    pinecone_index,
    doc_type: str
) -> Tuple[int, List[str]]:
    """Process a single PDF and upload to Pinecone."""

    # Extract text
    text, num_pages = extract_text_from_pdf(filepath)
    if len(text) < 500:
        logger.warning(f"Skipping {filepath}: insufficient text ({len(text)} chars)")
        return 0, []

    # Clean and chunk
    text = clean_text(text)
    chunks = smart_chunk(text)

    if not chunks:
        logger.warning(f"Skipping {filepath}: no valid chunks")
        return 0, []

    logger.info(f"Processing {os.path.basename(filepath)}: {len(chunks)} chunks from {num_pages} pages")

    # Extract metadata
    base_metadata = extract_metadata(filepath, text)
    base_metadata['type'] = doc_type
    base_metadata['num_pages'] = num_pages

    # Create vector IDs
    base_id = hashlib.md5(filepath.encode()).hexdigest()[:12]
    vector_ids = []

    # Process in batches
    vectors_to_upsert = []

    for i, chunk in enumerate(chunks):
        vector_id = f"{base_id}-{i}"
        vector_ids.append(vector_id)

        # Chunk-specific metadata
        metadata = base_metadata.copy()
        metadata['text'] = chunk
        metadata['chunk_id'] = i
        metadata['total_chunks'] = len(chunks)

        vectors_to_upsert.append({
            'id': vector_id,
            'chunk': chunk,
            'metadata': metadata
        })

    # Embed and upload in batches
    uploaded = 0
    for batch_start in range(0, len(vectors_to_upsert), BATCH_SIZE):
        batch = vectors_to_upsert[batch_start:batch_start + BATCH_SIZE]

        # Get embeddings
        texts = [v['chunk'] for v in batch]
        embeddings = embed_texts(openai_client, texts)

        if not embeddings:
            continue

        # Prepare for upsert
        upsert_batch = []
        for v, embedding in zip(batch, embeddings):
            upsert_batch.append({
                'id': v['id'],
                'values': embedding,
                'metadata': v['metadata']
            })

        # Upsert to Pinecone
        try:
            pinecone_index.upsert(vectors=upsert_batch)
            uploaded += len(upsert_batch)
        except Exception as e:
            logger.error(f"Upsert error: {e}")

    return uploaded, vector_ids


def scan_for_pdfs(folders: Dict[str, str] = PDF_FOLDERS) -> List[Tuple[str, str]]:
    """Scan folders for PDF files and their types."""
    pdfs = []

    for folder, doc_type in folders.items():
        if not os.path.exists(folder):
            continue

        for root, dirs, files in os.walk(folder):
            for file in files:
                if file.lower().endswith('.pdf') and not file.startswith('.'):
                    filepath = os.path.join(root, file)
                    pdfs.append((filepath, doc_type))

    return pdfs


def build_knowledge_base(
    folders: Optional[Dict[str, str]] = None,
    force_reindex: bool = False,
    limit: Optional[int] = None
):
    """
    Main function to build/update the knowledge base.

    Args:
        folders: Dict of folder paths to document types (uses defaults if None)
        force_reindex: If True, reindex all files even if already indexed
        limit: Maximum number of new files to process (for testing)
    """
    if folders is None:
        folders = PDF_FOLDERS

    # Initialize clients
    openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index(os.getenv("PINECONE_INDEX", "turf-research"))

    # Initialize tracker
    tracker = IndexTracker()

    print("\n" + "=" * 60)
    print("GREENSIDE KNOWLEDGE BASE BUILDER")
    print("=" * 60)

    # Get current stats
    stats = tracker.get_stats()
    print(f"\nCurrent index: {stats['total_files']} files, {stats['total_chunks']} chunks")
    if stats['last_run']:
        print(f"Last run: {stats['last_run']}")

    # Scan for PDFs
    print("\nScanning for PDFs...")
    all_pdfs = scan_for_pdfs(folders)
    print(f"Found {len(all_pdfs)} PDF files")

    # Filter to unindexed files
    if force_reindex:
        to_process = all_pdfs
        print("Force reindex: processing all files")
    else:
        to_process = [(f, t) for f, t in all_pdfs if not tracker.is_indexed(f)]
        print(f"New/changed files to process: {len(to_process)}")

    if limit:
        to_process = to_process[:limit]
        print(f"Limited to {limit} files")

    if not to_process:
        print("\nNo new files to process!")
        return

    # Process files
    print("\n" + "-" * 60)
    start_time = time.time()

    total_chunks = 0
    processed = 0
    failed = []

    for i, (filepath, doc_type) in enumerate(to_process, 1):
        filename = os.path.basename(filepath)
        print(f"\n[{i}/{len(to_process)}] {filename}")

        try:
            chunks, vector_ids = process_pdf(filepath, openai_client, index, doc_type)

            if chunks > 0:
                tracker.mark_indexed(filepath, chunks, vector_ids)
                total_chunks += chunks
                processed += 1
                print(f"  ✓ Uploaded {chunks} chunks")
            else:
                print(f"  ⚠ Skipped (no content)")

        except Exception as e:
            logger.error(f"Error processing {filepath}: {e}")
            failed.append(filepath)
            print(f"  ✗ Failed: {e}")

        # Rate limiting
        time.sleep(0.1)

    # Final stats
    elapsed = time.time() - start_time

    print("\n" + "=" * 60)
    print("BUILD COMPLETE")
    print("=" * 60)
    print(f"Files processed: {processed}/{len(to_process)}")
    print(f"Chunks uploaded: {total_chunks}")
    print(f"Time elapsed: {elapsed:.1f}s")

    if failed:
        print(f"\nFailed files ({len(failed)}):")
        for f in failed:
            print(f"  - {os.path.basename(f)}")

    # Update stats
    final_stats = tracker.get_stats()
    tracker.update_stats({
        'files_processed': processed,
        'chunks_uploaded': total_chunks,
        'failed': len(failed),
        'elapsed_seconds': elapsed
    })

    print(f"\nTotal in index: {final_stats['total_files']} files, {final_stats['total_chunks']} chunks")
    print("=" * 60 + "\n")


def show_index_status():
    """Show current index status."""
    tracker = IndexTracker()
    stats = tracker.get_stats()

    print("\n" + "=" * 60)
    print("KNOWLEDGE BASE STATUS")
    print("=" * 60)
    print(f"Indexed files: {stats['total_files']}")
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Last run: {stats['last_run'] or 'Never'}")

    # Scan for new files
    all_pdfs = scan_for_pdfs()
    unindexed = [f for f, _ in all_pdfs if not tracker.is_indexed(f)]
    print(f"\nPDFs found: {len(all_pdfs)}")
    print(f"Unindexed: {len(unindexed)}")

    if unindexed[:5]:
        print("\nSample unindexed files:")
        for f in unindexed[:5]:
            print(f"  - {os.path.basename(f)}")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build Greenside Knowledge Base")
    parser.add_argument('--status', action='store_true', help='Show index status')
    parser.add_argument('--force', action='store_true', help='Force reindex all files')
    parser.add_argument('--limit', type=int, help='Limit number of files to process')

    args = parser.parse_args()

    if args.status:
        show_index_status()
    else:
        build_knowledge_base(force_reindex=args.force, limit=args.limit)
