from flask import Flask, render_template, request, jsonify, send_from_directory
import openai
from pinecone import Pinecone
import os
from dotenv import load_dotenv
import re

load_dotenv()

app = Flask(__name__)

# Initialize
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
        'lexicon': 'lexicon intrinsic fluxapyroxad',
        'dedicate': 'dedicate stressgard azoxystrobin',
        'tenacity': 'tenacity herbicide mesotrione',
        'drive': 'drive xlr8 herbicide quinclorac',
        'monument': 'monument herbicide trifloxysulfuron',
        'dollar spot': 'dollar spot sclerotinia homoeocarpa clarireedia',
        'brown patch': 'brown patch rhizoctonia solani',
        'pythium': 'pythium blight cottony blight',
        'anthracnose': 'anthracnose colletotrichum',
        'fairy ring': 'fairy ring basidiomycete fungi',
        'bentgrass': 'creeping bentgrass agrostis stolonifera',
        'bermudagrass': 'bermudagrass cynodon dactylon',
        'poa': 'poa annua annual bluegrass',
        'tank mix': 'tank mixing compatibility co-apply',
        'grub': 'grubs white grubs scarab beetle larvae',
        'aerify': 'aerification aeration core aerify',
        'topdress': 'topdressing sand application',
        'overseed': 'overseeding interseeding',
    }
    
    expanded = question.lower()
    for term, expansion in expansions.items():
        if term in expanded:
            expanded += f" {expansion}"
    
    return expanded

def expand_vague_question(question):
    """Expand vague questions to be more specific and searchable"""
    question_lower = question.lower().strip()
    
    # If question is already detailed (>50 chars), don't change it
    if len(question) > 50:
        return question
    
    # Pattern: Just a disease name
    diseases = {
        'dollar spot': 'What fungicide should I use to control dollar spot? Include rates and timing.',
        'brown patch': 'What fungicide should I use to control brown patch? Include rates and timing.',
        'pythium': 'What fungicide should I use to control pythium blight? Include rates and timing.',
        'summer patch': 'What fungicide should I use to control summer patch? Include rates and timing.',
        'anthracnose': 'What fungicide should I use to control anthracnose? Include rates and timing.',
        'fairy ring': 'How do I control fairy ring? Include both cultural and chemical options.',
        'snow mold': 'What fungicide should I use to prevent snow mold? Include application timing.',
        'rust': 'What fungicide should I use to control rust? Include rates.',
        'take-all': 'How do I manage take-all patch? Include cultural and chemical approaches.',
    }
    
    for disease, expanded in diseases.items():
        if question_lower == disease or question_lower == f"{disease}?":
            return expanded
    
    # Pattern: Just a weed name
    weeds = {
        'crabgrass': 'What pre-emergent herbicide should I use for crabgrass control? Include timing and rates.',
        'poa': 'How do I control Poa annua? Include both pre and post-emergent options.',
        'poa annua': 'How do I control Poa annua? Include both pre and post-emergent options.',
        'goosegrass': 'What herbicide should I use for goosegrass? Include timing and rates.',
        'nutsedge': 'What herbicide works for nutsedge? Include rates and timing.',
        'clover': 'What herbicide should I use for clover in turf?',
        'dandelion': 'What post-emergent herbicide for dandelions?',
    }
    
    for weed, expanded in weeds.items():
        if question_lower == weed or question_lower == f"{weed}?":
            return expanded
    
    # Pattern: Just "help" or very vague
    if question_lower in ['help', 'help?', 'what spray', 'what to use', 'what do i do']:
        return "I need help with a turf problem. What information do you need from me to give a recommendation?"
    
    # Pattern: Just product name (looking for rate)
    products = ['heritage', 'lexicon', 'xzemplar', 'primo', 'tenacity', 'monument', 'barricade']
    for product in products:
        if question_lower == product or question_lower == f"{product}?":
            return f"What is the application rate for {product.title()}? Include target pest and turf type."
    
    # Pattern: "sick turf" or "turf dying"
    sick_patterns = ['sick', 'dying', 'dead', 'brown', 'yellow', 'thin', 'weak']
    if any(pattern in question_lower for pattern in sick_patterns) and len(question) < 30:
        return f"My turf shows these symptoms: {question}. Help me diagnose the problem and recommend treatment."
    
    # If nothing matched, return original
    return question

