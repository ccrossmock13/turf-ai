from flask import Flask, render_template, send_from_directory, jsonify, request, session
from routes import turf_bp
import os
import logging
import openai
from config import Config
from dotenv import load_dotenv
from pinecone import Pinecone
from logging_config import logger
from detection import detect_grass_type, detect_region, detect_product_need
from query_expansion import expand_query, expand_vague_question
from chat_history import (
    create_session, save_message, build_context_for_ai,
    calculate_confidence_score, get_confidence_label,
    get_conversation_history
)
from feedback_system import save_feedback as save_user_feedback, save_query, update_query_rating
from constants import (
    STATIC_FOLDERS, SEARCH_FOLDERS, DEFAULT_SOURCES,
    MAX_CONTEXT_LENGTH, MAX_SOURCES
)
from search_service import (
    detect_topic, detect_state, get_embedding,
    search_all_parallel,
    deduplicate_sources, filter_display_sources
)
from scoring_service import score_results, safety_filter_results, build_context
from query_rewriter import rewrite_query
from answer_grounding import check_answer_grounding, add_grounding_warning, calculate_grounding_confidence
from knowledge_base import enrich_context_with_knowledge, extract_product_names, extract_disease_names
from reranker import rerank_results, is_cross_encoder_available
from web_search import should_trigger_web_search, search_web_for_turf_info, format_web_search_disclaimer
from weather_service import get_weather_data, get_weather_context, get_weather_warnings, format_weather_for_response

load_dotenv()

# Logging is configured in logging_config.py

app = Flask(__name__)
app.secret_key = Config.FLASK_SECRET_KEY
app.register_blueprint(turf_bp)

openai_client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
pc = Pinecone(api_key=Config.PINECONE_API_KEY)
index = pc.Index(Config.PINECONE_INDEX)


# -----------------------------------------------------------------------------
# Static file routes
# -----------------------------------------------------------------------------

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/epa_labels/<path:filename>')
def serve_epa_label(filename):
    return send_from_directory('static/epa_labels', filename)


@app.route('/product-labels/<path:filename>')
def serve_product_label(filename):
    return send_from_directory('static/product-labels', filename)


@app.route('/solution-sheets/<path:filename>')
def serve_solution_sheet(filename):
    return send_from_directory('static/solution-sheets', filename)


@app.route('/spray-programs/<path:filename>')
def serve_spray_program(filename):
    return send_from_directory('static/spray-programs', filename)


@app.route('/ntep-pdfs/<path:filename>')
def serve_ntep(filename):
    return send_from_directory('static/ntep-pdfs', filename)


@app.route('/resources')
def resources():
    return render_template('resources.html')


@app.route('/api/resources')
def get_resources():
    resources_list = []
    try:
        for folder, category in STATIC_FOLDERS.items():
            folder_path = f'static/{folder}'
            if os.path.exists(folder_path):
                for root, dirs, files in os.walk(folder_path):
                    for filename in files:
                        if filename.lower().endswith('.pdf') and not filename.startswith('.'):
                            full_path = os.path.join(root, filename)
                            relative_path = full_path.replace('static/', '')
                            resources_list.append({
                                'filename': filename,
                                'url': f'/static/{relative_path}',
                                'category': category
                            })
        resources_list.sort(key=lambda x: x['filename'])
    except Exception as e:
        logger.error(f"Error reading PDF folders: {e}")
        return jsonify({'error': str(e)}), 500
    return jsonify(resources_list)


# -----------------------------------------------------------------------------
# Main AI endpoint
# -----------------------------------------------------------------------------

