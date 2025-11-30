import openai
from pinecone import Pinecone
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Initialize APIs
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("turf-research")

print("TURF AI ACCURACY TESTING\n")
print("Testing AI with 50 real superintendent questions\n")

# Real specific questions superintendents actually ask
TEST_QUESTIONS = [
    # Product/Rate Questions - SPECIFIC
    "Heritage fungicide rate for bentgrass greens with active dollar spot",
    "Can I tank mix Primo MAXX at 6 oz with fungicides during summer stress?",
    "Xzemplar application rate for preventive dollar spot on bentgrass fairways",
    "Spoon feeding nitrogen to bentgrass greens in July - what rate per week?",
    "Tenacity rate for killing Poa trivialis in tall fescue without injury",
    
    # Disease Questions - SPECIFIC
    "Dollar spot on greens won't go away after 3 Heritage applications, what should I rotate to?",
    "Anthracnose on Poa greens during heat stress, what's the best fungicide program?",
    "Type 2 fairy ring causing dead circles on fairways, what combination of products works?",
    "Brown patch on tall fescue roughs spreading fast, curative fungicide options?",
    "Pythium cottony blight outbreak on bentgrass greens after heavy rain, emergency treatment?",
    
    # Equipment/Irrigation - SPECIFIC
    "Rain Bird 5004 rotor pops up but won't retract, is it the wiper seal or spring?",
    "Toro Greensmaster 3150 cutting quality declining, when should I backlap vs grind?",
    "Fairway 12 has dry spots on north end only, controller shows full cycle time - what to check?",
    "John Deere 2500E greens mower hydraulic fluid is dark, how often should I change it?",
    "Hunter ICV valve sticking open intermittently, solenoid or diaphragm problem?",
    
    # Cultural Practices - SPECIFIC
    "Best month to core aerify bentgrass greens in transition zone without disrupting play?",
    "Overseeding bermudagrass fairways with perennial ryegrass in October, what seeding rate?",
    "Verticutting depth before overseeding dormant bermudagrass - 1/8 inch or deeper?",
    "How much sand per 1000 sq ft for light topdressing on bentgrass greens monthly?",
    "Apply Dimension pre-emergent for Poa annua control - late August or early September?",
    
    # Fertility - SPECIFIC
    "Bermudagrass fairways looking light green in June, is 0.5 lb N per 1000 enough?",
    "Foliar feeding bentgrass greens under heat stress with quick release nitrogen - safe rate?",
    "Should I apply potassium in October or November for winter hardiness on bentgrass?",
    "Greens are yellow but soil test shows adequate nitrogen, foliar iron rate for quick color?",
    "White tissue on new leaf tips of bentgrass, is this calcium deficiency?",
    
    # Weeds - SPECIFIC
    "Yellow nutsedge in bermudagrass rough getting worse, Monument or Dismiss better option?",
    "Pre-emergent timing for crabgrass in Kentucky - soil temp at 50 or 55 degrees?",
    "Poa trivialis invasion in bentgrass fairways, can Tenacity kill it selectively?",
    "Dollarweed in St. Augustine rough, post-emergent that won't hurt the grass?",
    "Goosegrass breakthrough in July after spring pre-emergent, what post-emergent works in heat?",
    
    # Stress Management - SPECIFIC
    "Bentgrass greens wilting at 2pm in 95 degree heat, what rate of syringing helps?",
    "Hydrophobic dry spots on greens after dry spell, which wetting agent works fastest?",
    "Fairway wear from cart traffic on slopes, should I use a root stimulator product?",
    "Bentgrass greens showing signs of heat stress during tournament week, immediate relief options?",
    "Exposed greens getting winter desiccation, should I cover them or apply an anti-transpirant?",
    
    # Insects - SPECIFIC
    "Grub damage appearing on fairways in August, is it too late for preventive control?",
    "Armyworms eating fairways overnight, what insecticide gives fastest knockdown?",
    "Annual bluegrass weevil larvae feeding on collars in May, Acelepryn or Merit?",
    "Chinch bugs killing St. Augustine in full sun areas, best curative insecticide?",
    "Mole crickets tunneling bermudagrass greens at night, fall or spring treatment better?",
    
    # Soil/Drainage - SPECIFIC  
    "Greens 3 and 8 stay wet after rain, can I improve drainage without reconstruction?",
    "Soil test shows pH 5.2 on bentgrass greens, how much lime per 1000 sq ft to raise to 6.5?",
    "Compaction on high traffic tees reading 350 PSI, solid tine or core aerification?",
    "High sodium levels causing black layer in greens, gypsum application rate and timing?",
    "Should I topdress bentgrass greens every 2 weeks or every month during growing season?",
    
    # Seasonal - SPECIFIC
    "Bermudagrass spring transition program - what nitrogen rate for fast greenup in April?",
    "Transitioning from summer to fall on bentgrass, when to increase nitrogen applications?",
    "Covering greens for winter protection in USDA zone 6, plastic or permeable covers?",
    "Summer fungicide rotation for bentgrass greens - Heritage, Lexicon, Xzemplar every 14 days?",
    "Member-guest tournament in 5 days, what's the best quick-fix for greens speed and color?",
]