def detect_grass_type(question):
    """Detect grass type from question"""
    question_lower = question.lower()
    
    grass_types = {
        'bentgrass': ['bentgrass', 'bent grass', 'agrostis', 'creeping bent'],
        'bermudagrass': ['bermudagrass', 'bermuda', 'cynodon'],
        'poa annua': ['poa', 'poa annua', 'annual bluegrass'],
        'kentucky bluegrass': ['kentucky bluegrass', 'kbg', 'poa pratensis'],
        'tall fescue': ['tall fescue', 'fescue'],
        'perennial ryegrass': ['perennial ryegrass', 'ryegrass', 'rye grass'],
        'zoysiagrass': ['zoysiagrass', 'zoysia'],
    }
    
    for grass_type, keywords in grass_types.items():
        if any(keyword in question_lower for keyword in keywords):
            return grass_type
    
    return None

def detect_region(question):
    """Detect region/state from question"""
    question_lower = question.lower()
    
    # Map states to regions
    regions = {
        'northeast': ['massachusetts', 'connecticut', 'rhode island', 'vermont', 'new hampshire', 'maine', 'new york', 'pennsylvania', 'new jersey'],
        'southeast': ['florida', 'georgia', 'alabama', 'south carolina', 'north carolina', 'virginia', 'tennessee'],
        'midwest': ['illinois', 'indiana', 'ohio', 'michigan', 'wisconsin', 'minnesota', 'iowa'],
        'southwest': ['texas', 'oklahoma', 'arizona', 'new mexico'],
        'west': ['california', 'oregon', 'washington', 'nevada', 'colorado'],
    }
    
    for region, states in regions.items():
        if any(state in question_lower for state in states):
            return region
    
    return None

def detect_product_need(question):
    """Detect what type of product is needed based on question"""
    question_lower = question.lower()
    
    # Disease keywords = need fungicide
    disease_keywords = ['dollar spot', 'brown patch', 'pythium', 'anthracnose', 'fairy ring', 
                       'summer patch', 'fusarium', 'snow mold', 'rust', 'leaf spot', 
                       'take-all', 'spring dead spot', 'disease', 'fungicide', 'gray leaf spot',
                       'red thread', 'pink patch', 'microdochium', 'typhula']
    
    # Weed keywords = need herbicide
    weed_keywords = ['weed', 'crabgrass', 'poa', 'goosegrass', 'sedge', 'clover', 
                    'dandelion', 'herbicide', 'pre-emergent', 'post-emergent']
    
    # Insect keywords = need insecticide
    insect_keywords = ['grub', 'armyworm', 'cutworm', 'billbug', 'mole cricket', 
                      'chinch bug', 'insect', 'insecticide', 'pest']
    
    # Growth regulation keywords = need PGR
    pgr_keywords = ['growth', 'pgr', 'primo', 'reduce mowing', 'plant growth regulator']
    
    if any(keyword in question_lower for keyword in disease_keywords):
        return 'fungicide'
    elif any(keyword in question_lower for keyword in weed_keywords):
        return 'herbicide'
    elif any(keyword in question_lower for keyword in insect_keywords):
        return 'insecticide'
    elif any(keyword in question_lower for keyword in pgr_keywords):
        return 'pgr'
    
    return None

def keyword_score(text, question):
    """Score text based on keyword overlap with question"""
    question_words = set(re.findall(r'\w+', question.lower()))
    text_words = set(re.findall(r'\w+', text.lower()))
    
    # Remove common words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'what', 'how', 'when', 'where'}
    question_words -= stop_words
    
    overlap = len(question_words & text_words)
    return overlap / len(question_words) if question_words else 0

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory('static/images', filename)

@app.route('/pdfs/<path:filename>')
def serve_pdf(filename):
    return send_from_directory('static/pdfs', filename)

