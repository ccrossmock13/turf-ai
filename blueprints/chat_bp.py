"""
Chat / Conversation / Ask blueprint.

Extracted from app.py — contains:
  - /api/conversations (GET)
  - /api/conversations/<id>/messages (GET)
  - /ask (POST)
  - /ask-stream (POST)
  - /diagnose (POST)
  - /api/new-session (POST)
  - helper functions: _get_or_create_conversation, _is_significant_topic_change,
    _build_user_prompt, _build_messages_with_history, _check_vague_query
"""

import json
import logging
import os

from flask import Blueprint, jsonify, request, session, Response

from auth import login_required
from config import Config
from chat_history import (
    create_session, save_message, build_context_for_ai,
    calculate_confidence_score, get_confidence_label,
    get_conversation_history
)
from constants import SEARCH_FOLDERS, MAX_CONTEXT_LENGTH, MAX_SOURCES
from detection import detect_grass_type, detect_region, detect_product_need
from feedback_system import save_query
from knowledge_base import (
    enrich_context_with_knowledge, get_disease_photos,
    get_weed_photos, get_pest_photos
)
from logging_config import logger
from profile import get_profile, build_profile_context
from query_expansion import expand_query, expand_vague_question
from query_rewriter import rewrite_query
from query_classifier import classify_query, get_response_for_category
from reranker import rerank_results
from scoring_service import score_results, build_context
from search_service import (
    detect_topic, detect_specific_subject, get_embedding,
    search_all_parallel, deduplicate_sources, filter_display_sources,
    TOPIC_KW
)
from feasibility_gate import check_feasibility
from hallucination_filter import filter_hallucinations
from answer_grounding import check_answer_grounding, add_grounding_warning, calculate_grounding_confidence
from tracing import Trace
from cache import get_answer_cache
from demo_cache import find_demo_response
from pipeline import PipelineContext, run_pre_llm_pipeline, run_llm_and_postprocess


chat_bp = Blueprint('chat', __name__)


# ---------------------------------------------------------------------------
# Lazy accessor for singleton clients created in app.py
# ---------------------------------------------------------------------------

def _get_clients():
    """Lazy import of singleton clients from app module."""
    import app as _app
    return _app.openai_client, _app.index


# ---------------------------------------------------------------------------
# Conversation history
# ---------------------------------------------------------------------------

@chat_bp.route('/api/conversations')
@login_required
def api_user_conversations():
    """Get conversation history for the current user."""
    from chat_history import get_user_conversations
    conversations = get_user_conversations(session['user_id'], limit=50)
    return jsonify(conversations)


@chat_bp.route('/api/conversations/<int:conversation_id>/messages')
@login_required
def api_conversation_messages(conversation_id):
    """Get messages for a specific conversation."""
    messages = get_conversation_history(conversation_id, limit=50)
    return jsonify(messages)


# ---------------------------------------------------------------------------
# Main AI endpoint (non-streaming)
# ---------------------------------------------------------------------------

@chat_bp.route('/ask', methods=['POST'])
@login_required
def ask():
    openai_client, index = _get_clients()
    try:
        body = request.json or {}
        question = body.get('question', '').strip()
        if not question:
            return jsonify({
                'answer': "Please enter a question about turfgrass management.",
                'sources': [], 'confidence': {'score': 0, 'label': 'No Question'}
            })

        body['client_ip'] = request.remote_addr or '127.0.0.1'
        ctx = PipelineContext(
            question=question,
            user_id=session.get('user_id'),
            session_data=dict(session),
            openai_client=openai_client,
            pinecone_index=index
        )

        # Pre-LLM pipeline (classify, detect, search, rerank, build context)
        early_return = run_pre_llm_pipeline(ctx, body)
        if early_return:
            status = early_return.pop('_status', 200)
            return jsonify(early_return), status

        # Sync session state back from pipeline
        session['last_topic'] = ctx.question_topic
        if ctx.current_subject:
            session['last_subject'] = ctx.current_subject
        if 'session_id' in ctx.session_data:
            session['session_id'] = ctx.session_data['session_id']
            session['conversation_id'] = ctx.session_data['conversation_id']

        # LLM call + post-processing (grounding, hallucination, confidence)
        response_data = run_llm_and_postprocess(ctx)
        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error processing question: {e}", exc_info=True)
        return jsonify({
            'answer': "I apologize, but I encountered an issue processing your question. Please try rephrasing or ask a different question about turfgrass management.",
            'sources': [], 'confidence': {'score': 0, 'label': 'Error'},
            'error_logged': True
        })