def query_ai(question):
    """Query the AI system and get response"""
    try:
        # Get embeddings for question
        response = openai_client.embeddings.create(
            input=question,
            model="text-embedding-3-small"
        )
        question_embedding = response.data[0].embedding
        
        # Search Pinecone
        results = index.query(
            vector=question_embedding,
            top_k=5,
            include_metadata=True
        )
        
        # Build context from results (limit to prevent token overflow)
        context = ""
        sources = []
        for match in results['matches']:
            chunk_text = match['metadata'].get('text', '')
            # Limit each chunk to 800 chars to prevent overflow
            context += chunk_text[:800] + "\n\n"
            sources.append(match['metadata'].get('source', 'Unknown'))
        
        # Limit total context to 3000 chars
        context = context[:3000]
        
        # Generate answer with GPT-3.5-turbo (cheaper, faster)
        gpt_response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert turfgrass agronomist. Answer questions based ONLY on the provided context. Be specific with rates, timing, and products. Always cite which product/source you're referencing. If context lacks info, say 'Information not found in database'."},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer (include product names and rates):"}
            ],
            max_tokens=300,
            temperature=0.3
        )
        
        answer = gpt_response.choices[0].message.content
        
        return {
            'question': question,
            'answer': answer,
            'sources': sources[:3],  # Top 3 sources
            'relevance_score': results['matches'][0]['score'] if results['matches'] else 0
        }
        
    except Exception as e:
        return {
            'question': question,
            'answer': f"ERROR: {e}",
            'sources': [],
            'relevance_score': 0
        }

# Run tests
print("="*70)
print("RUNNING TESTS")
print("="*70 + "\n")

results = []
for i, question in enumerate(TEST_QUESTIONS, 1):
    print(f"[{i}/{len(TEST_QUESTIONS)}] {question}")
    result = query_ai(question)
    results.append(result)
    
    # Show answer preview
    answer_preview = result['answer'][:150] + "..." if len(result['answer']) > 150 else result['answer']
    print(f"  Answer: {answer_preview}")
    print(f"  Relevance: {result['relevance_score']:.3f}")
    print()

# Save results to file
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = f"ai_test_results_{timestamp}.txt"

with open(output_file, 'w') as f:
    f.write("TURF AI ACCURACY TEST RESULTS\n")
    f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"Questions tested: {len(TEST_QUESTIONS)}\n")
    f.write("="*70 + "\n\n")
    
    for i, result in enumerate(results, 1):
        f.write(f"QUESTION {i}:\n{result['question']}\n\n")
        f.write(f"ANSWER:\n{result['answer']}\n\n")
        f.write(f"SOURCES: {', '.join(result['sources'])}\n")
        f.write(f"RELEVANCE SCORE: {result['relevance_score']:.3f}\n")
        f.write("-"*70 + "\n\n")

print("="*70)
print("TEST COMPLETE")
print("="*70)
print(f"\nResults saved to: {output_file}")
print("\nREVIEW THE RESULTS:")
print("1. Look for questions with low relevance scores (<0.7)")
print("2. Check if answers are specific enough (rates, products, timing)")
print("3. Identify missing info (gaps in your database)")
print("4. Note any hallucinations or wrong info")
print("\nThen we'll fix the issues!")