@app.route('/labels/<path:filename>')
def serve_label(filename):
    return send_from_directory('static/labels', filename)

@app.route('/epa_labels/<path:filename>')
def serve_epa_label(filename):
    return send_from_directory('static/epa_labels', filename)

@app.route('/product-labels/<path:filename>')
def serve_product_label(filename):
    return send_from_directory('static/product-labels', filename)

@app.route('/solution-sheets/<path:filename>')
def serve_solution_sheet(filename):
    return send_from_directory('static/solution-sheets', filename)

@app.route('/programs/<path:filename>')
def serve_program(filename):
    return send_from_directory('static/programs', filename)

@app.route('/spray-programs/<path:filename>')
def serve_spray_program(filename):
    return send_from_directory('static/spray-programs', filename)

@app.route('/ntep-pdfs/<path:filename>')
def serve_ntep(filename):
    return send_from_directory('static/ntep-pdfs', filename)

@app.route('/industry-resources/<path:filename>')
def serve_industry(filename):
    return send_from_directory('static/industry-resources', filename)

@app.route('/state-bmps/<path:filename>')
def serve_state_bmp(filename):
    return send_from_directory('static/state-bmps', filename)

@app.route('/static/<path:subpath>/<path:filename>')
def serve_static_generic(subpath, filename):
    """Generic route to serve any file from static subfolders"""
    return send_from_directory(f'static/{subpath}', filename)

@app.route('/resources')
def resources():
    return render_template('resources.html')

@app.route('/api/resources')
def get_resources():
    resources = []
    
    # Map folder name to display category
    folders = {
        'product-labels': 'Product Labels',
        'epa_labels': 'Product Labels',
        'solution-sheets': 'Solution Sheets',
        'spray-programs': 'Spray Programs',
        'state-bmps': 'State BMPs',
        'ntep-pdfs': 'NTEP Trials'
    }
    
    try:
        for folder, category in folders.items():
            folder_path = f'static/{folder}'
            if os.path.exists(folder_path):
                # Walk through folder and subfolders
                for root, dirs, files in os.walk(folder_path):
                    for filename in files:
                        if filename.lower().endswith('.pdf') and not filename.startswith('.'):
                            # Get relative path from static folder
                            full_path = os.path.join(root, filename)
                            relative_path = full_path.replace('static/', '')
                            
                            resources.append({
                                'filename': filename,
                                'url': f'/static/{relative_path}',
                                'category': category
                            })
        
        # Sort alphabetically
        resources.sort(key=lambda x: x['filename'])
        
    except Exception as e:
        print(f"Error reading PDF folders: {e}")
        return jsonify({'error': str(e)}), 500
    
    return jsonify(resources)

