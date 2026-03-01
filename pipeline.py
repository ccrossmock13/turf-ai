"""
RAG Pipeline for Greenside AI.
Extracts the core question-answering logic from app.py into a testable, reusable module.
Both /ask and /ask-stream use this pipeline.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from config import Config
from constants import SEARCH_FOLDERS, DEFAULT_SOURCES, MAX_CONTEXT_LENGTH, MAX_SOURCES
from detection import detect_grass_type, detect_region, detect_product_need
from search_service import (
    detect_topic, detect_specific_subject, detect_state, get_embedding,
    search_all_parallel, deduplicate_sources, filter_display_sources
)
from scoring_service import score_results, safety_filter_results, build_context
from query_rewriter import rewrite_query
from query_expansion import expand_query, expand_vague_question
from query_classifier import classify_query, get_response_for_category
from feasibility_gate import check_feasibility
from knowledge_base import (
    enrich_context_with_knowledge, extract_product_names, extract_disease_names,
    get_disease_photos, get_weed_photos, get_pest_photos
)
from reranker import rerank_results, is_cross_encoder_available
from web_search import (
    should_trigger_web_search, should_supplement_with_web_search,
    search_web_for_turf_info, format_web_search_disclaimer
)
from weather_service import get_weather_data, get_weather_context, get_weather_warnings, format_weather_for_response
from hallucination_filter import filter_hallucinations
from answer_grounding import check_answer_grounding, add_grounding_warning, calculate_grounding_confidence
from answer_validator import apply_validation
from chat_history import (
    create_session, save_message, build_context_for_ai,
    calculate_confidence_score, get_confidence_label,
    get_conversation_history
)
from feedback_system import save_query
from profile import get_profile, build_profile_context
from spray_tracker import build_spray_history_context
from turf_intelligence import (
    build_seasonal_context, select_model, build_frac_rotation_context,
    generate_follow_up_suggestions, assess_knowledge_gaps,
    build_weather_spray_context, build_diagnostic_context,
    get_cultivar_context, build_cross_module_context,
    build_cost_context, generate_predictive_alerts,
    get_regional_disease_pressure, get_turfgrass_zone,
    process_community_feedback, log_knowledge_gap,
)
from answer_grounding import validate_domain_specific
from query_expansion import get_query_intent
from intelligence_engine import (
    SelfHealingLoop, ABTestingEngine, SourceQualityIntelligence,
    ConfidenceCalibration, PipelineAnalytics, CircuitBreaker,
    PromptVersioning, FeatureFlags, RateLimiter, InputSanitizer,
    process_answer_intelligence
)
from demo_cache import find_demo_response
from cache import get_answer_cache
from tracing import Trace
from product_loader import search_products

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper functions (moved from app.py)
# ---------------------------------------------------------------------------

def is_significant_topic_change(previous_topic, current_topic, question,
                                previous_subject=None, current_subject=None):
    """Detect if the user is changing to a completely different topic."""
    if not previous_topic:
        if current_subject and previous_subject and current_subject != previous_subject:
            return True
        return False

    if not current_topic:
        return True

    if previous_topic == current_topic:
        if current_subject and previous_subject and current_subject != previous_subject:
            return True
        return False

    new_topic_signals = [
        'different question', 'new question', 'unrelated',
        'switching topic', 'change of topic', 'another question', 'also wondering',
    ]
    question_lower = question.lower()
    if any(signal in question_lower for signal in new_topic_signals):
        return True

    related_groups = [
        {'chemical', 'fungicide', 'herbicide', 'insecticide'},
        {'cultural', 'irrigation', 'fertilizer'},
        {'equipment', 'calibration'},
        {'diagnostic', 'disease'},
    ]
    for group in related_groups:
        if previous_topic in group and current_topic in group:
            if current_subject and previous_subject and current_subject != previous_subject:
                return True
            return False

    followup_signals = [
        'what about', 'how about', 'and ', 'also ', 'what if',
        'same ', 'that ', 'the rate', 'the product', 'this disease', 'those ',
    ]
    if any(question_lower.startswith(s) or s in question_lower[:30] for s in followup_signals):
        return False

    if previous_topic and current_topic and previous_topic != current_topic:
        return True

    return False


def build_user_prompt(context, question):
    """Build the user prompt for the AI."""
    return (
        f"Context from research and manuals:\n\n{context}\n\n"
        f"Question: {question}\n\n"
        "INSTRUCTIONS:\n"
        "1. Provide specific treatment options with actual rates AND explain WHY each is recommended.\n"
        "2. Include FRAC/HRAC/IRAC codes when recommending pesticides.\n"
        "3. If verified product data is provided, use those exact rates."
    )


def build_messages_with_history(conversation_id, system_prompt, context, current_question):
    """Build messages array including conversation history for follow-up understanding."""
    messages = [{"role": "system", "content": system_prompt}]
    history = get_conversation_history(conversation_id, limit=6)
    for msg in history[:-1]:
        if msg['role'] == 'user':
            messages.append({"role": "user", "content": msg['content']})
        elif msg['role'] == 'assistant':
            content = msg['content']
            if len(content) > 500:
                content = content[:500] + "..."
            messages.append({"role": "assistant", "content": content})
    messages.append({
        "role": "user",
        "content": build_user_prompt(context, current_question)
    })
    return messages


def truncate_context(context, max_length=MAX_CONTEXT_LENGTH):
    """Safe truncation: cut at last source boundary, not mid-sentence."""
    if len(context) <= max_length:
        return context
    truncated = context[:max_length]
    last_break = truncated.rfind('\n\n')
    if last_break > max_length * 0.7:
        return truncated[:last_break]
    last_period = truncated.rfind('. ')
    if last_period > max_length * 0.7:
        return truncated[:last_period + 1]
    return truncated


# ---------------------------------------------------------------------------
# Pre-LLM pipeline: everything before the LLM call
# ---------------------------------------------------------------------------

class PipelineContext:
    """Holds all state accumulated during the pipeline."""

    def __init__(self, question, user_id, session_data, openai_client, pinecone_index):
        self.question = question
        self.user_id = user_id
        self.session_data = session_data
        self.openai_client = openai_client
        self.index = pinecone_index

        # Populated during pipeline execution
        self.trace = None
        self.timings = {}
        self.t0 = time.time()

        self.question_topic = None
        self.current_subject = None
        self.grass_type = None
        self.region = None
        self.product_need = None
        self.rewritten_query = None

        self.context = ""
        self.sources = []
        self.display_sources = []
        self.images = []

        self.system_prompt = ""
        self.messages = []

        self.used_web_search = False
        self.supplement_mode = False
        self.weather_data = None
        self.pinecone_failed = False

        self.llm_model = Config.CHAT_MODEL
        self.llm_max_tokens = Config.CHAT_MAX_TOKENS
        self.llm_temperature = Config.CHAT_TEMPERATURE
        self.ab_assignment = None
        self.token_usage = {}

        self.conversation_id = None
        self.is_topic_change = False


def run_pre_llm_pipeline(ctx: PipelineContext, body: dict) -> Optional[dict]:
    """
    Execute the full pre-LLM pipeline: classify, detect, search, rerank, build context.

    Returns:
        - dict if the pipeline should short-circuit (intercept, feasibility, budget exceeded)
        - None if the pipeline should proceed to LLM call
    """
    ctx.trace = Trace(question=ctx.question, user_id=ctx.user_id,
                      session_id=ctx.session_data.get('session_id'))

    # --- Rate limiting ---
    client_ip = body.get('client_ip', '127.0.0.1')
    rate_check = RateLimiter.check_rate_limit(client_ip, 'ask')
    if not rate_check['allowed']:
        return {
            'answer': "Too many requests. Please wait a moment and try again.",
            'sources': [], 'confidence': {'score': 0, 'label': 'Rate Limited'},
            '_status': 429
        }

    # --- Input sanitization ---
    sanitize_result = InputSanitizer.check_query(ctx.question, client_ip)
    if not sanitize_result['safe']:
        return {
            'answer': "I can only help with turfgrass management questions. Please rephrase your question.",
            'sources': [], 'confidence': {'score': 0, 'label': 'Blocked'}
        }

    # --- Demo mode ---
    if Config.DEMO_MODE:
        demo_response = find_demo_response(ctx.question)
        if demo_response:
            return demo_response

    # --- Answer cache ---
    answer_cache = get_answer_cache()
    skip_cache = body.get('regenerate', False)
    if not skip_cache:
        cached = answer_cache.get(ctx.question, course_id=ctx.user_id)
        if cached:
            cached['cached'] = True
            return cached

    # --- Parallel: classify + rewrite + feasibility ---
    with ThreadPoolExecutor(max_workers=3) as executor:
        classify_future = executor.submit(classify_query, ctx.openai_client, ctx.question, "gpt-4o-mini")
        rewrite_future = executor.submit(rewrite_query, ctx.openai_client, ctx.question, model="gpt-4o-mini")
        feasibility_result = check_feasibility(ctx.question)

    classification = classify_future.result()
    intercept_response = get_response_for_category(
        classification['category'], classification.get('reason', '')
    )
    ctx.timings['1_classify'] = time.time() - ctx.t0
    ctx.trace.step("classify", category=classification.get('category'), intercepted=bool(intercept_response))

    if intercept_response:
        return intercept_response
    if feasibility_result:
        return feasibility_result

    # --- Session / topic detection ---
    ctx.conversation_id = _get_or_create_conversation(ctx.session_data, ctx.user_id)

    question_lower = ctx.question.lower()
    ctx.question_topic = detect_topic(question_lower)
    ctx.current_subject = detect_specific_subject(question_lower)
    previous_topic = ctx.session_data.get('last_topic')
    previous_subject = ctx.session_data.get('last_subject')
    ctx.is_topic_change = is_significant_topic_change(
        previous_topic, ctx.question_topic, ctx.question,
        previous_subject=previous_subject, current_subject=ctx.current_subject
    )

    save_message(ctx.conversation_id, 'user', ctx.question)

    if ctx.is_topic_change:
        question_to_process = expand_vague_question(ctx.question)
    else:
        contextual_question = build_context_for_ai(ctx.conversation_id, ctx.question)
        question_to_process = expand_vague_question(contextual_question)

    ctx.timings['2_feasibility'] = time.time() - ctx.t0
    ctx.rewritten_query = rewrite_future.result()

    ctx.timings['3_rewrite'] = time.time() - ctx.t0
    ctx.trace.step("rewrite", rewritten=ctx.rewritten_query[:100])

    # --- Detection ---
    ctx.grass_type = detect_grass_type(question_to_process)
    ctx.region = detect_region(question_to_process)
    ctx.product_need = detect_product_need(question_to_process)
    ctx.question_topic = detect_topic(question_to_process.lower())
    ctx.trace.step("detect", topic=ctx.question_topic, grass=ctx.grass_type,
                    region=ctx.region, product_need=ctx.product_need)

    # Profile-based fallback
    user_profile = get_profile(ctx.user_id)
    if not ctx.grass_type and user_profile:
        if user_profile.get('turf_type') == 'golf_course':
            ctx.grass_type = user_profile.get('greens_grass') or user_profile.get('fairways_grass')
        else:
            ctx.grass_type = user_profile.get('primary_grass')
    if not ctx.region and user_profile and user_profile.get('region'):
        ctx.region = user_profile['region']
    if ctx.product_need and not ctx.question_topic:
        ctx.question_topic = 'chemical'

    # --- Search ---
    expanded_query = expand_query(ctx.rewritten_query)
    if ctx.grass_type:
        expanded_query += f" {ctx.grass_type}"
    if ctx.region:
        expanded_query += f" {ctx.region}"

    try:
        search_results = search_all_parallel(
            ctx.index, ctx.openai_client, ctx.rewritten_query, expanded_query,
            ctx.product_need, ctx.grass_type, Config.EMBEDDING_MODEL
        )
    except Exception as e:
        logger.error(f"Pinecone search failed — degrading gracefully: {e}")
        ctx.pinecone_failed = True
        search_results = {
            'general': {'matches': []},
            'product': {'matches': []},
            'timing': {'matches': []}
        }
        try:
            golden_fallback = SelfHealingLoop.get_relevant_golden_answers(
                query=ctx.question, category=ctx.question_topic
            )
            if golden_fallback:
                return {
                    'answer': golden_fallback[0]['answer'],
                    'sources': DEFAULT_SOURCES.copy(),
                    'confidence': {'score': 65, 'label': 'Moderate'},
                    'pinecone_degraded': True
                }
        except Exception:
            pass

    ctx.timings['4_search'] = time.time() - ctx.t0
    ctx.trace.step("vector_search",
                    general=len(search_results['general'].get('matches', [])),
                    product=len(search_results['product'].get('matches', [])),
                    timing=len(search_results['timing'].get('matches', [])))

    # --- Score + rerank ---
    all_matches = (
        search_results['general'].get('matches', []) +
        search_results['product'].get('matches', []) +
        search_results['timing'].get('matches', [])
    )
    scored_results = score_results(all_matches, ctx.question, ctx.grass_type, ctx.region, ctx.product_need)

    if scored_results:
        scored_results = rerank_results(ctx.rewritten_query, scored_results, top_k=20)

    try:
        scored_results = CircuitBreaker.filter_sources(scored_results)
    except Exception:
        pass

    try:
        scored_results = SourceQualityIntelligence.apply_source_adjustments(scored_results)
    except Exception:
        pass

    # Content freshness enforcement
    try:
        if FeatureFlags.is_enabled('content_freshness_enforcement') and scored_results:
            from intelligence_engine import _get_conn as _get_intel_conn
            fc = _get_intel_conn()
            stale_sources = {}
            rows = fc.execute('''
                SELECT source_id, status FROM content_freshness
                WHERE status IN ('stale', 'very_stale')
            ''').fetchall()
            fc.close()
            for r in rows:
                stale_sources[r['source_id']] = r['status']
            if stale_sources:
                for sr in scored_results:
                    src_id = str(sr.get('id', ''))
                    if src_id in stale_sources:
                        decay = 0.5 if stale_sources[src_id] == 'very_stale' else 0.7
                        sr['score'] = sr.get('score', 0) * decay
    except Exception:
        pass

    ctx.timings['5_rerank'] = time.time() - ctx.t0
    ctx.trace.step("score_rerank", scored_count=len(scored_results),
                    cross_encoder=is_cross_encoder_available())

    # --- Build context ---
    filtered_results = safety_filter_results(scored_results, ctx.question_topic, ctx.product_need)
    context, sources, images = build_context(filtered_results, SEARCH_FOLDERS)
    ctx.images = images

    prelim_confidence = 0
    if filtered_results:
        avg_score = sum(r.get('score', 0) for r in filtered_results[:5]) / min(5, len(filtered_results))
        prelim_confidence = min(100, avg_score * 100)

    # --- Web search fallback ---
    if should_trigger_web_search(search_results) or ctx.pinecone_failed:
        reformulated = _try_query_reformulation(
            ctx, search_results, scored_results, filtered_results, context, sources
        )
        if reformulated:
            context, sources, prelim_confidence = reformulated
        else:
            web_result = search_web_for_turf_info(ctx.openai_client, ctx.question, supplement_mode=False)
            if web_result:
                ctx.used_web_search = True
                context = web_result['context']
                sources = web_result['sources']
                ctx.images = []
    elif should_supplement_with_web_search(prelim_confidence):
        web_result = search_web_for_turf_info(ctx.openai_client, ctx.question, supplement_mode=True)
        if web_result:
            ctx.used_web_search = True
            ctx.supplement_mode = True
            context = context + "\n\n" + web_result['context']
            sources = sources + web_result['sources']

    # --- Knowledge enrichment ---
    if not ctx.used_web_search or ctx.supplement_mode:
        context = enrich_context_with_knowledge(ctx.question, context)

    # --- Photos ---
    if ctx.current_subject:
        photos = get_disease_photos(ctx.current_subject)
        if not photos:
            photos = get_weed_photos(ctx.current_subject)
        if not photos:
            photos = get_pest_photos(ctx.current_subject)
        if photos:
            ctx.images.extend(photos)

    # --- Weather ---
    user_location = body.get('location', {})
    lat, lon = user_location.get('lat'), user_location.get('lon')
    city, state = user_location.get('city'), user_location.get('state')
    weather_topics = {'chemical', 'fungicide', 'herbicide', 'insecticide', 'irrigation', 'cultural', 'diagnostic', 'disease'}
    if (lat and lon) or city:
        if ctx.question_topic in weather_topics or ctx.product_need:
            ctx.weather_data = get_weather_data(lat=lat, lon=lon, city=city, state=state)
            if ctx.weather_data:
                context = context + "\n\n" + get_weather_context(ctx.weather_data)

    # --- Truncation ---
    context = truncate_context(context)
    ctx.context = context

    # --- Source processing ---
    sources = [s for s in sources if s.get('url') is not None or s.get('note')]
    sources = deduplicate_sources(sources)

    if ctx.supplement_mode:
        db_src = [s for s in sources if not s.get('note', '').startswith('Web search')]
        web_src = [s for s in sources if s.get('note', '').startswith('Web search')]
        ctx.display_sources = filter_display_sources(db_src, SEARCH_FOLDERS) + web_src
    elif ctx.used_web_search:
        ctx.display_sources = sources
    else:
        ctx.display_sources = filter_display_sources(sources, SEARCH_FOLDERS)
    ctx.sources = sources

    if not ctx.display_sources:
        ctx.display_sources = DEFAULT_SOURCES.copy()

    # --- Build system prompt ---
    active_prompt_version = None
    try:
        if FeatureFlags.is_enabled('prompt_versioning'):
            active_prompt_version = PromptVersioning.get_active_version()
    except Exception:
        pass

    from prompts import build_system_prompt, build_reference_context
    if active_prompt_version and active_prompt_version.get('template'):
        ctx.system_prompt = active_prompt_version['template']
    else:
        ctx.system_prompt = build_system_prompt(ctx.question_topic, ctx.product_need)

    reference_context = build_reference_context(ctx.question_topic, ctx.product_need)
    if reference_context:
        ctx.context = "--- EXPERT REFERENCE DATA ---\n" + reference_context + "\n\n--- RETRIEVED SOURCES ---\n" + ctx.context

    profile_context = build_profile_context(ctx.user_id, question_topic=ctx.question_topic)
    if profile_context:
        ctx.system_prompt += (
            "\n\n--- USER CONTEXT ---\n" + profile_context +
            "\nUse this profile to tailor your recommendations. "
            "If the user's question specifies different grass/location, use theirs."
        )

    try:
        spray_context = build_spray_history_context(ctx.user_id)
        if spray_context:
            ctx.system_prompt += (
                "\n\n--- SPRAY HISTORY ---\n" + spray_context +
                "\nIMPORTANT: When recommending pesticides, check the spray history "
                "above. Do NOT recommend the same FRAC/HRAC/IRAC group that was "
                "recently used on the same area. Suggest rotation to a different "
                "mode of action group."
            )
    except Exception:
        pass

    # --- Turf Intelligence Context Injection ---
    try:
        # Seasonal/GDD context
        _user_state = detect_state(ctx.question.lower()) if hasattr(ctx, 'question') else None
        if not _user_state:
            _prof = get_profile(ctx.user_id)
            if _prof:
                _user_state = _prof.get('state') or _prof.get('region')
        seasonal_ctx = build_seasonal_context(state=_user_state, grass_type=ctx.grass_type)
        if seasonal_ctx:
            ctx.context = seasonal_ctx + "\n\n" + ctx.context
    except Exception:
        pass

    try:
        # FRAC rotation enforcement
        frac_ctx = build_frac_rotation_context(ctx.user_id, ctx.question, area=None)
        if frac_ctx:
            ctx.system_prompt += "\n\n" + frac_ctx
    except Exception:
        pass

    try:
        # Cross-module intelligence
        cross_ctx = build_cross_module_context(ctx.user_id, ctx.question)
        if cross_ctx:
            ctx.system_prompt += "\n\n" + cross_ctx
    except Exception:
        pass

    try:
        # Cultivar context
        _prof = get_profile(ctx.user_id) if ctx.user_id else None
        _cultivar = _prof.get('cultivars') if _prof else None
        cultivar_ctx = get_cultivar_context(ctx.grass_type, cultivar=_cultivar, disease=ctx.current_subject)
        if cultivar_ctx:
            ctx.context += "\n\n" + cultivar_ctx
    except Exception:
        pass

    try:
        # Cost context for product questions
        if ctx.product_need or ctx.question_topic == 'chemical':
            cost_ctx = build_cost_context(ctx.question)
            if cost_ctx:
                ctx.context += "\n\n" + cost_ctx
    except Exception:
        pass

    try:
        # Diagnostic context for diagnosis questions
        if ctx.question_topic == 'diagnostic' or (hasattr(ctx, 'question') and
                any(kw in ctx.question.lower() for kw in ['diagnose', 'identify', "what's wrong", 'what is wrong'])):
            diag_ctx = build_diagnostic_context(grass_type=ctx.grass_type)
            if diag_ctx:
                ctx.context += "\n\n" + diag_ctx
    except Exception:
        pass

    try:
        # Weather spray window context
        if ctx.weather_data and (ctx.product_need or ctx.question_topic in ('chemical', 'disease')):
            spray_window_ctx = build_weather_spray_context(ctx.weather_data)
            if spray_window_ctx:
                ctx.context += "\n\n" + spray_window_ctx
    except Exception:
        pass

    # --- Dynamic model routing ---
    try:
        _intent = get_query_intent(ctx.question)
        model_selection = select_model(ctx.question, intent=_intent, source_count=len(ctx.display_sources))
        ctx.llm_model = model_selection['model']
        ctx.llm_max_tokens = model_selection['max_tokens']
        ctx.llm_temperature = model_selection['temperature']
    except Exception:
        pass

    # Golden answers
    try:
        golden_answers = SelfHealingLoop.get_relevant_golden_answers(
            query=ctx.question, category=ctx.question_topic
        )
        if golden_answers:
            golden_ctx = "\n\n--- CURATED EXAMPLES (use these as reference for similar questions) ---"
            for ga in golden_answers:
                golden_ctx += f"\nQ: {ga['question']}\nA: {ga['answer']}\n"
            ctx.system_prompt += golden_ctx
            for ga in golden_answers:
                SelfHealingLoop.record_golden_answer_usage(ga['id'])
    except Exception:
        pass

    # --- Build messages ---
    if ctx.is_topic_change:
        ctx.messages = [
            {"role": "system", "content": ctx.system_prompt},
            {"role": "user", "content": build_user_prompt(ctx.context, ctx.question)}
        ]
    else:
        ctx.messages = build_messages_with_history(
            ctx.conversation_id, ctx.system_prompt, ctx.context, ctx.question
        )

    ctx.timings['6_pre_llm'] = time.time() - ctx.t0
    ctx.trace.step("pre_llm", context_len=len(ctx.context), source_count=len(ctx.sources),
                    web_search=ctx.used_web_search)

    # --- A/B testing ---
    try:
        if FeatureFlags.is_enabled('ab_testing') and ctx.user_id:
            ctx.ab_assignment = ABTestingEngine.get_ab_assignment(ctx.question, ctx.user_id)
            if ctx.ab_assignment and ctx.ab_assignment.get('strategy'):
                strategy = ctx.ab_assignment['strategy']
                if strategy == 'concise':
                    ctx.llm_max_tokens = min(500, ctx.llm_max_tokens)
                elif strategy == 'detailed':
                    ctx.llm_max_tokens = max(1500, ctx.llm_max_tokens)
                elif strategy == 'creative':
                    ctx.llm_temperature = 0.5
                elif strategy == 'conservative':
                    ctx.llm_temperature = 0.1
    except Exception:
        pass

    # --- Budget enforcement ---
    try:
        budget = PipelineAnalytics.check_budget()
        budget_action = budget.get('action', 'none')
        if budget_action == 'budget_exceeded':
            golden_hit = SelfHealingLoop.get_relevant_golden_answers(
                query=ctx.question, category=ctx.question_topic
            )
            if golden_hit:
                return _build_final_response(ctx, golden_hit[0]['answer'],
                                             {'prompt_tokens': 0, 'completion_tokens': 0, 'model': 'cached'})
            return {
                'answer': "The system has reached its daily cost budget. Please try again tomorrow.",
                'sources': [], 'confidence': {'score': 0, 'label': 'Budget Exceeded'}
            }
        elif budget_action == 'fallback_model':
            ctx.llm_model = 'gpt-4o-mini'
    except Exception:
        pass

    return None  # Proceed to LLM call


# ---------------------------------------------------------------------------
# LLM call + post-processing
# ---------------------------------------------------------------------------

def run_llm_and_postprocess(ctx: PipelineContext) -> dict:
    """Execute the LLM call and all post-processing (grounding, hallucination, confidence)."""
    # LLM call with retry
    assistant_response = ""
    token_usage = {'prompt_tokens': 0, 'completion_tokens': 0, 'model': ctx.llm_model}

    for attempt in range(2):
        try:
            timeout = 20 if attempt == 0 else 30
            answer = ctx.openai_client.chat.completions.create(
                model=ctx.llm_model,
                messages=ctx.messages,
                max_tokens=ctx.llm_max_tokens,
                temperature=ctx.llm_temperature,
                timeout=timeout
            )
            assistant_response = answer.choices[0].message.content or ""
            if not assistant_response:
                assistant_response = "I wasn't able to generate a response. Please try rephrasing your question."
            token_usage = {
                'prompt_tokens': answer.usage.prompt_tokens if answer.usage else 0,
                'completion_tokens': answer.usage.completion_tokens if answer.usage else 0,
                'model': ctx.llm_model
            }
            break
        except Exception as e:
            if attempt == 1:
                logger.error(f"LLM call failed after 2 attempts: {e}")
                assistant_response = "I'm having trouble generating a response right now. Please try again in a moment."

    ctx.timings['7_llm_answer'] = time.time() - ctx.t0
    ctx.trace.step("llm_answer", model=ctx.llm_model, tokens=token_usage.get('completion_tokens', 0))

    return _build_final_response(ctx, assistant_response, token_usage)


def _build_final_response(ctx: PipelineContext, assistant_response: str, token_usage: dict) -> dict:
    """Run post-processing checks and build the final response dict."""
    # Parallel: grounding check + local hallucination filter + validation
    with ThreadPoolExecutor(max_workers=2) as executor:
        grounding_future = executor.submit(
            check_answer_grounding, ctx.openai_client, assistant_response,
            ctx.context, ctx.question, "gpt-4o-mini"
        )
        hallucination_result = filter_hallucinations(
            answer=assistant_response, question=ctx.question,
            context=ctx.context, sources=ctx.sources, openai_client=ctx.openai_client
        )
        if hallucination_result['was_modified']:
            assistant_response = hallucination_result['filtered_answer']

        assistant_response, validation_result = apply_validation(assistant_response, ctx.question)
        grounding_result = grounding_future.result()

    assistant_response = add_grounding_warning(assistant_response, grounding_result)

    ctx.timings['8_grounding+checks'] = time.time() - ctx.t0
    ctx.trace.step("post_checks",
                    grounding_supported=grounding_result.get('supported_ratio', 0),
                    hallucination_issues=len(hallucination_result.get('issues_found', [])),
                    validation_issues=len(validation_result.get('issues', [])))

    # --- Confidence ---
    base_confidence = calculate_confidence_score(ctx.sources, assistant_response, ctx.question)
    confidence = calculate_grounding_confidence(grounding_result, base_confidence)
    hall_penalty = min(hallucination_result.get('confidence_penalty', 0) / 100, 0.20)
    val_penalty = min(validation_result.get('confidence_penalty', 0) / 100, 0.20)
    confidence = max(0, confidence * (1 - hall_penalty) * (1 - val_penalty))

    try:
        confidence = ConfidenceCalibration.get_calibration_adjustment(confidence, ctx.question_topic)
        confidence = max(0, min(100, confidence))
    except Exception:
        pass

    confidence_label = get_confidence_label(confidence)

    # --- Save to conversation history ---
    save_message(
        ctx.conversation_id, 'assistant', assistant_response,
        sources=ctx.display_sources[:MAX_SOURCES], confidence_score=confidence
    )

    needs_review = (
        confidence < 70 or
        not grounding_result.get('grounded', True) or
        len(grounding_result.get('unsupported_claims', [])) > 1 or
        not ctx.sources
    )

    query_id = save_query(
        question=ctx.question, ai_answer=assistant_response,
        sources=ctx.display_sources[:MAX_SOURCES],
        confidence=confidence, needs_review=needs_review
    )

    # Intelligence subsystems
    try:
        process_answer_intelligence(
            query_id=query_id or 0, question=ctx.question,
            answer=assistant_response, confidence=confidence,
            sources=ctx.display_sources[:MAX_SOURCES],
            category=ctx.question_topic, user_id=str(ctx.user_id or ''),
            grounding_result=grounding_result,
            hallucination_result=hallucination_result,
            timings=ctx.timings, token_usage=token_usage,
            ab_assignment=ctx.ab_assignment
        )
    except Exception:
        pass

    # --- Domain-specific validation ---
    try:
        domain_validation = validate_domain_specific(assistant_response)
        if domain_validation.get('issues'):
            assistant_response += "\n\n⚠️ **Safety Note**: " + "; ".join(domain_validation['issues'])
        if domain_validation.get('warnings'):
            assistant_response += "\n\n📋 **Note**: " + "; ".join(domain_validation['warnings'])
    except Exception:
        domain_validation = {'valid': True, 'warnings': [], 'issues': []}

    # --- Follow-up suggestions ---
    follow_ups = []
    try:
        _intent = get_query_intent(ctx.question) if hasattr(ctx, 'question') else None
        follow_ups = generate_follow_up_suggestions(
            ctx.question, assistant_response,
            intent=_intent, disease=ctx.current_subject, product=ctx.product_need
        )
    except Exception:
        pass

    # --- Knowledge gap assessment ---
    knowledge_gap_msg = None
    try:
        gap_result = assess_knowledge_gaps(
            ctx.sources, confidence, ctx.question, context=ctx.context
        )
        if gap_result.get('has_gap'):
            knowledge_gap_msg = gap_result.get('message', '')
            log_knowledge_gap(gap_result)
    except Exception:
        pass

    # --- Predictive alerts ---
    alerts = []
    try:
        _user_state = detect_state(ctx.question.lower()) if hasattr(ctx, 'question') else None
        if not _user_state:
            _prof = get_profile(ctx.user_id) if ctx.user_id else None
            if _prof:
                _user_state = _prof.get('state') or _prof.get('region')
        alerts = generate_predictive_alerts(
            ctx.user_id, weather_data=ctx.weather_data,
            state=_user_state, grass_type=ctx.grass_type
        )
    except Exception:
        pass

    response_data = {
        'answer': assistant_response,
        'sources': ctx.display_sources[:MAX_SOURCES],
        'images': ctx.images,
        'confidence': {'score': confidence, 'label': confidence_label},
        'grounding': {
            'verified': grounding_result.get('grounded', True),
            'issues': grounding_result.get('unsupported_claims', [])
        },
        'needs_review': needs_review,
        'follow_ups': follow_ups,
    }

    if knowledge_gap_msg:
        response_data['knowledge_gap'] = knowledge_gap_msg
    if alerts:
        response_data['alerts'] = alerts

    # Product recommendations from answer
    try:
        mentioned_names = extract_product_names(assistant_response)
        if mentioned_names:
            rec_products = []
            seen_ids = set()
            for name in mentioned_names[:8]:
                matches = search_products(name, category=None, form_type=None)
                if matches:
                    p = matches[0]
                    pid = p.get('id', p.get('product_id', ''))
                    if pid and pid not in seen_ids:
                        seen_ids.add(pid)
                        rec_products.append({'id': pid, 'name': p.get('display_name', p.get('name', name))})
            if rec_products:
                response_data['recommended_products'] = rec_products[:5]
    except Exception:
        pass

    if ctx.used_web_search:
        response_data['web_search_used'] = True
        response_data['web_search_disclaimer'] = format_web_search_disclaimer()

    if ctx.weather_data:
        response_data['weather'] = {
            'location': ctx.weather_data.get('location'),
            'summary': format_weather_for_response(ctx.weather_data),
            'warnings': get_weather_warnings(ctx.weather_data)
        }

    ctx.timings['10_total'] = time.time() - ctx.t0
    ctx.trace.finish(confidence=confidence, source_count=len(ctx.display_sources),
                      web_search=ctx.used_web_search, model=ctx.llm_model)
    response_data['trace_id'] = ctx.trace.trace_id

    # Log timing
    prev = 0
    parts = []
    for key in sorted(ctx.timings.keys()):
        elapsed = ctx.timings[key]
        parts.append(f"{key}={elapsed - prev:.1f}s")
        prev = elapsed
    logger.info(f"PIPELINE TIMING [{ctx.timings['10_total']:.1f}s total]: {' | '.join(parts)}")

    # Cache good responses
    if confidence >= 50 and not ctx.used_web_search:
        answer_cache = get_answer_cache()
        answer_cache.set(ctx.question, response_data, course_id=ctx.user_id)

    return response_data


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_or_create_conversation(session_data, user_id):
    """Get existing conversation ID or create new session."""
    if 'session_id' not in session_data:
        session_id, conversation_id = create_session(user_id=user_id)
        session_data['session_id'] = session_id
        session_data['conversation_id'] = conversation_id
    return session_data['conversation_id']


def _try_query_reformulation(ctx, search_results, scored_results, filtered_results, context, sources):
    """Try reformulating the query before falling back to web search. Returns (context, sources, confidence) or None."""
    if ctx.pinecone_failed:
        return None
    try:
        resp = ctx.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": (
                "Rephrase this turfgrass question using different terminology and common synonyms "
                "to improve search results. Return ONLY the rephrased question.\n\n"
                f"Question: {ctx.question}"
            )}],
            max_tokens=150, temperature=0.4, timeout=10
        )
        reformulated = resp.choices[0].message.content.strip()
        if not reformulated or reformulated.lower().strip() == ctx.question.lower().strip():
            return None

        expanded = expand_query(reformulated)
        retry_results = search_all_parallel(
            ctx.index, ctx.openai_client, reformulated, expanded,
            ctx.product_need, ctx.grass_type, Config.EMBEDDING_MODEL
        )
        retry_matches = (
            retry_results['general'].get('matches', []) +
            retry_results['product'].get('matches', []) +
            retry_results['timing'].get('matches', [])
        )
        if not retry_matches:
            return None

        scored = score_results(retry_matches, ctx.question, ctx.grass_type, ctx.region, ctx.product_need)
        if scored:
            scored = rerank_results(ctx.rewritten_query, scored, top_k=20)
        filtered = safety_filter_results(scored, ctx.question_topic, ctx.product_need)
        new_context, new_sources, new_images = build_context(filtered, SEARCH_FOLDERS)
        ctx.images = new_images

        new_confidence = 0
        if filtered:
            avg = sum(r.get('score', 0) for r in filtered[:5]) / min(5, len(filtered))
            new_confidence = min(100, avg * 100)

        return (new_context, new_sources, new_confidence)
    except Exception:
        return None
