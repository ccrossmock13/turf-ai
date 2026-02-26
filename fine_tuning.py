"""
Fine-tuning Pipeline for Greenside AI
Closes the feedback loop: approved corrections → fine-tuned model → better answers
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
import openai
from config import Config
from db import get_db, FEEDBACK_DB

logger = logging.getLogger(__name__)

# Minimum examples needed for fine-tuning
MIN_EXAMPLES_FOR_TRAINING = 50

# Fine-tuning configuration
FINE_TUNE_CONFIG = {
    'base_model': 'gpt-4o-mini-2024-07-18',  # Cost-effective base for fine-tuning
    'n_epochs': 3,
    'batch_size': 'auto',
    'learning_rate_multiplier': 'auto',
}


def get_openai_client():
    """Get OpenAI client."""
    return openai.OpenAI(api_key=Config.OPENAI_API_KEY)


def prepare_training_data(output_path: str = 'data/training_data.jsonl') -> Optional[Dict]:
    """
    Prepare training data from approved feedback.
    Returns info about the prepared data or None if insufficient examples.
    """
    from feedback_system import get_training_examples

    examples = get_training_examples(unused_only=True)

    if len(examples) < MIN_EXAMPLES_FOR_TRAINING:
        return {
            'success': False,
            'error': f'Need at least {MIN_EXAMPLES_FOR_TRAINING} examples, have {len(examples)}',
            'current_count': len(examples),
            'needed': MIN_EXAMPLES_FOR_TRAINING
        }

    # Build training file in OpenAI chat format
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Use the actual production system prompt for training consistency
    from prompts import build_system_prompt
    production_system_prompt = build_system_prompt()

    training_data = []
    for ex in examples:
        # Create training example with the real system prompt
        training_obj = {
            "messages": [
                {"role": "system", "content": production_system_prompt},
                {"role": "user", "content": ex['question']},
                {"role": "assistant", "content": ex['ideal_answer']}
            ]
        }
        training_data.append(training_obj)

    # Write JSONL file
    with open(output_path, 'w') as f:
        for item in training_data:
            f.write(json.dumps(item) + '\n')

    logger.info(f"Prepared {len(training_data)} training examples at {output_path}")

    return {
        'success': True,
        'path': output_path,
        'num_examples': len(training_data),
        'prepared_at': datetime.now().isoformat()
    }


def upload_training_file(file_path: str) -> Optional[Dict]:
    """Upload training file to OpenAI."""
    client = get_openai_client()

    try:
        with open(file_path, 'rb') as f:
            response = client.files.create(
                file=f,
                purpose='fine-tune'
            )

        logger.info(f"Uploaded training file: {response.id}")

        return {
            'success': True,
            'file_id': response.id,
            'filename': response.filename,
            'bytes': response.bytes,
            'created_at': datetime.fromtimestamp(response.created_at).isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to upload training file: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def start_fine_tuning_job(
    training_file_id: str,
    suffix: str = None,
    validation_file_id: str = None
) -> Optional[Dict]:
    """Start a fine-tuning job."""
    client = get_openai_client()

    # Generate suffix if not provided
    if not suffix:
        suffix = f"greenside-{datetime.now().strftime('%Y%m%d')}"

    try:
        # Create fine-tuning job
        job = client.fine_tuning.jobs.create(
            training_file=training_file_id,
            model=FINE_TUNE_CONFIG['base_model'],
            suffix=suffix,
            hyperparameters={
                'n_epochs': FINE_TUNE_CONFIG['n_epochs']
            }
        )

        logger.info(f"Started fine-tuning job: {job.id}")

        # Record in database
        from feedback_system import create_training_run, mark_examples_used
        create_training_run(job.id, job.trained_tokens or 0, f"Model: {suffix}")
        mark_examples_used(job.id)

        return {
            'success': True,
            'job_id': job.id,
            'status': job.status,
            'model': job.model,
            'suffix': suffix,
            'created_at': datetime.fromtimestamp(job.created_at).isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to start fine-tuning job: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def get_fine_tuning_status(job_id: str) -> Optional[Dict]:
    """Get status of a fine-tuning job."""
    client = get_openai_client()

    try:
        job = client.fine_tuning.jobs.retrieve(job_id)

        result = {
            'job_id': job.id,
            'status': job.status,
            'model': job.model,
            'created_at': datetime.fromtimestamp(job.created_at).isoformat(),
            'trained_tokens': job.trained_tokens,
            'error': job.error.message if job.error else None
        }

        if job.finished_at:
            result['finished_at'] = datetime.fromtimestamp(job.finished_at).isoformat()

        if job.fine_tuned_model:
            result['fine_tuned_model'] = job.fine_tuned_model

            # Update database
            from feedback_system import update_training_run
            update_training_run(job_id, 'completed', job.fine_tuned_model)

        return result

    except Exception as e:
        logger.error(f"Failed to get fine-tuning status: {e}")
        return {
            'error': str(e)
        }


def list_fine_tuning_jobs(limit: int = 10) -> List[Dict]:
    """List recent fine-tuning jobs."""
    client = get_openai_client()

    try:
        jobs = client.fine_tuning.jobs.list(limit=limit)

        return [{
            'job_id': job.id,
            'status': job.status,
            'model': job.model,
            'fine_tuned_model': job.fine_tuned_model,
            'created_at': datetime.fromtimestamp(job.created_at).isoformat(),
            'finished_at': datetime.fromtimestamp(job.finished_at).isoformat() if job.finished_at else None,
            'error': job.error.message if job.error else None
        } for job in jobs.data]

    except Exception as e:
        logger.error(f"Failed to list fine-tuning jobs: {e}")
        return []


def get_active_fine_tuned_model() -> Optional[str]:
    """Get the most recent successfully fine-tuned model."""
    jobs = list_fine_tuning_jobs(limit=20)

    for job in jobs:
        if job['status'] == 'succeeded' and job.get('fine_tuned_model'):
            return job['fine_tuned_model']

    return None


def run_full_fine_tuning_pipeline() -> Dict:
    """
    Run the complete fine-tuning pipeline:
    1. Prepare training data from approved feedback
    2. Upload to OpenAI
    3. Start fine-tuning job
    """
    results = {
        'started_at': datetime.now().isoformat(),
        'steps': []
    }

    # Step 1: Prepare data
    logger.info("Step 1: Preparing training data...")
    prep_result = prepare_training_data()
    results['steps'].append({'step': 'prepare_data', 'result': prep_result})

    if not prep_result.get('success'):
        results['success'] = False
        results['error'] = prep_result.get('error', 'Failed to prepare data')
        return results

    # Step 2: Upload file
    logger.info("Step 2: Uploading training file...")
    upload_result = upload_training_file(prep_result['path'])
    results['steps'].append({'step': 'upload_file', 'result': upload_result})

    if not upload_result.get('success'):
        results['success'] = False
        results['error'] = upload_result.get('error', 'Failed to upload file')
        return results

    # Step 3: Start fine-tuning
    logger.info("Step 3: Starting fine-tuning job...")
    job_result = start_fine_tuning_job(upload_result['file_id'])
    results['steps'].append({'step': 'start_job', 'result': job_result})

    if not job_result.get('success'):
        results['success'] = False
        results['error'] = job_result.get('error', 'Failed to start job')
        return results

    results['success'] = True
    results['job_id'] = job_result['job_id']
    results['message'] = f"Fine-tuning started! Job ID: {job_result['job_id']}"

    return results


# =============================================================================
# SOURCE QUALITY TRACKING
# =============================================================================

def track_source_quality(question: str, sources: List[Dict], rating: str, feedback_id: int):
    """
    Track source quality based on user feedback.
    Negative feedback on an answer = potential issue with sources used.
    """
    with get_db(FEEDBACK_DB) as conn:
        # Create source_quality table if needed
        conn.execute('''
            CREATE TABLE IF NOT EXISTS source_quality (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL,
                source_url TEXT,
                positive_count INTEGER DEFAULT 0,
                negative_count INTEGER DEFAULT 0,
                quality_score REAL DEFAULT 0.5,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_url)
            )
        ''')

        for source in sources:
            url = source.get('url', '')
            name = source.get('title', source.get('name', 'Unknown'))

            if not url:
                continue

            # Upsert source record
            conn.execute('''
                INSERT INTO source_quality (source_name, source_url, positive_count, negative_count)
                VALUES (?, ?, 0, 0)
                ON CONFLICT(source_url) DO NOTHING
            ''', (name, url))

            # Update counts based on rating
            if rating == 'positive':
                conn.execute('''
                    UPDATE source_quality
                    SET positive_count = positive_count + 1,
                        quality_score = (positive_count + 1.0) / (positive_count + negative_count + 2.0),
                        last_updated = CURRENT_TIMESTAMP
                    WHERE source_url = ?
                ''', (url,))
            elif rating == 'negative':
                conn.execute('''
                    UPDATE source_quality
                    SET negative_count = negative_count + 1,
                        quality_score = (positive_count + 1.0) / (positive_count + negative_count + 2.0),
                        last_updated = CURRENT_TIMESTAMP
                    WHERE source_url = ?
                ''', (url,))


def get_source_quality_scores() -> Dict[str, float]:
    """Get quality scores for all tracked sources."""
    try:
        with get_db(FEEDBACK_DB) as conn:
            cursor = conn.execute('''
                SELECT source_url, quality_score, positive_count, negative_count
                FROM source_quality
                WHERE positive_count + negative_count >= 3
                ORDER BY quality_score DESC
            ''')

            results = {}
            for row in cursor.fetchall():
                results[row[0]] = {
                    'score': row[1],
                    'positive': row[2],
                    'negative': row[3]
                }

            return results

    except Exception:
        return {}


def get_low_quality_sources(threshold: float = 0.4) -> List[Dict]:
    """Get sources with low quality scores (candidates for removal/review)."""
    try:
        with get_db(FEEDBACK_DB) as conn:
            cursor = conn.execute('''
                SELECT source_name, source_url, quality_score, positive_count, negative_count
                FROM source_quality
                WHERE quality_score < ? AND (positive_count + negative_count) >= 3
                ORDER BY quality_score ASC
            ''', (threshold,))

            return [{
                'name': row[0],
                'url': row[1],
                'score': row[2],
                'positive': row[3],
                'negative': row[4]
            } for row in cursor.fetchall()]

    except Exception:
        return []


def apply_source_quality_boost(results: List[Dict]) -> List[Dict]:
    """
    Apply quality score adjustments to search results.
    Good sources get boosted, bad sources get penalized.
    """
    quality_scores = get_source_quality_scores()

    if not quality_scores:
        return results

    for result in results:
        url = result.get('metadata', {}).get('source', '') or result.get('source', '')

        if url in quality_scores:
            quality = quality_scores[url]
            score_adjustment = quality['score']

            # Apply adjustment: scores range 0-1, neutral at 0.5
            # Good sources (>0.5) get boosted, bad sources (<0.5) get penalized
            if 'score' in result:
                original = result['score']
                # Adjustment factor: 0.8 to 1.2 based on quality
                factor = 0.8 + (score_adjustment * 0.4)
                result['score'] = original * factor
                result['quality_adjusted'] = True

    return results


# =============================================================================
# EVALUATION SYSTEM
# =============================================================================

# Sample evaluation questions with expected topics/keywords
EVAL_QUESTIONS = [
    {
        'question': 'What fungicide should I use for dollar spot on bentgrass greens?',
        'expected_keywords': ['dollar spot', 'fungicide', 'bentgrass'],
        'expected_products': ['heritage', 'banner', 'daconil', 'propiconazole'],
        'category': 'disease_management'
    },
    {
        'question': 'When should I apply pre-emergent herbicide in the transition zone?',
        'expected_keywords': ['pre-emergent', 'soil temperature', '55'],
        'expected_products': ['prodiamine', 'dimension', 'barricade'],
        'category': 'weed_control'
    },
    {
        'question': 'What is the recommended nitrogen rate for bermudagrass fairways?',
        'expected_keywords': ['nitrogen', 'bermuda', 'fairway', 'pound'],
        'expected_products': [],
        'category': 'fertility'
    },
    {
        'question': 'How do I treat pythium blight?',
        'expected_keywords': ['pythium', 'fungicide', 'drainage', 'moisture'],
        'expected_products': ['subdue', 'mefenoxam', 'segway'],
        'category': 'disease_management'
    },
    {
        'question': 'What causes brown patch and how do I prevent it?',
        'expected_keywords': ['brown patch', 'rhizoctonia', 'nitrogen', 'humidity'],
        'expected_products': [],
        'category': 'disease_management'
    },
]


def run_evaluation(custom_questions: List[Dict] = None, use_internal: bool = True) -> Dict:
    """
    Run evaluation against test questions.
    Returns scores and detailed results.

    Args:
        custom_questions: Optional list of question dicts to evaluate
        use_internal: If True, use Flask test client (works on Render).
                      If False, use HTTP requests (requires separate server).
    """
    questions = custom_questions or EVAL_QUESTIONS
    results = []

    if use_internal:
        # Use Flask test client - works internally on Render
        from app import app
        client = app.test_client()

        for q in questions:
            try:
                response = client.post(
                    '/ask',
                    json={'question': q['question']},
                    content_type='application/json'
                )

                if response.status_code != 200:
                    results.append({
                        'question': q['question'],
                        'success': False,
                        'error': f'API error: {response.status_code}'
                    })
                    continue

                data = response.get_json()
                answer = data.get('answer', '').lower()
                confidence = data.get('confidence', {}).get('score', 0)

                # Score the response
                keyword_hits = sum(1 for kw in q.get('expected_keywords', [])
                                  if kw.lower() in answer)
                keyword_total = len(q.get('expected_keywords', []))
                keyword_score = keyword_hits / keyword_total if keyword_total > 0 else 1.0

                product_hits = sum(1 for p in q.get('expected_products', [])
                                  if p.lower() in answer)
                product_total = len(q.get('expected_products', []))
                product_score = product_hits / max(product_total, 1)

                # Combined score
                overall_score = (keyword_score * 0.6) + (product_score * 0.2) + (confidence / 100 * 0.2)

                results.append({
                    'question': q['question'],
                    'category': q.get('category', 'general'),
                    'success': True,
                    'answer_preview': answer[:200] + '...' if len(answer) > 200 else answer,
                    'confidence': confidence,
                    'keyword_score': round(keyword_score * 100, 1),
                    'product_score': round(product_score * 100, 1),
                    'overall_score': round(overall_score * 100, 1),
                    'keywords_found': keyword_hits,
                    'keywords_expected': keyword_total,
                    'products_found': product_hits,
                    'products_expected': product_total
                })

            except Exception as e:
                results.append({
                    'question': q['question'],
                    'success': False,
                    'error': str(e)
                })
    else:
        # Use HTTP requests - requires running server
        import requests

        for q in questions:
            try:
                # Call the API
                response = requests.post(
                    'http://localhost:5000/ask',
                    json={'question': q['question']},
                    timeout=60
                )

                if response.status_code != 200:
                    results.append({
                        'question': q['question'],
                        'success': False,
                        'error': f'API error: {response.status_code}'
                    })
                    continue

                data = response.json()
                answer = data.get('answer', '').lower()
                confidence = data.get('confidence', {}).get('score', 0)

                # Score the response
                keyword_hits = sum(1 for kw in q.get('expected_keywords', [])
                                  if kw.lower() in answer)
                keyword_total = len(q.get('expected_keywords', []))
                keyword_score = keyword_hits / keyword_total if keyword_total > 0 else 1.0

                product_hits = sum(1 for p in q.get('expected_products', [])
                                  if p.lower() in answer)
                product_total = len(q.get('expected_products', []))
                product_score = product_hits / max(product_total, 1)

                # Combined score
                overall_score = (keyword_score * 0.6) + (product_score * 0.2) + (confidence / 100 * 0.2)

                results.append({
                    'question': q['question'],
                    'category': q.get('category', 'general'),
                    'success': True,
                    'answer_preview': answer[:200] + '...' if len(answer) > 200 else answer,
                    'confidence': confidence,
                    'keyword_score': round(keyword_score * 100, 1),
                    'product_score': round(product_score * 100, 1),
                    'overall_score': round(overall_score * 100, 1),
                    'keywords_found': keyword_hits,
                    'keywords_expected': keyword_total,
                    'products_found': product_hits,
                    'products_expected': product_total
                })

            except Exception as e:
                results.append({
                    'question': q['question'],
                    'success': False,
                    'error': str(e)
                })

    # Calculate aggregate scores
    successful = [r for r in results if r.get('success')]

    summary = {
        'total_questions': len(questions),
        'successful': len(successful),
        'failed': len(questions) - len(successful),
        'avg_confidence': round(sum(r['confidence'] for r in successful) / len(successful), 1) if successful else 0,
        'avg_keyword_score': round(sum(r['keyword_score'] for r in successful) / len(successful), 1) if successful else 0,
        'avg_product_score': round(sum(r['product_score'] for r in successful) / len(successful), 1) if successful else 0,
        'avg_overall_score': round(sum(r['overall_score'] for r in successful) / len(successful), 1) if successful else 0,
        'evaluated_at': datetime.now().isoformat()
    }

    # Category breakdown
    categories = {}
    for r in successful:
        cat = r.get('category', 'general')
        if cat not in categories:
            categories[cat] = {'count': 0, 'total_score': 0}
        categories[cat]['count'] += 1
        categories[cat]['total_score'] += r['overall_score']

    for cat in categories:
        categories[cat]['avg_score'] = round(
            categories[cat]['total_score'] / categories[cat]['count'], 1
        )

    summary['by_category'] = categories

    return {
        'summary': summary,
        'results': results
    }


def save_eval_results(eval_results: Dict) -> int:
    """Save evaluation results to database for tracking over time."""
    with get_db(FEEDBACK_DB) as conn:
        # Create eval_runs table if needed
        conn.execute('''
            CREATE TABLE IF NOT EXISTS eval_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_questions INTEGER,
                avg_overall_score REAL,
                avg_confidence REAL,
                avg_keyword_score REAL,
                details TEXT
            )
        ''')

        summary = eval_results.get('summary', {})

        cursor = conn.execute('''
            INSERT INTO eval_runs (total_questions, avg_overall_score, avg_confidence, avg_keyword_score, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            summary.get('total_questions', 0),
            summary.get('avg_overall_score', 0),
            summary.get('avg_confidence', 0),
            summary.get('avg_keyword_score', 0),
            json.dumps(eval_results)
        ))

        run_id = cursor.lastrowid
        return run_id


def get_eval_history(limit: int = 10) -> List[Dict]:
    """Get evaluation run history."""
    try:
        with get_db(FEEDBACK_DB) as conn:
            cursor = conn.execute('''
                SELECT id, run_date, total_questions, avg_overall_score, avg_confidence
                FROM eval_runs
                ORDER BY run_date DESC
                LIMIT ?
            ''', (limit,))

            return [{
                'id': row[0],
                'run_date': row[1],
                'total_questions': row[2],
                'avg_overall_score': row[3],
                'avg_confidence': row[4]
            } for row in cursor.fetchall()]

    except Exception:
        return []