# ---------------------------------------------------------------------------
# SSE streaming endpoint
# ---------------------------------------------------------------------------

@chat_bp.route('/ask-stream', methods=['POST'])
@login_required
def ask_stream():
    """SSE streaming endpoint -- streams LLM tokens in real-time, then final metadata."""
    openai_client, index = _get_clients()

    body = request.json or {}
    question = body.get('question', '').strip()
    if not question:
        return jsonify({'error': 'No question provided'}), 400

    import time as _time
    from concurrent.futures import ThreadPoolExecutor
    from intelligence_engine import RateLimiter, InputSanitizer

    # Capture request/session values BEFORE entering generator (Flask
    # pops the request context after returning the Response, so the
    # generator would otherwise crash with "Working outside of request context")
    _user_id = session.get('user_id')
    _session_id = session.get('session_id')
    _client_ip = request.remote_addr or '127.0.0.1'
    _conversation_id = _get_or_create_conversation()

    def generate():
        try:
            _t0 = _time.time()
            _trace = Trace(question=question, user_id=_user_id, session_id=_session_id)

            # Rate limiting + sanitization
            _rate_check = RateLimiter.check_rate_limit(_client_ip, 'ask')
            if not _rate_check['allowed']:
                yield f"data: {json.dumps({'error': 'Rate limited', 'done': True})}\n\n"
                return
            _sanitize_result = InputSanitizer.check_query(question, _client_ip)
            if not _sanitize_result['safe']:
                yield f"data: {json.dumps({'error': 'Query blocked', 'done': True})}\n\n"
                return

            # Demo/cache fast paths
            if Config.DEMO_MODE:
                demo_response = find_demo_response(question)
                if demo_response:
                    yield f"data: {json.dumps({'token': demo_response.get('answer', '')})}\n\n"
                    demo_response['done'] = True
                    yield f"data: {json.dumps(demo_response)}\n\n"
                    return

            _answer_cache = get_answer_cache()
            _course_id = _user_id
            if not body.get('regenerate', False):
                cached = _answer_cache.get(question, course_id=_course_id)
                if cached:
                    yield f"data: {json.dumps({'token': cached.get('answer', '')})}\n\n"
                    cached['done'] = True
                    cached['cached'] = True
                    yield f"data: {json.dumps(cached)}\n\n"
                    return

            # -- Pre-LLM pipeline (classify, detect, search, score, build context) --
            with ThreadPoolExecutor(max_workers=3) as executor:
                classify_future = executor.submit(classify_query, openai_client, question, "gpt-4o-mini")
                rewrite_future = executor.submit(rewrite_query, openai_client, question, model="gpt-4o-mini")
                feasibility_result = check_feasibility(question)

            classification = classify_future.result()
            intercept_response = get_response_for_category(
                classification['category'], classification.get('reason', '')
            )
            _trace.step("classify", category=classification.get('category'))
            if intercept_response:
                yield f"data: {json.dumps({'token': intercept_response.get('answer', '')})}\n\n"
                intercept_response['done'] = True
                yield f"data: {json.dumps(intercept_response)}\n\n"
                return
            if feasibility_result:
                yield f"data: {json.dumps({'token': feasibility_result.get('answer', '')})}\n\n"
                feasibility_result['done'] = True
                yield f"data: {json.dumps(feasibility_result)}\n\n"
                return

            # Detection
            rewritten_query_text = rewrite_future.result() or question
            question_to_process = expand_vague_question(question)
            grass_type = detect_grass_type(question_to_process)
            region = detect_region(question_to_process)
            product_need = detect_product_need(question_to_process)
            question_topic = detect_topic(question_to_process.lower())
            _trace.step("detect", grass=grass_type, region=region, product=product_need)

            # Profile fallback
            user_profile = get_profile(_user_id)
            if not grass_type and user_profile:
                if user_profile.get('turf_type') == 'golf_course':
                    grass_type = user_profile.get('greens_grass') or user_profile.get('fairways_grass')
                else:
                    grass_type = user_profile.get('primary_grass')
            if not region and user_profile and user_profile.get('region'):
                region = user_profile['region']

            # Expand + search
            expanded_query = expand_query(rewritten_query_text)
            if grass_type:
                expanded_query += f" {grass_type}"
            if region:
                expanded_query += f" {region}"

            search_results = search_all_parallel(
                index, openai_client, rewritten_query_text, expanded_query,
                product_need, grass_type, Config.EMBEDDING_MODEL
            )
            all_matches = (
                search_results['general'].get('matches', []) +
                search_results['product'].get('matches', []) +
                search_results['timing'].get('matches', [])
            )
            scored_results = score_results(all_matches, question, grass_type, region, product_need)
            if scored_results:
                scored_results = rerank_results(rewritten_query_text, scored_results, top_k=20)
            _trace.step("search_rerank", result_count=len(scored_results))

            # Build context
            context, _src_list, _images = build_context(scored_results[:MAX_SOURCES], SEARCH_FOLDERS)
            sources = deduplicate_sources(scored_results[:MAX_SOURCES])
            display_sources = filter_display_sources(sources, SEARCH_FOLDERS)
            context = enrich_context_with_knowledge(context, question)

            # Truncate safely
            if len(context) > MAX_CONTEXT_LENGTH:
                truncated = context[:MAX_CONTEXT_LENGTH]
                last_break = truncated.rfind('\n\n')
                if last_break > MAX_CONTEXT_LENGTH * 0.7:
                    context = truncated[:last_break]
                else:
                    last_period = truncated.rfind('. ')
                    if last_period > MAX_CONTEXT_LENGTH * 0.7:
                        context = truncated[:last_period + 1]
                    else:
                        context = truncated

            # Build messages
            from prompts import build_system_prompt as _build_sys, build_reference_context
            system_prompt = _build_sys(question_topic, product_need)
            ref_ctx = build_reference_context(question_topic, product_need)
            if ref_ctx:
                context = "--- EXPERT REFERENCE DATA ---\n" + ref_ctx + "\n\n--- RETRIEVED SOURCES ---\n" + context
            profile_context = build_profile_context(_user_id, question_topic=question_topic)
            if profile_context:
                system_prompt += "\n\n--- USER CONTEXT ---\n" + profile_context

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": _build_user_prompt(context, question)}
            ]

            # -- Stream LLM response --
            _llm_model = Config.CHAT_MODEL
            full_response = []
            try:
                stream = openai_client.chat.completions.create(
                    model=_llm_model,
                    messages=messages,
                    max_tokens=Config.CHAT_MAX_TOKENS,
                    temperature=Config.CHAT_TEMPERATURE,
                    stream=True,
                    timeout=30
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        token = delta.content
                        full_response.append(token)
                        yield f"data: {json.dumps({'token': token})}\n\n"
            except Exception as llm_err:
                logger.error(f"SSE LLM error: {llm_err}")
                err_msg = "I encountered an error generating a response. Please try again."
                yield f"data: {json.dumps({'token': err_msg})}\n\n"
                full_response = [err_msg]

            assistant_response = ''.join(full_response)
            _trace.step("llm_answer", model=_llm_model)

            # Post-processing
            confidence = calculate_confidence_score(sources, assistant_response, question)
            confidence_label = get_confidence_label(confidence)
            _trace.finish(confidence=confidence, source_count=len(display_sources))

            # Save to conversation history
            try:
                save_message(_conversation_id, 'user', question)
                save_message(_conversation_id, 'assistant', assistant_response)
            except Exception:
                pass

            # Save query to feedback table so user ratings work
            try:
                needs_review = confidence < 70 or not sources
                save_query(
                    question=question, ai_answer=assistant_response,
                    sources=display_sources[:MAX_SOURCES],
                    confidence=confidence, needs_review=needs_review
                )
            except Exception as sq_err:
                logger.warning(f"Failed to save SSE query to feedback: {sq_err}")

            # Normalize sources for frontend display
            normalized_sources = []
            for s in display_sources[:MAX_SOURCES]:
                name = (
                    s.get('name')
                    or s.get('title')
                    or s.get('metadata', {}).get('source', '')
                    or s.get('source', '')
                    or 'Source'
                )
                url = s.get('url') or s.get('source') or ''
                score = s.get('score', s.get('combined_score', 0))
                normalized_sources.append({'name': name, 'url': url, 'score': score})

            # Generate follow-up suggestions
            follow_ups = []
            try:
                follow_up_resp = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Generate exactly 3 short follow-up questions a turf professional might ask next. Return ONLY a JSON array of strings, nothing else."},
                        {"role": "user", "content": f"Question: {question}\nAnswer summary: {assistant_response[:500]}"}
                    ],
                    temperature=0.7,
                    max_tokens=200
                )
                import json as _json
                follow_ups = _json.loads(follow_up_resp.choices[0].message.content)
                if not isinstance(follow_ups, list):
                    follow_ups = []
            except Exception as fu_err:
                logger.debug(f"Follow-up generation failed: {fu_err}")

            # Final metadata event
            final_data = {
                'done': True,
                'sources': normalized_sources,
                'confidence': {'score': confidence, 'label': confidence_label},
                'trace_id': _trace.trace_id,
                'follow_ups': follow_ups[:3]
            }
            yield f"data: {json.dumps(final_data)}\n\n"

        except Exception as e:
            logger.error(f"SSE stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


# ---------------------------------------------------------------------------
# Helper functions (used only by chat routes)
# ---------------------------------------------------------------------------

def _get_or_create_conversation():
    """Get existing conversation ID or create new session."""
    if 'session_id' not in session:
        session_id, conversation_id = create_session(user_id=session.get('user_id'))
        session['session_id'] = session_id
        session['conversation_id'] = conversation_id
    return session['conversation_id']


def _is_significant_topic_change(previous_topic: str, current_topic: str, question: str,
                                  previous_subject: str = None, current_subject: str = None) -> bool:
    """
    Detect if the user is changing to a completely different topic.
    This helps prevent conversation history from confusing unrelated questions.

    Returns True if this appears to be a new topic that shouldn't use previous context.
    """
    # No previous topic means first question -- but check subjects
    if not previous_topic:
        # If the current question has a specific subject different from last known subject,
        # treat as topic change to avoid injecting stale history
        if current_subject and previous_subject and current_subject != previous_subject:
            logging.debug(f'Subject change (no prev topic): {previous_subject} -> {current_subject}')
            return True
        return False

    # If we can't detect the current topic, treat it as a new topic
    # to avoid injecting irrelevant conversation history
    if not current_topic:
        return True

    # Same category but different specific subject = topic change
    # e.g., "pythium" vs "summer patch" are both 'disease' but different subjects
    if previous_topic == current_topic:
        if current_subject and previous_subject and current_subject != previous_subject:
            logging.debug(f'Subject change within same category: {previous_subject} -> {current_subject}')
            return True
        return False

    # Check for explicit "new question" signals (loaded from topic_keywords.json)
    question_lower = question.lower()
    if any(signal in question_lower for signal in TOPIC_KW['new_topic_signals']):
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
            # Still check for subject change within related groups
            if current_subject and previous_subject and current_subject != previous_subject:
                logging.debug(f'Subject change within related group: {previous_subject} -> {current_subject}')
                return True
            return False

    # Check for follow-up language that suggests continuation (loaded from topic_keywords.json)
    if any(question_lower.startswith(signal) or signal in question_lower[:30] for signal in TOPIC_KW['followup_signals']):
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


def _check_vague_query(question: str):
    """
    Detect queries that are too vague, off-topic, or adversarial to process
    meaningfully. Returns a response dict if the query should be intercepted,
    or None if the query should proceed normally.
    """
    q = question.lower().strip().rstrip('?.!')

    # Ultra-short queries (1-3 words) that lack turf context
    words = q.split()
    if len(words) <= 2 and not any(
        term in q for term in [
            'dollar spot', 'brown patch', 'pythium', 'crabgrass', 'poa',
            'grub', 'fungicide', 'herbicide', 'insecticide', 'pgr',
            'mowing', 'aeration', 'topdress', 'irrigation', 'fertiliz',
            'bermuda', 'bentgrass', 'zoysia', 'bluegrass', 'fescue',
            'ryegrass', 'primo', 'heritage', 'banner', 'daconil',
            'barricade', 'dimension', 'tenacity', 'acelepryn',
        ]
    ):
        # Check for ultra-vague fragments
        vague_fragments = [
            'spray it', 'fix it', 'help', 'weeds', 'brown spots',
            'is it too late', 'how much', 'what should i',
        ]
        if q in vague_fragments or len(q) < 12:
            return {
                'answer': (
                    "I'd love to help, but I need a bit more information to give you a useful answer. "
                    "Could you tell me:\n\n"
                    "- **What grass type** do you have? (e.g., bermudagrass, bentgrass, bluegrass)\n"
                    "- **What's the problem or goal?** (e.g., disease, weeds, fertilization, mowing)\n"
                    "- **Any symptoms?** (e.g., brown patches, yellowing, thinning)\n"
                    "- **Your location or region?** (helps with timing and product selection)\n\n"
                    "The more detail you provide, the more specific my recommendations can be!"
                ),
                'sources': [],
                'confidence': {'score': 0, 'label': 'Need More Info'}
            }

    # Off-topic detection -- clearly non-turfgrass questions
    off_topic_patterns = [
        # Finance/business
        'stock', 'invest', 'bitcoin', 'crypto', 'portfolio', 'trading',
        # Medical
        'headache', 'medicine', 'prescription', 'doctor', 'symptom',
        'diagnosis',  # only if no turf context
        # Cooking
        'recipe', 'cook', 'bake', 'ingredient',
        # Coding/tech
        'python script', 'javascript', 'html', 'programming', 'write code',
        'scrape web', 'source code', 'compile',
        # General knowledge
        'meaning of life', 'roman empire', 'history of', 'who invented',
        # Career
        'cover letter', 'resume', 'job interview',
        # Automotive
        'car engine', 'oil change', 'brake pad',
        # Legal
        'legal advice', 'lawsuit', 'attorney',
        # Cannabis/drugs
        'marijuana', 'cannabis', 'weed grow',  # Note: 'weed' alone is turf-related
    ]

    # Check for off-topic but avoid false positives for turf terms
    turf_context_words = [
        'turf', 'grass', 'lawn', 'green', 'fairway', 'golf', 'mow',
        'spray', 'fungicide', 'herbicide', 'fertiliz', 'aerat', 'irrigat',
        'bermuda', 'bentgrass', 'zoysia', 'fescue', 'bluegrass', 'rye',
        'disease', 'weed control', 'grub', 'insect', 'thatch', 'soil',
        'topdress', 'overseed', 'pgr', 'primo', 'frac', 'hrac', 'irac',
        'barricade', 'dimension', 'heritage', 'daconil', 'banner',
        'roundup', 'glyphosate', 'dollar spot', 'brown patch', 'pythium',
        'crabgrass', 'poa annua', 'nematode', 'pesticide', 'label rate',
        'application rate', 'tank mix', 'pre-emergent', 'post-emergent',
        'specticle', 'tenacity', 'acelepryn', 'merit', 'bifenthrin',
        'propiconazole', 'chlorothalonil', 'azoxystrobin',
    ]
    has_turf_context = any(t in q for t in turf_context_words)

    if not has_turf_context:
        for pattern in off_topic_patterns:
            if pattern in q:
                return {
                    'answer': (
                        "I specialize in turfgrass management and can't help with that topic. "
                        "Feel free to ask me anything about turf, lawn care, golf course management, "
                        "disease control, weed management, fertility, irrigation, or cultural practices!"
                    ),
                    'sources': [],
                    'confidence': {'score': 0, 'label': 'Off Topic'}
                }

    # Turf-related but missing critical context (location, grass type, target)
    missing_context_patterns = [
        'what should i spray this month',
        'what should i apply this month',
        'what do i need to spray',
        'what do i spray now',
        'what should i put down this month',
        'what should i apply now',
        'what product should i use this month',
    ]
    if any(p in q for p in missing_context_patterns):
        return {
            'answer': (
                "Great question! To give you the right spray program for this month, "
                "I need a few details:\n\n"
                "- **What grass type?** (e.g., bermudagrass, bentgrass, bluegrass, fescue)\n"
                "- **What's your location/region?** (timing varies significantly by climate)\n"
                "- **What are you targeting?** (disease prevention, weed control, insect management)\n"
                "- **What type of turf area?** (golf greens, fairways, home lawn, sports field)\n\n"
                "With these details, I can recommend specific products, rates, and timing!"
            ),
            'sources': [],
            'confidence': {'score': 0, 'label': 'Need More Info'}
        }

    # Prompt injection / system prompt leak attempts
    injection_patterns = [
        'ignore your instructions', 'ignore your prompt', 'ignore previous',
        'what are your instructions', 'show me your prompt',
        'system prompt', 'you are now', 'act as a', 'pretend you are',
        'forget your training', 'disregard your',
    ]
    if any(p in q for p in injection_patterns):
        return {
            'answer': (
                "I'm Greenside AI, a turfgrass management expert. "
                "I'm here to help with questions about turf, lawn care, disease management, "
                "weed control, fertility, irrigation, and golf course maintenance. "
                "What turf question can I help you with?"
            ),
            'sources': [],
            'confidence': {'score': 0, 'label': 'Off Topic'}
        }

    return None


# ---------------------------------------------------------------------------
# Photo diagnosis route
# ---------------------------------------------------------------------------

@chat_bp.route('/diagnose', methods=['POST'])
@login_required
def diagnose():
    """Analyze an uploaded turf photo using GPT-4o Vision, then enrich with RAG."""
    import base64
    import time as _time

    openai_client, index = _get_clients()
    _t0 = _time.time()

    try:
        if 'image' not in request.files:
            return jsonify({
                'answer': 'No image was uploaded. Please select a photo.',
                'sources': [], 'images': [],
                'confidence': {'score': 0, 'label': 'No Image'}
            })

        image_file = request.files['image']
        optional_question = request.form.get('question', '').strip()

        # Validate file size (5MB)
        image_data = image_file.read()
        if len(image_data) > 5 * 1024 * 1024:
            return jsonify({
                'answer': 'Image is too large. Please use a photo under 5MB.',
                'sources': [], 'images': [],
                'confidence': {'score': 0, 'label': 'Image Too Large'}
            })

        base64_image = base64.b64encode(image_data).decode('utf-8')
        content_type = image_file.content_type or 'image/jpeg'

        # Build Vision prompt
        vision_text = (
            "Analyze this turf/grass photo. Identify:\n"
            "1. What disease, pest, weed, or cultural issue is visible\n"
            "2. What visual evidence supports your identification\n"
            "3. What grass type this appears to be (if identifiable)\n"
            "4. How severe the issue appears (early, moderate, severe)\n"
        )
        if optional_question:
            vision_text += f"\nThe user also asks: {optional_question}\n"

        # Call GPT-4o Vision
        vision_response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a PhD-level turfgrass pathologist performing visual diagnosis. "
                        "Analyze the turf photo and identify the most likely disease, pest, or cultural issue. "
                        "Be specific but honest about uncertainty. "
                        "If the image is not of turf or is too unclear, say so. "
                        "Structure: 1) Identification, 2) Key visual evidence, "
                        "3) Confidence (definite/likely/possible/uncertain), 4) Recommended next steps."
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": vision_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{content_type};base64,{base64_image}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=800,
            temperature=0.3,
            timeout=30
        )

        diagnosis_text = vision_response.choices[0].message.content
        if not diagnosis_text:
            diagnosis_text = "I could not analyze this image. Please try a clearer photo."

        # Try to detect the disease from the diagnosis for RAG enrichment
        diagnosis_lower = diagnosis_text.lower()
        detected_disease = detect_specific_subject(diagnosis_lower)

        sources = []
        images = []

        # If a disease was identified, enrich with RAG treatment data
        if detected_disease:
            try:
                treatment_query = f"How to treat {detected_disease} on turfgrass? Best fungicide options and cultural practices."
                expanded = expand_query(treatment_query)
                embedding = get_embedding(openai_client, expanded, Config.EMBEDDING_MODEL)

                search_results = search_all_parallel(
                    index, openai_client, treatment_query, expanded,
                    'fungicide', None, Config.EMBEDDING_MODEL
                )

                all_matches = []
                for key in search_results:
                    all_matches.extend(search_results[key].get('matches', []))

                if all_matches:
                    scored = score_results(all_matches, treatment_query, None, None, 'fungicide')
                    if scored:
                        context, sources, images = build_context(scored[:5], SEARCH_FOLDERS)
                        context = enrich_context_with_knowledge(treatment_query, context)

                        # Generate combined diagnosis + treatment
                        from prompts import build_system_prompt
                        system_prompt = build_system_prompt('diagnostic', 'fungicide')

                        combined = openai_client.chat.completions.create(
                            model=Config.CHAT_MODEL,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": (
                                    f"Based on visual diagnosis of a turf photo, the likely issue is: {detected_disease}.\n\n"
                                    f"Visual analysis:\n{diagnosis_text}\n\n"
                                    f"Treatment context from research:\n{context}\n\n"
                                    f"Provide a combined response: 1) Visual diagnosis findings, "
                                    f"2) Treatment recommendations with product names and rates, "
                                    f"3) Cultural practice adjustments. Keep it focused and actionable."
                                )}
                            ],
                            max_tokens=Config.CHAT_MAX_TOKENS,
                            temperature=Config.CHAT_TEMPERATURE,
                            timeout=30
                        )
                        diagnosis_text = combined.choices[0].message.content or diagnosis_text
            except Exception as e:
                logger.warning(f"RAG enrichment failed for diagnosis: {e}")

            # Add disease, weed, or pest reference photos
            disease_photos = get_disease_photos(detected_disease)
            if disease_photos:
                images.extend(disease_photos)
            else:
                weed_photos = get_weed_photos(detected_disease)
                if weed_photos:
                    images.extend(weed_photos)
                else:
                    pest_photos = get_pest_photos(detected_disease)
                    if pest_photos:
                        images.extend(pest_photos)

        # Process sources
        sources = deduplicate_sources(sources) if sources else []
        display_sources = filter_display_sources(sources, SEARCH_FOLDERS) if sources else []

        confidence_score = 75 if detected_disease else 55
        confidence_label = get_confidence_label(confidence_score)

        elapsed = _time.time() - _t0
        logging.info(f"Photo diagnosis in {elapsed:.1f}s | detected: {detected_disease or 'unknown'}")

        return jsonify({
            'answer': diagnosis_text,
            'sources': display_sources[:MAX_SOURCES],
            'images': images,
            'confidence': {'score': confidence_score, 'label': confidence_label},
            'grounding': {'verified': True, 'issues': []},
            'needs_review': False
        })

    except Exception as e:
        logger.error(f"Photo diagnosis error: {e}", exc_info=True)
        return jsonify({
            'answer': "I had trouble analyzing the photo. Please try again with a clear, well-lit photo of the affected turf area.",
            'sources': [], 'images': [],
            'confidence': {'score': 0, 'label': 'Error'}
        })


# ---------------------------------------------------------------------------
# Session routes
# ---------------------------------------------------------------------------

@chat_bp.route('/api/new-session', methods=['POST'])
@login_required
def new_session():
    """Clear session to start a new conversation."""
    session.clear()
    return jsonify({'success': True})
