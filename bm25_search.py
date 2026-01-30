"""
BM25 keyword search implementation for hybrid retrieval.
Combines with vector search for better recall on exact keyword matches.
"""
import re
import math
from collections import Counter
from typing import List, Dict, Tuple


class BM25:
    """
    BM25 (Best Matching 25) ranking function for keyword search.
    Provides TF-IDF-like scoring that handles term frequency saturation.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 with tuning parameters.

        Args:
            k1: Term frequency saturation parameter (1.2-2.0 typical)
            b: Document length normalization (0.75 typical)
        """
        self.k1 = k1
        self.b = b
        self.corpus = []
        self.doc_freqs = Counter()
        self.doc_lengths = []
        self.avg_doc_length = 0
        self.n_docs = 0
        self.idf_cache = {}

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into lowercase words."""
        return re.findall(r'\b\w+\b', text.lower())

    def fit(self, documents: List[str]):
        """
        Fit BM25 on a corpus of documents.

        Args:
            documents: List of document texts
        """
        self.corpus = []
        self.doc_freqs = Counter()
        self.doc_lengths = []
        self.idf_cache = {}

        for doc in documents:
            tokens = self._tokenize(doc)
            self.corpus.append(tokens)
            self.doc_lengths.append(len(tokens))

            # Count document frequency (unique terms per doc)
            unique_terms = set(tokens)
            for term in unique_terms:
                self.doc_freqs[term] += 1

        self.n_docs = len(documents)
        self.avg_doc_length = sum(self.doc_lengths) / self.n_docs if self.n_docs > 0 else 0

        # Pre-compute IDF for all terms
        for term, df in self.doc_freqs.items():
            self.idf_cache[term] = self._compute_idf(df)

    def _compute_idf(self, doc_freq: int) -> float:
        """Compute IDF with smoothing."""
        return math.log((self.n_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1)

    def get_idf(self, term: str) -> float:
        """Get IDF for a term."""
        return self.idf_cache.get(term, self._compute_idf(0))

    def score(self, query: str, doc_index: int) -> float:
        """
        Score a document against a query.

        Args:
            query: Query string
            doc_index: Index of document in corpus

        Returns:
            BM25 score
        """
        query_terms = self._tokenize(query)
        doc_tokens = self.corpus[doc_index]
        doc_length = self.doc_lengths[doc_index]

        # Term frequency in document
        tf_doc = Counter(doc_tokens)

        score = 0.0
        for term in query_terms:
            if term not in tf_doc:
                continue

            tf = tf_doc[term]
            idf = self.get_idf(term)

            # BM25 formula
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * (doc_length / self.avg_doc_length))
            score += idf * (numerator / denominator)

        return score

    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """
        Search corpus and return top-k results.

        Args:
            query: Query string
            top_k: Number of results to return

        Returns:
            List of (doc_index, score) tuples sorted by score descending
        """
        scores = [(i, self.score(query, i)) for i in range(self.n_docs)]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class HybridSearcher:
    """
    Combines vector search results with BM25 keyword search.
    Uses reciprocal rank fusion to merge result lists.
    """

    def __init__(self, alpha: float = 0.5, rrf_k: int = 60):
        """
        Initialize hybrid searcher.

        Args:
            alpha: Weight for vector search (1-alpha for BM25)
            rrf_k: RRF constant (higher = more uniform blending)
        """
        self.alpha = alpha
        self.rrf_k = rrf_k
        self.bm25 = BM25()
        self.doc_id_to_index = {}
        self.index_to_doc_id = {}

    def index_documents(self, documents: List[Dict]):
        """
        Index documents for BM25 search.

        Args:
            documents: List of dicts with 'id' and 'text' keys
        """
        texts = []
        self.doc_id_to_index = {}
        self.index_to_doc_id = {}

        for i, doc in enumerate(documents):
            doc_id = doc.get('id', str(i))
            text = doc.get('text', '')
            texts.append(text)
            self.doc_id_to_index[doc_id] = i
            self.index_to_doc_id[i] = doc_id

        self.bm25.fit(texts)

    def reciprocal_rank_fusion(
        self,
        vector_results: List[Dict],
        bm25_results: List[Tuple[int, float]]
    ) -> List[Dict]:
        """
        Merge vector and BM25 results using Reciprocal Rank Fusion.

        Args:
            vector_results: Vector search results with 'id' and 'score'
            bm25_results: BM25 results as (index, score) tuples

        Returns:
            Merged results sorted by RRF score
        """
        rrf_scores = {}

        # Score vector results
        for rank, result in enumerate(vector_results, 1):
            doc_id = result.get('id', '')
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + self.alpha / (self.rrf_k + rank)

        # Score BM25 results
        for rank, (index, _) in enumerate(bm25_results, 1):
            doc_id = self.index_to_doc_id.get(index, '')
            if doc_id:
                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + (1 - self.alpha) / (self.rrf_k + rank)

        # Build merged results
        id_to_result = {r.get('id'): r for r in vector_results}
        merged = []

        for doc_id, rrf_score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
            if doc_id in id_to_result:
                result = id_to_result[doc_id].copy()
                result['rrf_score'] = rrf_score
                merged.append(result)

        return merged

    def search(
        self,
        query: str,
        vector_results: List[Dict],
        top_k: int = 30
    ) -> List[Dict]:
        """
        Perform hybrid search combining vector and BM25 results.

        Args:
            query: Search query
            vector_results: Results from vector search
            top_k: Number of results to return

        Returns:
            Merged and reranked results
        """
        # Get BM25 results
        bm25_results = self.bm25.search(query, top_k=top_k)

        # Merge with RRF
        merged = self.reciprocal_rank_fusion(vector_results, bm25_results)

        return merged[:top_k]


# Global hybrid searcher instance
_hybrid_searcher = None


def get_hybrid_searcher() -> HybridSearcher:
    """Get or create global hybrid searcher."""
    global _hybrid_searcher
    if _hybrid_searcher is None:
        _hybrid_searcher = HybridSearcher(alpha=0.6)  # Slightly favor vector search
    return _hybrid_searcher


def rerank_with_bm25(query: str, vector_results: List[Dict], top_k: int = 30) -> List[Dict]:
    """
    Rerank vector search results using BM25 hybrid scoring.

    Args:
        query: Original search query
        vector_results: Results from vector search (Pinecone matches)
        top_k: Number of results to return

    Returns:
        Reranked results combining vector and keyword relevance
    """
    if not vector_results:
        return []

    searcher = get_hybrid_searcher()

    # Extract documents for BM25 indexing
    documents = []
    for match in vector_results:
        if match is None:
            continue
        doc_id = match.get('id', '') if hasattr(match, 'get') else str(match)
        metadata = match.get('metadata', {}) if hasattr(match, 'get') else {}
        text = metadata.get('text', '') if hasattr(metadata, 'get') else ''
        source = metadata.get('source', '') if hasattr(metadata, 'get') else ''
        # Include source name in searchable text
        combined_text = f"{source} {text}"
        documents.append({'id': doc_id, 'text': combined_text})

    # Index and search
    searcher.index_documents(documents)

    # Convert to format expected by hybrid searcher
    formatted_results = []
    for m in vector_results:
        if m is None:
            continue
        result = {
            'id': m.get('id', '') if hasattr(m, 'get') else '',
            'score': m.get('score', 0) if hasattr(m, 'get') else 0,
            'metadata': m.get('metadata', {}) if hasattr(m, 'get') else {}
        }
        formatted_results.append(result)

    return searcher.search(query, formatted_results, top_k=top_k)