@app.route('/ask', methods=['POST'])
def ask():
    try:
        logging.debug('Received a question request.')
        question = request.json.get('question', '').strip()
        if not question:
            return jsonify({
                'answer': "Please enter a question about turfgrass management.",
                'sources': [],
                'confidence': {'score': 0, 'label': 'No Question'}
            })
        logging.debug(f'Question: {question}')

    # Get optional location for weather (can be passed from frontend)
    user_location = request.json.get('location', {})
    lat = user_location.get('lat')
    lon = user_location.get('lon')
    city = user_location.get('city')
    state = user_location.get('state')

    # Session management
    conversation_id = _get_or_create_conversation()

    # Detect if this is a topic change - if so, don't use conversation history
    current_topic = detect_topic(question.lower())
    previous_topic = session.get('last_topic')
    is_topic_change = _is_significant_topic_change(previous_topic, current_topic, question)

    # Always save the message
    save_message(conversation_id, 'user', question)

    if is_topic_change:
        logging.debug(f'Topic change detected: {previous_topic} -> {current_topic}')
        # Start fresh context for new topic - don't use conversation history
        contextual_question = question
        question_to_process = expand_vague_question(question)
    else:
        # Use conversation history for follow-up questions
        contextual_question = build_context_for_ai(conversation_id, question)
        question_to_process = expand_vague_question(contextual_question)

    # Update the last topic
    session['last_topic'] = current_topic

    # LLM-based query rewriting for better retrieval
    rewritten_query = rewrite_query(openai_client, question_to_process, model="gpt-4o-mini")
    logging.debug(f'Rewritten query: {rewritten_query[:100]}')

    # Detect context from original question
    grass_type = detect_grass_type(question_to_process)
    region = detect_region(question_to_process)
    product_need = detect_product_need(question_to_process)
    question_topic = detect_topic(question_to_process.lower())
    if product_need and not question_topic:
        question_topic = 'chemical'

    # Build expanded query using rewritten version
    expanded_query = expand_query(rewritten_query)
    if grass_type:
        expanded_query += f" {grass_type}"
    if region:
        expanded_query += f" {region}"

    # Search (parallel execution for better performance)
    search_results = search_all_parallel(
        index, openai_client, rewritten_query, expanded_query,
        product_need, grass_type, Config.EMBEDDING_MODEL
    )

    # Check if web search fallback is needed (only when NO results, not low confidence)
    used_web_search = False
    web_search_result = None
    if should_trigger_web_search(search_results):
        logging.debug('No Pinecone results found - triggering web search fallback')
        web_search_result = search_web_for_turf_info(openai_client, question)
        if web_search_result:
            used_web_search = True
            logging.debug('Web search fallback returned results')

    # Combine and score results
    all_matches = (
        search_results['general'].get('matches', []) +
        search_results['product'].get('matches', []) +
        search_results['timing'].get('matches', [])
    )
    scored_results = score_results(all_matches, question, grass_type, region, product_need)

    # Apply cross-encoder reranking for better relevance (if available)
    if scored_results:
        scored_results = rerank_results(rewritten_query, scored_results, top_k=20)

    # Filter and build context
    filtered_results = safety_filter_results(scored_results, question_topic, product_need)
    context, sources, images = build_context(filtered_results, SEARCH_FOLDERS)

    # If web search was used, replace context with web search results
    if used_web_search and web_search_result:
        context = web_search_result['context']
        sources = web_search_result['sources']
        images = []
    else:
        # Enrich context with structured knowledge base data (only for DB results)
        context = enrich_context_with_knowledge(question, context)

    # Add weather context if location provided and topic is relevant
    weather_data = None
    weather_topics = {'chemical', 'fungicide', 'herbicide', 'insecticide', 'irrigation', 'cultural', 'diagnostic', 'disease'}
    if (lat and lon) or city:
        if question_topic in weather_topics or product_need:
            weather_data = get_weather_data(lat=lat, lon=lon, city=city, state=state)
            if weather_data:
                weather_context = get_weather_context(weather_data)
                context = context + "\n\n" + weather_context
                logging.debug(f"Added weather context for {weather_data.get('location', 'unknown')}")

    context = context[:MAX_CONTEXT_LENGTH]

    # Process sources
    sources = [s for s in sources if s.get('url') is not None or s.get('note')]  # Allow web search sources
    sources = deduplicate_sources(sources)
    display_sources = filter_display_sources(sources, SEARCH_FOLDERS) if not used_web_search else sources
    all_sources_for_confidence = sources

    if not display_sources:
        display_sources = DEFAULT_SOURCES.copy()

    # Generate AI response with topic-specific prompt and conversation history
    from prompts import build_system_prompt
    system_prompt = build_system_prompt(question_topic, product_need)

    # Build messages array - skip history if topic changed
    if is_topic_change:
        # Fresh start - no conversation history
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _build_user_prompt(context, question)}
        ]
    else:
        # Include conversation history for follow-up understanding
        messages = _build_messages_with_history(
            conversation_id, system_prompt, context, question
        )

    answer = openai_client.chat.completions.create(
        model=Config.CHAT_MODEL,
        messages=messages,
        max_tokens=Config.CHAT_MAX_TOKENS,
        temperature=Config.CHAT_TEMPERATURE
    )
    assistant_response = answer.choices[0].message.content

    # Check answer grounding against sources
    grounding_result = check_answer_grounding(
        openai_client, assistant_response, context, question, model="gpt-4o-mini"
    )

    # Add warning if answer has grounding issues
    assistant_response = add_grounding_warning(assistant_response, grounding_result)

    # Calculate confidence with grounding adjustment
    base_confidence = calculate_confidence_score(all_sources_for_confidence, assistant_response, question)
    confidence = calculate_grounding_confidence(grounding_result, base_confidence)
    confidence_label = get_confidence_label(confidence)

    # Save response to conversation history
    save_message(
        conversation_id, 'assistant', assistant_response,
        sources=display_sources[:MAX_SOURCES],
        confidence_score=confidence
    )

    # Determine if human review is needed (below 70% threshold)
    needs_review = (
        confidence < 70 or
        not grounding_result.get('grounded', True) or
        len(grounding_result.get('unsupported_claims', [])) > 1 or
        not sources  # No sources found
    )

    # Save query to admin dashboard (all queries, not just rated ones)
    save_query(
        question=question,
        ai_answer=assistant_response,
        sources=display_sources[:MAX_SOURCES],
        confidence=confidence,
        needs_review=needs_review
    )

    response_data = {
        'answer': assistant_response,
        'sources': display_sources[:MAX_SOURCES],
        'images': images,
        'confidence': {'score': confidence, 'label': confidence_label},
        'grounding': {
            'verified': grounding_result.get('grounded', True),
            'issues': grounding_result.get('unsupported_claims', [])
        },
        'needs_review': needs_review
    }

    # Add web search indicator if used
    if used_web_search:
        response_data['web_search_used'] = True
        response_data['web_search_disclaimer'] = format_web_search_disclaimer()

    # Add weather info if available
    if weather_data:
        response_data['weather'] = {
            'location': weather_data.get('location'),
            'summary': format_weather_for_response(weather_data),
            'warnings': get_weather_warnings(weather_data)
        }

    return jsonify(response_data)

    except Exception as e:
        # Log the error but never crash - always return something useful
        logger.error(f"Error processing question: {e}", exc_info=True)

        # Return a graceful fallback response
        return jsonify({
            'answer': "I apologize, but I encountered an issue processing your question. Please try rephrasing or ask a different question about turfgrass management.",
            'sources': [],
            'confidence': {'score': 0, 'label': 'Error'},
            'error_logged': True
        })


