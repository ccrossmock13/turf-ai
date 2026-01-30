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
from feedback_system import save_feedback as save_user_feedback
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

load_dotenv()

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

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
    logging.debug('Received a question request.')
    question = request.json['question']
    logging.debug(f'Question: {question}')

    # Session management
    conversation_id = _get_or_create_conversation()
    save_message(conversation_id, 'user', question)

    # Process question with context
    contextual_question = build_context_for_ai(conversation_id, question)
    question_to_process = expand_vague_question(contextual_question)

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

    # Combine and score results
    all_matches = (
        search_results['general'].get('matches', []) +
        search_results['product'].get('matches', []) +
        search_results['timing'].get('matches', [])
    )
    scored_results = score_results(all_matches, question, grass_type, region, product_need)

    # Filter and build context
    filtered_results = safety_filter_results(scored_results, question_topic, product_need)
    context, sources, images = build_context(filtered_results, SEARCH_FOLDERS)
    context = context[:MAX_CONTEXT_LENGTH]

    # Process sources
    sources = [s for s in sources if s['url'] is not None]
    sources = deduplicate_sources(sources)
    display_sources = filter_display_sources(sources, SEARCH_FOLDERS)
    all_sources_for_confidence = sources

    if not display_sources:
        display_sources = DEFAULT_SOURCES.copy()

    # Generate AI response with topic-specific prompt and conversation history
    from prompts import build_system_prompt
    system_prompt = build_system_prompt(question_topic, product_need)

    # Build messages array with conversation history for follow-up understanding
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

    # Save response
    save_message(
        conversation_id, 'assistant', assistant_response,
        sources=display_sources[:MAX_SOURCES],
        confidence_score=confidence
    )

    return jsonify({
        'answer': assistant_response,
        'sources': display_sources[:MAX_SOURCES],
        'images': images,
        'confidence': {'score': confidence, 'label': confidence_label},
        'grounding': {
            'verified': grounding_result.get('grounded', True),
            'issues': grounding_result.get('unsupported_claims', [])
        }
    })


def _get_or_create_conversation():
    """Get existing conversation ID or create new session."""
    if 'session_id' not in session:
        session_id, conversation_id = create_session()
        session['session_id'] = session_id
        session['conversation_id'] = conversation_id
    return session['conversation_id']


def _build_user_prompt(context, question):
    """Build the user prompt for the AI."""
    return (
        f"Context from research and manuals:\n\n{context}\n\n"
        f"Question: {question}\n\n"
        "Provide specific treatment options with actual rates AND explain WHY each is recommended. "
        "If the question asks for a chart/table/diagram, tell the user the information is in [Source X] "
        "and they should view it for the full chart."
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
    from cache import get_embedding_cache, get_source_url_cache
    return jsonify({
        'embedding_cache': get_embedding_cache().stats(),
        'source_url_cache': get_source_url_cache().stats()
    })


@app.route('/admin/feedback/review')
def admin_feedback_review():
    from feedback_system import get_negative_feedback
    return jsonify(get_negative_feedback(limit=100, unreviewed_only=True))


@app.route('/admin/feedback/all')
def admin_feedback_all():
    import sqlite3
    conn = sqlite3.connect('greenside_feedback.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, question, ai_answer, user_rating, user_correction, timestamp
        FROM feedback ORDER BY timestamp DESC LIMIT 100
    ''')
    results = cursor.fetchall()
    conn.close()

    feedback = [{
        'id': row[0], 'question': row[1], 'ai_answer': row[2],
        'rating': row[3], 'correction': row[4], 'timestamp': row[5]
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


@app.route('/admin/training/generate', methods=['POST'])
def admin_generate_training():
    from feedback_system import generate_training_file
    result = generate_training_file(min_examples=1)
    if result:
        filepath, num_examples = result
        return jsonify({'success': True, 'filepath': filepath, 'num_examples': num_examples})
    return jsonify({'success': False, 'message': 'Not enough examples to generate training file'})


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
        save_user_feedback(
            question=data.get('question'),
            ai_answer=data.get('answer'),
            rating=data.get('rating'),
            correction=data.get('correction'),
            sources=data.get('sources', []),
            confidence=data.get('confidence', {}).get('score')
        )
        return jsonify({'success': True, 'message': 'Feedback saved'})
    except Exception as e:
        logger.error(f"Error saving feedback: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=Config.DEBUG, port=Config.PORT)
