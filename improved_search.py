import openai
from pinecone import Pinecone
import os
from dotenv import load_dotenv
import re

load_dotenv()

# Initialize APIs
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

def expand_query(question):
    """Expand query with synonyms and context to improve search"""
    
    # Add common synonyms and related terms
    expansions = {
        'rate': 'application rate dosage amount per 1000 sq ft per acre',
        'heritage': 'heritage fungicide azoxystrobin',
        'primo': 'primo maxx trinexapac-ethyl pgr plant growth regulator',
        'xzemplar': 'xzemplar fungicide fluxapyroxad',
        'dollar spot': 'dollar spot sclerotinia homoeocarpa',
        'brown patch': 'brown patch rhizoctonia',
        'pythium': 'pythium blight cottony blight',
        'bentgrass': 'creeping bentgrass agrostis stolonifera',
        'bermudagrass': 'bermudagrass cynodon dactylon',
        'tank mix': 'tank mixing compatibility co-apply',
        'grub': 'grubs white grubs scarab beetle larvae',
    }
    
    expanded = question.lower()
    for term, expansion in expansions.items():
        if term in expanded:
            expanded += f" {expansion}"
    
    return expanded

def keyword_score(text, question):
    """Score text based on keyword overlap with question"""
    question_words = set(re.findall(r'\w+', question.lower()))
    text_words = set(re.findall(r'\w+', text.lower()))
    
    # Remove common words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    question_words -= stop_words
    
    overlap = len(question_words & text_words)
    return overlap / len(question_words) if question_words else 0

def improved_query(question):
    """Improved search with query expansion and hybrid ranking"""
    
    try:
        print(f"\n{'='*70}")
        print(f"QUESTION: {question}")
        print(f"{'='*70}")
        
        # Step 1: Expand query
        expanded_query = expand_query(question)
        print(f"\nExpanded query: {expanded_query[:100]}...")
        
        # Step 2: Get embeddings
        response = openai_client.embeddings.create(
            input=expanded_query,
            model="text-embedding-3-small"
        )
        question_embedding = response.data[0].embedding
        
        # Step 3: Search Pinecone with more results
        results = index.query(
            vector=question_embedding,
            top_k=15,  # Get more results for better coverage
            include_metadata=True
        )
        
        print(f"Found {len(results['matches'])} results")
        
        # Step 4: Re-rank by combining vector similarity + keyword match
        scored_results = []
        for match in results['matches']:
            text = match['metadata'].get('text', '')
            source = match['metadata'].get('source', 'Unknown')
            
            vector_score = match['score']
            keyword_score_val = keyword_score(text, question)
            
            # Combined score (70% vector, 30% keyword)
            combined_score = (0.7 * vector_score) + (0.3 * keyword_score_val)
            
            scored_results.append({
                'text': text,
                'source': source,
                'score': combined_score,
                'vector_score': vector_score,
                'keyword_score': keyword_score_val
            })
        
        # Sort by combined score
        scored_results.sort(key=lambda x: x['score'], reverse=True)
        
        # Show top 5
        print("\nTop 5 results after re-ranking:")
        for i, result in enumerate(scored_results[:5], 1):
            print(f"{i}. {result['source'][:60]}")
            print(f"   Vector: {result['vector_score']:.3f} | Keyword: {result['keyword_score']:.3f} | Combined: {result['score']:.3f}")
        
        # Step 5: Build context from top results
        context = ""
        sources = []
        for result in scored_results[:8]:  # Use top 8 results
            context += result['text'][:1000] + "\n\n---\n\n"  # 1000 chars per result
            sources.append(result['source'])
        
        # Limit total context
        context = context[:6000]
        
        # Step 6: Generate answer with improved prompt
        gpt_response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": """You are an expert turfgrass agronomist. Answer questions using ONLY the provided context.

CRITICAL RULES:
1. Extract SPECIFIC rates (e.g., "2-4 oz per 1000 sq ft", not "use as directed")
2. Name SPECIFIC products (e.g., "Heritage at 0.4 oz", not "a fungicide")
3. If context has the info but it's vague, say "Label recommends [general guidance] - check product label for exact rate"
4. If context truly lacks info, say "Information not found in database"
5. Always cite which product/source you're using

Be precise. Superintendents need exact rates and products."""
                },
                {
                    "role": "user", 
                    "content": f"Context from database:\n\n{context}\n\nQuestion: {question}\n\nProvide a specific answer with rates and product names:"
                }
            ],
            max_tokens=350,
            temperature=0.2
        )
        
        answer = gpt_response.choices[0].message.content
        
        print(f"\nANSWER: {answer[:200]}...")
        print(f"\nTop sources: {sources[:3]}")
        
        return {
            'question': question,
            'answer': answer,
            'sources': sources[:3],
            'relevance_score': scored_results[0]['score'] if scored_results else 0
        }
        
    except Exception as e:
        print(f"ERROR: {e}")
        return {
            'question': question,
            'answer': f"ERROR: {e}",
            'sources': [],
            'relevance_score': 0
        }

# Test with a few questions
if __name__ == "__main__":
    test_questions = [
        "Heritage fungicide rate for bentgrass greens with active dollar spot",
        "Can I tank mix Primo MAXX at 6 oz with fungicides during summer stress?",
        "Xzemplar application rate for preventive dollar spot on bentgrass fairways",
        "Spoon feeding nitrogen to bentgrass greens in July - what rate per week?",
    ]
    
    for q in test_questions:
        result = improved_query(q)
        print("\n" + "="*70 + "\n")