def _get_or_create_conversation():
    """Get existing conversation ID or create new session."""
    if 'session_id' not in session:
        session_id, conversation_id = create_session()
        session['session_id'] = session_id
        session['conversation_id'] = conversation_id
    return session['conversation_id']


def _is_significant_topic_change(previous_topic: str, current_topic: str, question: str) -> bool:
    """
    Detect if the user is changing to a completely different topic.
    This helps prevent conversation history from confusing unrelated questions.

    Returns True if this appears to be a new topic that shouldn't use previous context.
    """
    # No previous topic means first question
    if not previous_topic:
        return False

    # Same topic - not a change
    if previous_topic == current_topic:
        return False

    # Check for explicit "new question" signals
    new_topic_signals = [
        'different question',
        'new question',
        'unrelated',
        'switching topic',
        'change of topic',
        'another question',
        'also wondering',
    ]
    question_lower = question.lower()
    if any(signal in question_lower for signal in new_topic_signals):
        return True

    # Define topic groups that are related
    related_groups = [
        {'chemical', 'fungicide', 'herbicide', 'insecticide'},
        {'cultural', 'irrigation', 'fertilizer'},
        {'equipment', 'calibration'},
        {'diagnostic', 'disease'},
    ]

    # Check if topics are in the same related group
    for group in related_groups:
        if previous_topic in group and current_topic in group:
            return False

    # Check for follow-up language that suggests continuation
    followup_signals = [
        'what about',
        'how about',
        'and ',
        'also ',
        'what if',
        'same ',
        'that ',
        'the rate',
        'the product',
        'this disease',
        'those ',
    ]
    if any(question_lower.startswith(signal) or signal in question_lower[:30] for signal in followup_signals):
        return False

    # Different topic groups and no follow-up language = topic change
    if previous_topic and current_topic and previous_topic != current_topic:
        return True

    return False