@app.route('/ask', methods=['POST'])
def ask():
    question = request.json['question']
    
    # EXPAND VAGUE QUESTIONS BEFORE PROCESSING
    question = expand_vague_question(question)
    
    # Step 1: Detect grass type, region, and product need
    grass_type = detect_grass_type(question)
    region = detect_region(question)
    product_need = detect_product_need(question)  # fungicide, herbicide, insecticide, or pgr
    
    # DETECT SPECIFIC STATE in question for direct BMP injection
    question_lower = question.lower()
    us_states = [
        'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado', 'connecticut',
        'delaware', 'florida', 'georgia', 'hawaii', 'idaho', 'illinois', 'indiana', 'iowa',
        'kansas', 'kentucky', 'louisiana', 'maine', 'maryland', 'massachusetts', 'michigan',
        'minnesota', 'mississippi', 'missouri', 'montana', 'nebraska', 'nevada', 'new hampshire',
        'new jersey', 'new mexico', 'new york', 'north carolina', 'north dakota', 'ohio',
        'oklahoma', 'oregon', 'pennsylvania', 'rhode island', 'south carolina', 'south dakota',
        'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington', 'west virginia',
        'wisconsin', 'wyoming'
    ]
    
    detected_state = None
    for state in us_states:
        if state in question_lower:
            detected_state = state.title()  # Capitalize: "texas" -> "Texas"
            break
    
    # Step 2: MULTI-PASS SEARCH STRATEGY
    
    # PASS 1: General search - understand the problem/disease
    expanded_query_1 = expand_query(question)
    if grass_type:
        expanded_query_1 += f" {grass_type}"
    if region:
        expanded_query_1 += f" {region}"
    
    response_1 = openai_client.embeddings.create(
        input=expanded_query_1,
        model="text-embedding-3-small"
    )
    
    general_results = index.query(
        vector=response_1.data[0].embedding,
        top_k=30,  # Increased depth
        include_metadata=True
    )
    
    # PASS 2: Product-specific search (if question is about treatment/products)
    product_results = []
    if any(word in question.lower() for word in ['spray', 'apply', 'fungicide', 'herbicide', 'insecticide', 'control', 'treat', 'product']):
        product_query = f"{question} product label application rate"
        
        response_2 = openai_client.embeddings.create(
            input=product_query,
            model="text-embedding-3-small"
        )
        
        # STRICT FILTERING: If disease question, ONLY search fungicides
        search_filter = {"type": {"$in": ["pesticide_label", "pesticide_product"]}}
        
        if product_need == 'fungicide':
            # Disease question - EXCLUDE all herbicides and insecticides
            product_results = index.query(
                vector=response_2.data[0].embedding,
                top_k=50,  # Get more, we'll filter heavily
                filter=search_filter,
                include_metadata=True
            )
            # Post-filter to remove herbicides/insecticides by name
            herbicide_names = ['specticle', 'tenacity', 'monument', 'certainty', 'sedgehammer', 
                             'drive', 'barricade', 'dimension', 'prodiamine', 'pendimethalin',
                             'acclaim', 'revolver', 'dismiss', 'tribute', 'tower', 'katana',
                             'kerb', 'gallery', 'surflan', 'ronstar', 'oryzalin', 'poacure']
            insecticide_names = ['acelepryn', 'merit', 'arena', 'allectus', 'meridian']
            
            filtered_matches = []
            for match in product_results['matches']:
                source = match['metadata'].get('source', '').lower()
                text = match['metadata'].get('text', '').lower()
                
                # Skip if it's a known herbicide or insecticide
                is_herbicide = any(herb in source or herb in text[:200] for herb in herbicide_names)
                is_insecticide = any(ins in source or ins in text[:200] for ins in insecticide_names)
                
                if not is_herbicide and not is_insecticide:
                    filtered_matches.append(match)
            
            product_results = {'matches': filtered_matches[:30]}
            
        elif product_need == 'herbicide':
            # Weed question - EXCLUDE fungicides
            product_results = index.query(
                vector=response_2.data[0].embedding,
                top_k=50,
                filter=search_filter,
                include_metadata=True
            )
            # Post-filter to remove fungicides
            fungicide_names = ['heritage', 'lexicon', 'xzemplar', 'headway', 'renown', 'medallion',
                             'interface', 'tartan', 'banner', 'bayleton', 'tourney', 'compass']
            
            filtered_matches = []
            for match in product_results['matches']:
                source = match['metadata'].get('source', '').lower()
                is_fungicide = any(fung in source for fung in fungicide_names)
                
                if not is_fungicide:
                    filtered_matches.append(match)
            
            product_results = {'matches': filtered_matches[:30]}
            
        else:
            # General product search
            product_results = index.query(
                vector=response_2.data[0].embedding,
                top_k=30,
                filter=search_filter,
                include_metadata=True
            )
    
    # PASS 3: Best practices/timing search
    timing_results = []
    if any(word in question.lower() for word in ['when', 'timing', 'schedule', 'program', 'month']):
        timing_query = f"{question} timing schedule calendar program"
        if grass_type:
            timing_query += f" {grass_type}"
        
        response_3 = openai_client.embeddings.create(
            input=timing_query,
            model="text-embedding-3-small"
        )
        
        timing_results = index.query(
            vector=response_3.data[0].embedding,
            top_k=20,
            include_metadata=True
        )
    
    # COMBINE ALL RESULTS
    all_results = []
    seen_ids = set()
    
    # AUTO-INJECT STATE BMP if state detected in question
    if detected_state:
        state_bmp_query = f"{detected_state} Bmp best management practices"
        bmp_response = openai_client.embeddings.create(
            input=state_bmp_query,
            model="text-embedding-3-small"
        )
        
        state_bmp_results = index.query(
            vector=bmp_response.data[0].embedding,
            top_k=5,
            include_metadata=True
        )
        
        # Add state BMP results as supporting context (not primary)
        for match in state_bmp_results['matches']:
            source = match['metadata'].get('source', '')
            # Case-insensitive check: "Texas Bmp" should match detected_state="Texas"
            if detected_state.lower() in source.lower() and 'bmp' in source.lower():
                all_results.append(match)
                seen_ids.add(match['id'])
    
    for match in general_results['matches']:
        if match['id'] not in seen_ids:
            all_results.append(match)
            seen_ids.add(match['id'])
    
    if product_results:
        for match in product_results['matches']:
            if match['id'] not in seen_ids:
                all_results.append(match)
                seen_ids.add(match['id'])
    
    if timing_results:
        for match in timing_results['matches']:
            if match['id'] not in seen_ids:
                all_results.append(match)
                seen_ids.add(match['id'])
    
    # Step 3: Score and filter combined results
    scored_results = []
    for match in all_results:
        text = match['metadata'].get('text', '')
        source = match['metadata'].get('source', 'Unknown')
        metadata = match['metadata']
        
        vector_score = match['score']
        keyword_score_val = keyword_score(text, question)
        
        # Combined score (70% vector, 30% keyword)
        combined_score = (0.7 * vector_score) + (0.3 * keyword_score_val)
        
        # BOOST if grass type matches
        if grass_type:
            text_lower = text.lower()
            source_lower = source.lower()
            doc_name = (metadata.get('document_name') or '').lower()
            
            if grass_type.lower() in text_lower or grass_type.lower() in source_lower or grass_type.lower() in doc_name:
                combined_score *= 1.3  # 30% boost for matching grass type
        
        # MASSIVE BOOST for state-specific BMPs
        question_lower = question.lower()
        source_lower = source.lower()
        
        us_states = [
            'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado', 'connecticut',
            'delaware', 'florida', 'georgia', 'hawaii', 'idaho', 'illinois', 'indiana', 'iowa',
            'kansas', 'kentucky', 'louisiana', 'maine', 'maryland', 'massachusetts', 'michigan',
            'minnesota', 'mississippi', 'missouri', 'montana', 'nebraska', 'nevada', 'new hampshire',
            'new jersey', 'new mexico', 'new york', 'north carolina', 'north dakota', 'ohio',
            'oklahoma', 'oregon', 'pennsylvania', 'rhode island', 'south carolina', 'south dakota',
            'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington', 'west virginia',
            'wisconsin', 'wyoming'
        ]
        
        # Check if question mentions a specific state
        for state in us_states:
            if state in question_lower:
                # If this source is that state's BMP, moderate boost (context, not primary)
                if state in source_lower and 'bmp' in source_lower:
                    combined_score *= 2.0  # 2x boost - enough to include but not dominate
                    break
                # If this source mentions the state (but isn't BMP), smaller boost
                elif state in source_lower or state in text.lower()[:500]:
                    combined_score *= 1.3  # 30% boost for state-relevant content
                    break
        
        # BOOST if region matches (keep existing logic)
        if region:
            text_lower = text.lower()
            source_lower = source.lower()
            
            if region in text_lower or region in source_lower:
                combined_score *= 1.2  # 20% boost for matching region
        
        # PENALIZE if wrong grass type detected
        if grass_type:
            wrong_grasses = ['bentgrass', 'bermudagrass', 'poa annua', 'kentucky bluegrass', 'zoysiagrass']
            wrong_grasses.remove(grass_type) if grass_type in wrong_grasses else None
            
            for wrong_grass in wrong_grasses:
                if wrong_grass in text.lower()[:200]:  # Check first 200 chars
                    combined_score *= 0.5  # Heavy penalty for wrong grass type
                    break
        
        # FILTER OUT Canada-only products (assume USA users)
        product_country = metadata.get('country', 'USA')
        if product_country == 'Canada':
            combined_score *= 0.1  # Heavy penalty for Canada-only products
        
        # HEAVILY PENALIZE wrong product type by checking known products
        if product_need:
            text_lower = text.lower()
            source_lower = source.lower()
            
            # Known herbicides (NOT for disease control)
            herbicides = ['specticle', 'tenacity', 'monument', 'certainty', 'sedgehammer', 
                         'drive', 'barricade', 'dimension', 'prodiamine', 'pendimethalin',
                         'acclaim', 'revolver', 'dismiss', 'tribute', 'tower', 'katana',
                         'kerb', 'gallery', 'surflan', 'ronstar', 'oryzalin']
            
            # Known fungicides (for disease control)
            fungicides = ['heritage', 'lexicon', 'xzemplar', 'headway', 'renown', 'medallion',
                         'interface', 'tartan', 'banner', 'bayleton', 'tourney', 'compass',
                         'honor', 'posterity', 'secure', 'briskway', 'velista', 'concert',
                         'daconil', 'chipco', 'subdue', 'banol', 'segway', 'disarm']
            
            # Known insecticides (for insect control)
            insecticides = ['acelepryn', 'merit', 'arena', 'allectus', 'meridian', 'chlorpyrifos',
                          'bifenthrin', 'dylox', 'sevin', 'talstar']
            
            # Known PGRs (for growth regulation)
            pgrs = ['primo', 'trimmit', 'cutless', 'anuew', 'embark', 'proxy']
            
            # If asking for fungicide but finds herbicide product, massive penalty
            if product_need == 'fungicide':
                if any(herb in text_lower or herb in source_lower for herb in herbicides):
                    combined_score *= 0.05  # 95% penalty for herbicide when fungicide needed
                elif any(ins in text_lower or ins in source_lower for ins in insecticides):
                    combined_score *= 0.05  # 95% penalty for insecticide when fungicide needed
            
            # If asking for herbicide but finds fungicide, massive penalty
            elif product_need == 'herbicide':
                if any(fung in text_lower or fung in source_lower for fung in fungicides):
                    combined_score *= 0.05
                elif any(ins in text_lower or ins in source_lower for ins in insecticides):
                    combined_score *= 0.05
            
            # If asking for insecticide but finds fungicide/herbicide, massive penalty
            elif product_need == 'insecticide':
                if any(fung in text_lower or fung in source_lower for fung in fungicides):
                    combined_score *= 0.05
                elif any(herb in text_lower or herb in source_lower for herb in herbicides):
                    combined_score *= 0.05
            
            # Generic wrong type keywords (fallback)
            wrong_types = []
            if product_need == 'fungicide':
                wrong_types = ['herbicide', 'pre-emergent', 'post-emergent', 'weed control']
            elif product_need == 'herbicide':
                wrong_types = ['disease control']
            elif product_need == 'insecticide':
                wrong_types = ['disease control', 'weed control']
            
            if any(wrong_type in text_lower[:300] for wrong_type in wrong_types):
                combined_score *= 0.1
        
        scored_results.append({
            'text': text,
            'source': source,
            'score': combined_score,
            'match_id': match['id'],
            'metadata': match['metadata']
        })
    
    # Sort by combined score
    scored_results.sort(key=lambda x: x['score'], reverse=True)
    
    # Step 6: Build context from top results and collect sources/images
    context = ""
    sources = []
    images = []
    
    # FINAL SAFETY CHECK: Remove wrong product types before building context
    herbicide_names = ['specticle', 'tenacity', 'monument', 'certainty', 'sedgehammer', 
                      'drive', 'barricade', 'dimension', 'prodiamine', 'pendimethalin',
                      'acclaim', 'revolver', 'dismiss', 'tribute', 'tower', 'katana',
                      'kerb', 'gallery', 'surflan', 'ronstar', 'oryzalin', 'poacure']
    
    fungicide_names = ['heritage', 'lexicon', 'xzemplar', 'headway', 'renown', 'medallion',
                      'interface', 'tartan', 'banner', 'bayleton', 'tourney', 'compass',
                      'honor', 'posterity', 'secure', 'briskway', 'velista', 'concert',
                      'daconil', 'chipco', 'subdue', 'banol', 'segway', 'disarm']
    
    safety_filtered_results = []
    for result in scored_results[:20]:  # Check top 20
        source = result['source'].lower()
        text = result['text'].lower()[:300]
        
        skip = False
        
        # If disease question, skip herbicides
        if product_need == 'fungicide':
            if any(herb in source or herb in text for herb in herbicide_names):
                skip = True
        
        # If weed question, skip fungicides  
        if product_need == 'herbicide':
            if any(fung in source or fung in text for fung in fungicide_names):
                skip = True
        
        if not skip:
            safety_filtered_results.append(result)
    
    # Use safety-filtered results
    for i, result in enumerate(safety_filtered_results[:12], 1):  # Use top 12 results from multi-pass search
        # Add source number to context for inline citations
        chunk_text = result['text'][:1200]  # Limit each chunk
        source = result['source']
        metadata = result['metadata']
        
        context += f"[Source {i}: {source}]\n{chunk_text}\n\n---\n\n"
        
        # BUILD URL FROM ACTUAL FILESYSTEM (same as resource page)
        source_url = None
        filename = source.replace(' ', ' ')  # Handle spaces
        
        # Search for file in all static folders
        search_folders = [
            'static/product-labels',
            'static/epa_labels',
            'static/solution-sheets',
            'static/spray-programs',
            'static/state-bmps',
            'static/ntep-pdfs',
            'static/industry-resources',
            'static/pdfs',
            'static/labels',
            'static/programs'
        ]
        
        for folder in search_folders:
            if os.path.exists(folder):
                for root, dirs, files in os.walk(folder):
                    for file in files:
                        # Match by source name (case-insensitive)
                        if file.lower().replace('.pdf', '') == source.lower().replace('.pdf', ''):
                            relative_path = os.path.join(root, file).replace('static/', '')
                            source_url = f'/static/{relative_path}'
                            break
                if source_url:
                    break
        
        # Build source with URL
        source_info = {
            'number': i,
            'name': source,
            'url': source_url,
            'type': metadata.get('type', 'document')
        }
        sources.append(source_info)
        
        # Check if this is an equipment manual
        if 'equipment' in result['match_id'].lower():
            chunk_id = result['match_id']
            parts = chunk_id.split('-chunk-')
            if len(parts) > 0:
                doc_name = parts[0].replace('equipment-', '')
                for page in range(1, 4):
                    image_path = f"{doc_name}_page_{page}.jpg"
                    if os.path.exists(f"static/images/{image_path}"):
                        images.append(image_path)
    
    # Limit total context
    context = context[:8000]  # Increased from 7000 to accommodate more sources
    
    # FILTER OUT sources without valid URLs
    sources = [s for s in sources if s['url'] is not None]
    
    # Improved system prompt with reasoning
    system_prompt = """You are an expert turfgrass management consultant. Superintendents are busy - give them FAST, actionable answers with clear reasoning.

CRITICAL: If the question is too vague to give a safe recommendation, ask 2-3 specific follow-up questions instead of guessing.

EXAMPLES OF WHEN TO ASK QUESTIONS:
- "Dollar spot" → Ask: What grass type? What location/climate?
- "Yellowing turf" → Ask: Uniform or patchy? Recent fertilization? Irrigation changes?
- "What spray?" → Ask: What problem are you treating? What turf type?

ONLY provide specific product recommendations when you have enough context to be safe.

CRITICAL SAFETY RULES - NEVER VIOLATE THESE:

🚫 GLYPHOSATE RULES:
- Glyphosate is NON-SELECTIVE - it KILLS ALL PLANTS including turf
- ONLY recommend glyphosate for:
  • Dormant bermudagrass (completely dormant, no green tissue)
  • Full renovation/kill situations
  • Isolated spot treatment with extreme caution
- NEVER recommend glyphosate for general weed control on active turf
- If source mentions glyphosate for Poa/crabgrass, that's for renovation - make this clear

🚫 PRODUCT CATEGORY RULES:
- PoaCure = HERBICIDE for Poa annua control (NOT A PGR)
- PGRs are: Primo MAXX, Trimmit, Cutless, Anuew, Embark
- NEVER list PoaCure alongside PGRs
- NEVER recommend PoaCure for growth regulation
- HERBICIDES (Specticle, Tenacity, Monument, Barricade, etc.) are ONLY for weed control
- NEVER recommend herbicides for disease control (dollar spot, brown patch, summer patch, etc.)
- If a source mentions a herbicide for disease control, it's WRONG - ignore it

🚫 SELECTIVITY RULES:
- Pre-emergent ≠ Post-emergent (don't mix these up)
- Warm-season products ≠ Cool-season products
- Always verify herbicide is safe for target turf type
- If unsure about selectivity, say so explicitly

🚫 TANK MIX SAFETY:
- Never mix products unless label specifically allows it
- High temps + DMI fungicides + chlorothalonil = phytotoxicity
- Herbicides rarely tank-mix safely with fungicides

FORMAT - ALWAYS USE THIS STRUCTURE:
1. Direct answer with SPECIFIC rate/product (never say "recommended rate" - give actual numbers)
2. WHY this is recommended (1 sentence explanation)
3. Alternative options if available (2-3 max) with brief reasoning
4. Cultural/non-chemical options if relevant
5. Source citations

EXAMPLE GOOD ANSWER (Disease Control):
"For dollar spot on bentgrass greens:

Primary: Heritage at 0.16 fl oz per 1000 sq ft [Source 1]
→ Why: Proven efficacy, lowest cost per application, tank-mix compatible
• Reapply every 14-21 days

Alternative: Xzemplar at 0.26 oz/1000 sq ft [Source 2]
→ Why: Longer residual (28 days), better for high-pressure situations
• Higher cost but fewer applications needed

Cultural: Increase nitrogen to 0.2 lb/1000 weekly [Source 3]
→ Why: Reduces disease severity by improving plant vigor"

EXAMPLE GOOD ANSWER (Product Rate):
"Apply Primo MAXX at 5.5 fl oz per acre (0.125 fl oz per 1000 sq ft) [Source 1]
→ Why: Standard rate balances growth regulation without excessive stress
• Reapply every 10-14 days
• Mix with 2-4 gallons water"

CRITICAL RULES:
- ALWAYS give specific rates (oz, lb, fl oz) - NEVER say "labeled rate" or "recommended rate"
- ALWAYS explain WHY you're recommending each option (cost, efficacy, timing, compatibility)
- If you don't have the exact rate, say "Database doesn't contain specific rate - check product label"
- Provide 2-3 options when available (primary + alternatives) with reasoning for each
- Keep reasoning brief (1 sentence per option)
- Always cite sources [Source X]
- NO long explanations, NO background info
- If question asks for a CHART, TABLE, or DIAGRAM: Tell user "The full chart is available in [Source X] - click to view the complete performance data"

Superintendents need ACTIONABLE answers with NUMBERS and REASONING."""
    
    # Ask AI with improved prompt - using GPT-4o for better reasoning
    answer = openai_client.chat.completions.create(
        model="gpt-4o",  # Upgraded from gpt-3.5-turbo for smarter answers
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context from research and manuals:\n\n{context}\n\nQuestion: {question}\n\nProvide specific treatment options with actual rates AND explain WHY each is recommended. If the question asks for a chart/table/diagram, tell the user the information is in [Source X] and they should view it for the full chart."}
        ],
        max_tokens=400,
        temperature=0.2
    )
    
    return jsonify({
        'answer': answer.choices[0].message.content,
        'sources': sources[:12],  # Top 12 sources from multi-pass
        'images': list(set(images[:6]))
    })

if __name__ == '__main__':
    app.run(debug=True, port=5001)