def _build_user_prompt(context, question):
    """Build the user prompt for the AI."""
    return (
        f"Context from research and manuals:\n\n{context}\n\n"
        f"Question: {question}\n\n"
        "INSTRUCTIONS:\n"
        "1. Provide specific treatment options with actual rates AND explain WHY each is recommended.\n"
        "2. Include FRAC/HRAC/IRAC codes when recommending pesticides.\n"
        "3. If verified product data is provided, use those exact rates."
    )


def _build_messages_with_history(conversation_id, system_prompt, context, current_question):
    """
    Build messages array including conversation history for follow-up understanding.
    This allows the AI to understand references like "what about the rate?" or "that product".
    """
    messages = [{"role": "system", "content": system_prompt}]

    # Get recent conversation history (last 3 exchanges = 6 messages)
    history = get_conversation_history(conversation_id, limit=6)

    # Add historical messages (excluding the current question we just saved)
    for msg in history[:-1]:  # Skip the last one (current question)
        if msg['role'] == 'user':
            messages.append({"role": "user", "content": msg['content']})
        elif msg['role'] == 'assistant':
            # Truncate long responses to save tokens
            content = msg['content']
            if len(content) > 500:
                content = content[:500] + "..."
            messages.append({"role": "assistant", "content": content})

    # Add current question with context
    messages.append({
        "role": "user",
        "content": _build_user_prompt(context, current_question)
    })

    return messages


# -----------------------------------------------------------------------------
# Session routes
# -----------------------------------------------------------------------------

@app.route('/api/new-session', methods=['POST'])
def new_session():
    """Clear session to start a new conversation."""
    session.clear()
    return jsonify({'success': True})


# -----------------------------------------------------------------------------
# Admin routes
# -----------------------------------------------------------------------------

@app.route('/admin')
def admin_dashboard():
    return render_template('admin.html')


@app.route('/admin/stats')
def admin_stats():
    from feedback_system import get_feedback_stats
    return jsonify(get_feedback_stats())


@app.route('/admin/cache')
def admin_cache_stats():
    """Get cache statistics for monitoring."""
    from cache import get_embedding_cache, get_source_url_cache, get_search_cache
    return jsonify({
        'embedding_cache': get_embedding_cache().stats(),
        'source_url_cache': get_source_url_cache().stats(),
        'search_cache': get_search_cache().stats()
    })


@app.route('/admin/feedback/review')
def admin_feedback_review():
    from feedback_system import get_negative_feedback
    return jsonify(get_negative_feedback(limit=100, unreviewed_only=True))


@app.route('/admin/feedback/needs-review')
def admin_needs_review():
    """Get queries that were auto-flagged for human review (< 70% confidence)"""
    from feedback_system import get_queries_needing_review
    return jsonify(get_queries_needing_review(limit=100))


@app.route('/admin/feedback/all')
def admin_feedback_all():
    import sqlite3
    from feedback_system import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, question, ai_answer, user_rating, user_correction, timestamp, confidence_score
        FROM feedback ORDER BY timestamp DESC LIMIT 100
    ''')
    results = cursor.fetchall()
    conn.close()

    feedback = [{
        'id': row[0], 'question': row[1], 'ai_answer': row[2],
        'rating': row[3], 'correction': row[4], 'timestamp': row[5],
        'confidence': row[6]
    } for row in results]
    return jsonify(feedback)


@app.route('/admin/feedback/approve', methods=['POST'])
def admin_approve_feedback():
    from feedback_system import approve_for_training
    data = request.json
    approve_for_training(data.get('id'), data.get('correction'))
    return jsonify({'success': True})


@app.route('/admin/feedback/reject', methods=['POST'])
def admin_reject_feedback():
    from feedback_system import reject_feedback
    data = request.json
    reject_feedback(data.get('id'), "Rejected by admin")
    return jsonify({'success': True})


@app.route('/admin/review-queue')
def admin_review_queue():
    """Get unified moderation queue (user-flagged + auto-flagged)"""
    from feedback_system import get_review_queue
    queue_type = request.args.get('type', 'all')  # all, negative, low_confidence
    return jsonify(get_review_queue(limit=100, queue_type=queue_type))


@app.route('/admin/moderate', methods=['POST'])
def admin_moderate():
    """Moderate an answer: approve, reject, or correct"""
    from feedback_system import moderate_answer
    data = request.json
    result = moderate_answer(
        feedback_id=data.get('id'),
        action=data.get('action'),  # approve, reject, correct
        corrected_answer=data.get('corrected_answer'),
        reason=data.get('reason'),
        moderator=data.get('moderator', 'admin')
    )
    return jsonify(result)


@app.route('/admin/moderator-history')
def admin_moderator_history():
    """Get audit trail of moderator actions"""
    from feedback_system import get_moderator_history
    return jsonify(get_moderator_history(limit=100))


@app.route('/admin/training/generate', methods=['POST'])
def admin_generate_training():
    from feedback_system import generate_training_file
    result = generate_training_file(min_examples=1)
    if result:
        filepath, num_examples = result
        return jsonify({'success': True, 'filepath': filepath, 'num_examples': num_examples})
    return jsonify({'success': False, 'message': 'Not enough examples to generate training file'})


@app.route('/admin/knowledge')
def admin_knowledge_status():
    """Get knowledge base status."""
    from knowledge_builder import IndexTracker, scan_for_pdfs
    tracker = IndexTracker()
    stats = tracker.get_stats()

    all_pdfs = scan_for_pdfs()
    unindexed = [f for f, _ in all_pdfs if not tracker.is_indexed(f)]

    return jsonify({
        'indexed_files': stats['total_files'],
        'total_chunks': stats['total_chunks'],
        'last_run': stats['last_run'],
        'total_pdfs': len(all_pdfs),
        'unindexed': len(unindexed),
        'unindexed_sample': [os.path.basename(f) for f in unindexed[:10]]
    })


@app.route('/admin/knowledge/build', methods=['POST'])
def admin_knowledge_build():
    """Trigger knowledge base build (limited for safety)."""
    from knowledge_builder import build_knowledge_base
    import threading

    limit = request.json.get('limit', 10)  # Default to 10 files at a time

    # Run in background thread
    def run_build():
        try:
            build_knowledge_base(limit=limit)
        except Exception as e:
            logger.error(f"Knowledge build error: {e}")

    thread = threading.Thread(target=run_build)
    thread.start()

    return jsonify({
        'success': True,
        'message': f'Building knowledge base (processing up to {limit} files in background)'
    })


# -----------------------------------------------------------------------------
# TGIF routes
# -----------------------------------------------------------------------------

@app.route('/tgif')
def tgif_search():
    return render_template('tgif_search.html')


@app.route('/tgif/analyze', methods=['POST'])
def tgif_analyze():
    import json
    try:
        data = request.json
        question = data.get('question')
        results = data.get('results')

        analysis_prompt = f"""You are analyzing turfgrass research results from the TGIF database.

User's question: {question}

Research results from TGIF:
{results}

Your task:
1. Provide a 2-3 sentence executive summary answering the user's question based on the research
2. Extract the top 5 most relevant findings with titles and brief summaries

Respond in JSON format:
{{
  "summary": "Executive summary here",
  "findings": [
    {{"title": "Study title", "summary": "Key finding"}},
    ...
  ]
}}
"""
        response = openai_client.chat.completions.create(
            model=Config.CHAT_MODEL,
            messages=[
                {"role": "system", "content": "You are a turfgrass research expert analyzing scientific literature."},
                {"role": "user", "content": analysis_prompt}
            ],
            temperature=0.3,
            max_tokens=1500
        )
        analysis = json.loads(response.choices[0].message.content)
        return jsonify(analysis)
    except Exception as e:
        logger.error(f"Error analyzing TGIF results: {e}")
        return jsonify({'error': str(e)}), 500


# -----------------------------------------------------------------------------
# Feedback routes
# -----------------------------------------------------------------------------

@app.route('/feedback', methods=['POST'])
def submit_feedback():
    try:
        data = request.json
        # Update the existing query with the user's rating
        update_query_rating(
            question=data.get('question'),
            rating=data.get('rating'),
            correction=data.get('correction')
        )
        return jsonify({'success': True, 'message': 'Feedback saved'})
    except Exception as e:
        logger.error(f"Error saving feedback: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# -----------------------------------------------------------------------------
# Health check for monitoring
# -----------------------------------------------------------------------------

@app.route('/health')
def health_check():
    """Health check endpoint for production monitoring."""
    import time
    start = time.time()

    status = {
        'status': 'healthy',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
        'services': {}
    }

    # Check Pinecone
    try:
        stats = index.describe_index_stats()
        status['services']['pinecone'] = {
            'status': 'connected',
            'vectors': stats.get('total_vector_count', 0)
        }
    except Exception as e:
        status['services']['pinecone'] = {'status': 'error', 'message': str(e)[:100]}
        status['status'] = 'degraded'

    # Check OpenAI key configured
    try:
        if Config.OPENAI_API_KEY and len(Config.OPENAI_API_KEY) > 10:
            status['services']['openai'] = {'status': 'configured'}
        else:
            status['services']['openai'] = {'status': 'not configured'}
            status['status'] = 'degraded'
    except Exception:
        status['services']['openai'] = {'status': 'error'}
        status['status'] = 'degraded'

    # Check database
    try:
        from feedback_system import get_feedback_stats
        stats = get_feedback_stats()
        status['services']['database'] = {
            'status': 'connected',
            'total_queries': stats.get('total_feedback', 0)
        }
    except Exception as e:
        status['services']['database'] = {'status': 'error', 'message': str(e)[:100]}
        status['status'] = 'degraded'

    status['response_time_ms'] = round((time.time() - start) * 1000, 2)

    http_status = 200 if status['status'] == 'healthy' else 503
    return jsonify(status), http_status


# -----------------------------------------------------------------------------
# Weather routes
# -----------------------------------------------------------------------------

@app.route('/api/weather', methods=['GET', 'POST'])
def get_weather():
    """Get weather data for a location."""
    if request.method == 'POST':
        data = request.json or {}
    else:
        data = request.args

    lat = data.get('lat', type=float) if request.method == 'GET' else data.get('lat')
    lon = data.get('lon', type=float) if request.method == 'GET' else data.get('lon')
    city = data.get('city')
    state = data.get('state')

    if not ((lat and lon) or city):
        return jsonify({'error': 'Provide lat/lon or city'}), 400

    weather_data = get_weather_data(lat=lat, lon=lon, city=city, state=state)
    if not weather_data:
        return jsonify({'error': 'Could not fetch weather data'}), 500

    return jsonify({
        'location': weather_data.get('location'),
        'current': weather_data.get('current'),
        'forecast': weather_data.get('forecast'),
        'warnings': get_weather_warnings(weather_data),
        'summary': format_weather_for_response(weather_data)
    })


if __name__ == '__main__':
    app.run(debug=Config.DEBUG, port=Config.PORT)
