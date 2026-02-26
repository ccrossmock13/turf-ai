"""
Feedback & Learning System
Collects user corrections and builds training data for continuous improvement
"""

import os
from datetime import datetime
import json
import logging

from db import get_db, is_postgres, add_column, FEEDBACK_DB

# Backward compat alias (fine_tuning.py imports DB_PATH)
DB_PATH = FEEDBACK_DB



def save_feedback(question, ai_answer, rating, correction=None, sources=None, confidence=None):
    """Save user feedback (when user rates)"""
    with get_db(FEEDBACK_DB) as conn:
        sources_json = json.dumps(sources) if sources else None

        cursor = conn.execute('''
            INSERT INTO feedback
            (question, ai_answer, user_rating, user_correction, sources, confidence_score)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (question, ai_answer, rating, correction, sources_json, confidence))

        feedback_id = cursor.lastrowid

    return feedback_id


def save_query(question, ai_answer, sources=None, confidence=None, topic=None, needs_review=False):
    """Save every query automatically (before user rates)"""
    try:
        with get_db(FEEDBACK_DB) as conn:
            sources_json = json.dumps(sources) if sources else None

            # Ensure needs_review column exists
            add_column(conn, 'feedback', 'needs_review', 'BOOLEAN DEFAULT 0')

            # Use 'unrated' as the default rating
            cursor = conn.execute('''
                INSERT INTO feedback
                (question, ai_answer, user_rating, sources, confidence_score, needs_review)
                VALUES (?, ?, 'unrated', ?, ?, ?)
            ''', (question, ai_answer, sources_json, confidence, 1 if needs_review else 0))

            query_id = cursor.lastrowid

        return query_id
    except Exception as e:
        logging.getLogger(__name__).error(f"DB error in save_query: {e}")
        return None


def get_queries_needing_review(limit=100):
    """Get queries flagged for human review (confidence < 70% or grounding issues)"""
    with get_db(FEEDBACK_DB) as conn:
        # Check if needs_review column exists
        try:
            cursor = conn.execute('''
                SELECT id, question, ai_answer, confidence_score, sources, timestamp
                FROM feedback
                WHERE needs_review = 1 AND reviewed = 0
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
        except Exception:
            # Fallback to confidence-based query if column doesn't exist
            cursor = conn.execute('''
                SELECT id, question, ai_answer, confidence_score, sources, timestamp
                FROM feedback
                WHERE confidence_score < 70 AND reviewed = 0
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))

        results = cursor.fetchall()

    queries = []
    for row in results:
        queries.append({
            'id': row[0],
            'question': row[1],
            'ai_answer': row[2],
            'confidence': row[3],
            'sources': json.loads(row[4]) if row[4] else [],
            'timestamp': row[5]
        })

    return queries


def update_query_rating(question, rating, correction=None):
    """Update an existing query with user's rating"""
    with get_db(FEEDBACK_DB) as conn:
        # Find the most recent query with this question
        conn.execute('''
            UPDATE feedback
            SET user_rating = ?, user_correction = ?
            WHERE id = (
                SELECT id FROM feedback
                WHERE question = ? AND user_rating = 'unrated'
                ORDER BY timestamp DESC LIMIT 1
            )
        ''', (rating, correction, question))


def get_negative_feedback(limit=50, unreviewed_only=True):
    """Get feedback that needs review"""
    with get_db(FEEDBACK_DB) as conn:
        query = '''
            SELECT id, question, ai_answer, user_correction, timestamp
            FROM feedback
            WHERE user_rating = 'negative'
        '''

        if unreviewed_only:
            query += ' AND reviewed = 0'

        query += ' ORDER BY timestamp DESC LIMIT ?'

        cursor = conn.execute(query, (limit,))
        results = cursor.fetchall()

    feedback_items = []
    for row in results:
        feedback_items.append({
            'id': row[0],
            'question': row[1],
            'ai_answer': row[2],
            'user_correction': row[3],
            'timestamp': row[4]
        })

    return feedback_items


def approve_for_training(feedback_id, ideal_answer):
    """Approve feedback and create training example"""
    with get_db(FEEDBACK_DB) as conn:
        # Get original question
        cursor = conn.execute('SELECT question FROM feedback WHERE id = ?', (feedback_id,))
        question = cursor.fetchone()[0]

        # Mark feedback as reviewed and approved
        conn.execute('''
            UPDATE feedback
            SET reviewed = 1, approved_for_training = 1
            WHERE id = ?
        ''', (feedback_id,))

        # Create training example
        conn.execute('''
            INSERT INTO training_examples (feedback_id, question, ideal_answer)
            VALUES (?, ?, ?)
        ''', (feedback_id, question, ideal_answer))


def reject_feedback(feedback_id, notes=None):
    """Mark feedback as reviewed but not approved"""
    with get_db(FEEDBACK_DB) as conn:
        conn.execute('''
            UPDATE feedback
            SET reviewed = 1, approved_for_training = 0, notes = ?
            WHERE id = ?
        ''', (notes, feedback_id))


def get_training_examples(unused_only=True, limit=1000):
    """Get training examples ready for fine-tuning"""
    with get_db(FEEDBACK_DB) as conn:
        query = '''
            SELECT id, question, ideal_answer
            FROM training_examples
        '''

        if unused_only:
            query += ' WHERE used_in_training = 0'

        query += ' ORDER BY created_at DESC LIMIT ?'

        cursor = conn.execute(query, (limit,))
        results = cursor.fetchall()

    examples = []
    for row in results:
        examples.append({
            'id': row[0],
            'question': row[1],
            'ideal_answer': row[2]
        })

    return examples


def generate_training_file(output_path='feedback_training.jsonl', min_examples=50):
    """Generate JSONL training file from approved feedback"""
    examples = get_training_examples(unused_only=True)

    if len(examples) < min_examples:
        print(f"Only {len(examples)} examples available. Need at least {min_examples} for training.")
        return None

    # Use the actual production system prompt for training consistency
    from prompts import build_system_prompt
    production_system_prompt = build_system_prompt()

    with open(output_path, 'w') as f:
        for ex in examples:
            training_obj = {
                "messages": [
                    {"role": "system", "content": production_system_prompt},
                    {"role": "user", "content": ex['question']},
                    {"role": "assistant", "content": ex['ideal_answer']}
                ]
            }
            f.write(json.dumps(training_obj) + '\n')

    print(f"Generated training file: {output_path}")
    print(f"   Examples: {len(examples)}")

    return output_path, len(examples)


def mark_examples_used(run_id):
    """Mark training examples as used in a training run"""
    with get_db(FEEDBACK_DB) as conn:
        conn.execute('''
            UPDATE training_examples
            SET used_in_training = 1, training_run_id = ?
            WHERE used_in_training = 0
        ''', (run_id,))


def create_training_run(run_id, num_examples, notes=None):
    """Record a new training run"""
    with get_db(FEEDBACK_DB) as conn:
        conn.execute('''
            INSERT INTO training_runs (run_id, num_examples, status, notes)
            VALUES (?, ?, 'started', ?)
        ''', (run_id, num_examples, notes))


def update_training_run(run_id, status, model_id=None):
    """Update training run status"""
    with get_db(FEEDBACK_DB) as conn:
        if status == 'completed':
            conn.execute('''
                UPDATE training_runs
                SET status = ?, model_id = ?, completed_at = CURRENT_TIMESTAMP
                WHERE run_id = ?
            ''', (status, model_id, run_id))
        else:
            conn.execute('''
                UPDATE training_runs
                SET status = ?
                WHERE run_id = ?
            ''', (status, run_id))


def get_review_queue(limit=100, queue_type='all'):
    """Get unified review queue: user-flagged negative + auto-flagged low-confidence"""
    with get_db(FEEDBACK_DB) as conn:
        # Ensure needs_review column exists
        add_column(conn, 'feedback', 'needs_review', 'BOOLEAN DEFAULT 0')

        if queue_type == 'negative':
            # Only user-flagged negative feedback
            cursor = conn.execute('''
                SELECT id, question, ai_answer, user_correction, confidence_score,
                       sources, timestamp, user_rating, needs_review
                FROM feedback
                WHERE user_rating = 'negative' AND reviewed = 0
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
        elif queue_type == 'low_confidence':
            # Only auto-flagged low-confidence
            cursor = conn.execute('''
                SELECT id, question, ai_answer, user_correction, confidence_score,
                       sources, timestamp, user_rating, needs_review
                FROM feedback
                WHERE needs_review = 1 AND reviewed = 0 AND user_rating != 'negative'
                ORDER BY confidence_score ASC, timestamp DESC
                LIMIT ?
            ''', (limit,))
        else:
            # All items needing review (both types)
            cursor = conn.execute('''
                SELECT id, question, ai_answer, user_correction, confidence_score,
                       sources, timestamp, user_rating, needs_review
                FROM feedback
                WHERE (user_rating = 'negative' OR needs_review = 1) AND reviewed = 0
                ORDER BY
                    CASE WHEN user_rating = 'negative' THEN 0 ELSE 1 END,
                    confidence_score ASC,
                    timestamp DESC
                LIMIT ?
            ''', (limit,))

        results = cursor.fetchall()

    items = []
    for row in results:
        rating = row[7]
        # Determine review type based on user feedback
        if rating == 'negative':
            review_type = 'user_flagged'
        elif rating == 'unrated':
            review_type = 'no_feedback'
        else:
            review_type = 'auto_flagged'  # positive rating but low confidence

        items.append({
            'id': row[0],
            'question': row[1],
            'ai_answer': row[2],
            'user_correction': row[3],
            'confidence': row[4],
            'sources': json.loads(row[5]) if row[5] else [],
            'timestamp': row[6],
            'rating': rating,
            'needs_review': bool(row[8]),
            'review_type': review_type
        })

    return items


def moderate_answer(feedback_id, action, corrected_answer=None, reason=None, moderator='admin'):
    """Moderate a feedback item: approve, reject, or correct"""
    with get_db(FEEDBACK_DB) as conn:
        # Get original answer
        cursor = conn.execute('SELECT question, ai_answer FROM feedback WHERE id = ?', (feedback_id,))
        result = cursor.fetchone()
        if not result:
            return {'success': False, 'error': 'Feedback not found'}

        question, original_answer = result

        # Log the moderation action
        conn.execute('''
            INSERT INTO moderator_actions
            (feedback_id, action, moderator, original_answer, corrected_answer, reason)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (feedback_id, action, moderator, original_answer, corrected_answer, reason))

        if action == 'approve':
            # Use correction if provided, otherwise use original answer
            ideal_answer = corrected_answer if corrected_answer else original_answer

            # Mark as reviewed and approved
            conn.execute('''
                UPDATE feedback
                SET reviewed = 1, approved_for_training = 1, notes = ?
                WHERE id = ?
            ''', (reason, feedback_id))

            # Create training example
            conn.execute('''
                INSERT INTO training_examples (feedback_id, question, ideal_answer)
                VALUES (?, ?, ?)
            ''', (feedback_id, question, ideal_answer))

        elif action == 'reject':
            # Mark as reviewed but not approved
            conn.execute('''
                UPDATE feedback
                SET reviewed = 1, approved_for_training = 0, notes = ?
                WHERE id = ?
            ''', (reason or 'Rejected by moderator', feedback_id))

        elif action == 'correct':
            # Save correction for later approval
            conn.execute('''
                UPDATE feedback
                SET user_correction = ?, notes = ?
                WHERE id = ?
            ''', (corrected_answer, reason, feedback_id))

    return {'success': True, 'action': action}


def get_moderator_history(limit=100):
    """Get audit trail of moderator actions"""
    with get_db(FEEDBACK_DB) as conn:
        try:
            cursor = conn.execute('''
                SELECT ma.id, ma.feedback_id, ma.action, ma.moderator,
                       ma.original_answer, ma.corrected_answer, ma.reason, ma.timestamp,
                       f.question
                FROM moderator_actions ma
                LEFT JOIN feedback f ON ma.feedback_id = f.id
                ORDER BY ma.timestamp DESC
                LIMIT ?
            ''', (limit,))

            results = cursor.fetchall()
        except Exception:
            # Table doesn't exist yet
            results = []

    history = []
    for row in results:
        history.append({
            'id': row[0],
            'feedback_id': row[1],
            'action': row[2],
            'moderator': row[3],
            'original_answer': row[4][:200] + '...' if row[4] and len(row[4]) > 200 else row[4],
            'corrected_answer': row[5][:200] + '...' if row[5] and len(row[5]) > 200 else row[5],
            'reason': row[6],
            'timestamp': row[7],
            'question': row[8][:100] + '...' if row[8] and len(row[8]) > 100 else row[8]
        })

    return history


def get_feedback_stats():
    """Get statistics about feedback"""
    with get_db(FEEDBACK_DB) as conn:
        stats = {}

        # Total queries (all)
        cursor = conn.execute('SELECT COUNT(*) FROM feedback')
        stats['total_feedback'] = cursor.fetchone()[0]

        # Today's count
        cursor = conn.execute('''
            SELECT COUNT(*) FROM feedback
            WHERE DATE(timestamp) = DATE('now')
        ''')
        stats['today_count'] = cursor.fetchone()[0]

        # Positive vs negative vs unrated
        cursor = conn.execute('SELECT user_rating, COUNT(*) FROM feedback GROUP BY user_rating')
        ratings = cursor.fetchall()
        for rating_row in ratings:
            if rating_row[0]:
                stats[f'{rating_row[0]}_feedback'] = rating_row[1]

        # Unreviewed negative
        cursor = conn.execute("SELECT COUNT(*) FROM feedback WHERE user_rating = 'negative' AND reviewed = 0")
        stats['unreviewed_negative'] = cursor.fetchone()[0]

        # Approved for training
        cursor = conn.execute('SELECT COUNT(*) FROM feedback WHERE approved_for_training = 1')
        stats['approved_for_training'] = cursor.fetchone()[0]

        # Training examples ready
        cursor = conn.execute('SELECT COUNT(*) FROM training_examples WHERE used_in_training = 0')
        stats['examples_ready'] = cursor.fetchone()[0]

        # Total training runs
        cursor = conn.execute('SELECT COUNT(*) FROM training_runs')
        stats['training_runs'] = cursor.fetchone()[0]

        # Average confidence
        cursor = conn.execute('SELECT AVG(confidence_score) FROM feedback WHERE confidence_score IS NOT NULL')
        avg_conf = cursor.fetchone()[0]
        stats['avg_confidence'] = round(avg_conf, 1) if avg_conf else None

        # Confidence distribution
        cursor = conn.execute('SELECT COUNT(*) FROM feedback WHERE confidence_score >= 80')
        high = cursor.fetchone()[0]
        cursor = conn.execute('SELECT COUNT(*) FROM feedback WHERE confidence_score >= 60 AND confidence_score < 80')
        medium = cursor.fetchone()[0]
        cursor = conn.execute('SELECT COUNT(*) FROM feedback WHERE confidence_score < 60 AND confidence_score IS NOT NULL')
        low = cursor.fetchone()[0]
        stats['confidence_distribution'] = {'high': high, 'medium': medium, 'low': low}

        # Auto-approval stats (70% threshold)
        cursor = conn.execute('SELECT COUNT(*) FROM feedback WHERE confidence_score >= 70')
        stats['auto_approved'] = cursor.fetchone()[0]
        cursor = conn.execute('SELECT COUNT(*) FROM feedback WHERE confidence_score < 70 AND confidence_score IS NOT NULL')
        stats['flagged_for_review'] = cursor.fetchone()[0]

        # Needs review queue (if column exists)
        try:
            cursor = conn.execute('SELECT COUNT(*) FROM feedback WHERE needs_review = 1 AND reviewed = 0')
            stats['pending_review'] = cursor.fetchone()[0]
        except Exception:
            stats['pending_review'] = stats.get('flagged_for_review', 0)

        # Daily query counts (last 14 days) for weekly chart
        cursor = conn.execute('''
            SELECT DATE(timestamp) as day, COUNT(*) as count
            FROM feedback
            WHERE timestamp >= DATE('now', '-14 days')
            GROUP BY DATE(timestamp)
            ORDER BY day
        ''')
        stats['daily_counts'] = [{'date': row[0], 'count': row[1]} for row in cursor.fetchall()]

        # Daily confidence trend (last 14 days)
        cursor = conn.execute('''
            SELECT DATE(timestamp) as day, AVG(confidence_score) as avg_conf
            FROM feedback
            WHERE timestamp >= DATE('now', '-14 days') AND confidence_score IS NOT NULL
            GROUP BY DATE(timestamp)
            ORDER BY day
        ''')
        stats['confidence_trend'] = [{'date': row[0], 'avg_confidence': round(row[1], 1) if row[1] else None}
                                      for row in cursor.fetchall()]

        # Daily ratings breakdown (last 14 days)
        cursor = conn.execute('''
            SELECT DATE(timestamp) as day, user_rating, COUNT(*) as count
            FROM feedback
            WHERE timestamp >= DATE('now', '-14 days')
            GROUP BY DATE(timestamp), user_rating
            ORDER BY day
        ''')
        daily_ratings = {}
        for row in cursor.fetchall():
            day = row[0]
            if day not in daily_ratings:
                daily_ratings[day] = {'positive': 0, 'negative': 0, 'unrated': 0}
            rating_key = row[1] if row[1] in ('positive', 'negative') else 'unrated'
            daily_ratings[day][rating_key] = row[2]
        stats['daily_ratings'] = daily_ratings

    return stats


# =============================================================================
# BULK OPERATIONS
# =============================================================================

def bulk_moderate(feedback_ids, action, reason=None, moderator='admin'):
    """Bulk approve or reject multiple feedback items"""
    with get_db(FEEDBACK_DB) as conn:
        results = {'success': 0, 'failed': 0, 'errors': []}

        for feedback_id in feedback_ids:
            try:
                # Get original data
                cursor = conn.execute('SELECT question, ai_answer FROM feedback WHERE id = ?', (feedback_id,))
                result = cursor.fetchone()
                if not result:
                    results['failed'] += 1
                    results['errors'].append(f"ID {feedback_id} not found")
                    continue

                question, original_answer = result

                # Log the action
                conn.execute('''
                    INSERT INTO moderator_actions
                    (feedback_id, action, moderator, original_answer, reason)
                    VALUES (?, ?, ?, ?, ?)
                ''', (feedback_id, action, moderator, original_answer, reason or f'Bulk {action}'))

                if action == 'approve':
                    conn.execute('''
                        UPDATE feedback
                        SET reviewed = 1, approved_for_training = 1, notes = ?
                        WHERE id = ?
                    ''', (reason or 'Bulk approved', feedback_id))

                    # Create training example
                    conn.execute('''
                        INSERT INTO training_examples (feedback_id, question, ideal_answer)
                        VALUES (?, ?, ?)
                    ''', (feedback_id, question, original_answer))

                elif action == 'reject':
                    conn.execute('''
                        UPDATE feedback
                        SET reviewed = 1, approved_for_training = 0, notes = ?
                        WHERE id = ?
                    ''', (reason or 'Bulk rejected', feedback_id))

                results['success'] += 1

            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"ID {feedback_id}: {str(e)}")

    return results


def bulk_approve_high_confidence(min_confidence=80, limit=100):
    """Auto-approve all high-confidence items that haven't been reviewed"""
    with get_db(FEEDBACK_DB) as conn:
        # Find high-confidence unreviewed items
        cursor = conn.execute('''
            SELECT id FROM feedback
            WHERE confidence_score >= ? AND reviewed = 0
            LIMIT ?
        ''', (min_confidence, limit))

        ids = [row[0] for row in cursor.fetchall()]

    if not ids:
        return {'success': 0, 'failed': 0, 'message': 'No items to approve'}

    result = bulk_moderate(ids, 'approve', f'Auto-approved (confidence >= {min_confidence}%)')
    result['message'] = f'Processed {len(ids)} high-confidence items'
    return result


# =============================================================================
# EXPORT FUNCTIONS
# =============================================================================

def export_feedback_csv():
    """Export all feedback to CSV format"""
    with get_db(FEEDBACK_DB) as conn:
        cursor = conn.execute('''
            SELECT id, question, ai_answer, user_rating, user_correction,
                   confidence_score, timestamp, reviewed, approved_for_training, notes
            FROM feedback
            ORDER BY timestamp DESC
        ''')

        rows = cursor.fetchall()

    # Build CSV
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        'ID', 'Question', 'AI Answer', 'User Rating', 'User Correction',
        'Confidence', 'Timestamp', 'Reviewed', 'Approved for Training', 'Notes'
    ])

    for row in rows:
        writer.writerow(row)

    return output.getvalue()


def export_training_examples_csv():
    """Export training examples to CSV format"""
    with get_db(FEEDBACK_DB) as conn:
        cursor = conn.execute('''
            SELECT te.id, te.question, te.ideal_answer, te.created_at,
                   te.used_in_training, f.confidence_score
            FROM training_examples te
            LEFT JOIN feedback f ON te.feedback_id = f.id
            ORDER BY te.created_at DESC
        ''')

        rows = cursor.fetchall()

    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'ID', 'Question', 'Ideal Answer', 'Created At', 'Used in Training', 'Original Confidence'
    ])

    for row in rows:
        writer.writerow(row)

    return output.getvalue()


def export_moderation_history_csv():
    """Export moderator actions to CSV"""
    with get_db(FEEDBACK_DB) as conn:
        cursor = conn.execute('''
            SELECT ma.id, ma.feedback_id, ma.action, ma.moderator,
                   ma.reason, ma.timestamp, f.question
            FROM moderator_actions ma
            LEFT JOIN feedback f ON ma.feedback_id = f.id
            ORDER BY ma.timestamp DESC
        ''')

        rows = cursor.fetchall()

    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'ID', 'Feedback ID', 'Action', 'Moderator', 'Reason', 'Timestamp', 'Question'
    ])

    for row in rows:
        writer.writerow(row)

    return output.getvalue()


def export_analytics_json():
    """Export comprehensive analytics data"""
    stats = get_feedback_stats()

    with get_db(FEEDBACK_DB) as conn:
        # Daily query counts (last 30 days)
        cursor = conn.execute('''
            SELECT DATE(timestamp) as day, COUNT(*) as count
            FROM feedback
            WHERE timestamp >= DATE('now', '-30 days')
            GROUP BY DATE(timestamp)
            ORDER BY day
        ''')
        daily_counts = [{'date': row[0], 'count': row[1]} for row in cursor.fetchall()]

        # Rating distribution by day
        cursor = conn.execute('''
            SELECT DATE(timestamp) as day, user_rating, COUNT(*) as count
            FROM feedback
            WHERE timestamp >= DATE('now', '-30 days')
            GROUP BY DATE(timestamp), user_rating
            ORDER BY day
        ''')
        daily_ratings = {}
        for row in cursor.fetchall():
            day = row[0]
            if day not in daily_ratings:
                daily_ratings[day] = {}
            daily_ratings[day][row[1]] = row[2]

        # Confidence trends
        cursor = conn.execute('''
            SELECT DATE(timestamp) as day, AVG(confidence_score) as avg_conf
            FROM feedback
            WHERE timestamp >= DATE('now', '-30 days') AND confidence_score IS NOT NULL
            GROUP BY DATE(timestamp)
            ORDER BY day
        ''')
        confidence_trend = [{'date': row[0], 'avg_confidence': round(row[1], 1) if row[1] else None}
                            for row in cursor.fetchall()]

    return {
        'stats': stats,
        'daily_counts': daily_counts,
        'daily_ratings': daily_ratings,
        'confidence_trend': confidence_trend,
        'exported_at': datetime.now().isoformat()
    }


# =============================================================================
# PRIORITY QUEUE WITH FREQUENCY DETECTION
# =============================================================================

def get_question_frequencies(limit=50):
    """Find frequently asked questions (potential problem areas)"""
    with get_db(FEEDBACK_DB) as conn:
        # Use fuzzy matching by normalizing questions
        cursor = conn.execute('''
            SELECT LOWER(TRIM(question)) as normalized_q,
                   COUNT(*) as frequency,
                   AVG(confidence_score) as avg_confidence,
                   SUM(CASE WHEN user_rating = 'negative' THEN 1 ELSE 0 END) as negative_count,
                   GROUP_CONCAT(id) as ids
            FROM feedback
            GROUP BY normalized_q
            HAVING COUNT(*) >= 2
            ORDER BY frequency DESC, avg_confidence ASC
            LIMIT ?
        ''', (limit,))

        results = cursor.fetchall()

    frequencies = []
    for row in results:
        frequencies.append({
            'question': row[0],
            'frequency': row[1],
            'avg_confidence': round(row[2], 1) if row[2] else None,
            'negative_count': row[3],
            'ids': [int(x) for x in row[4].split(',')] if row[4] else [],
            'priority_score': _calculate_priority_score(row[1], row[2], row[3])
        })

    return sorted(frequencies, key=lambda x: x['priority_score'], reverse=True)


def _calculate_priority_score(frequency, avg_confidence, negative_count):
    """Calculate priority score for a question cluster"""
    score = 0

    # Frequency boost (more asks = higher priority)
    score += min(frequency * 10, 50)

    # Low confidence penalty
    if avg_confidence:
        if avg_confidence < 50:
            score += 30
        elif avg_confidence < 70:
            score += 15

    # Negative feedback boost
    score += negative_count * 20

    return score


def get_priority_review_queue(limit=100):
    """Get review queue sorted by priority (frequency + confidence + negative feedback)"""
    with get_db(FEEDBACK_DB) as conn:
        # Ensure needs_review column exists
        add_column(conn, 'feedback', 'needs_review', 'BOOLEAN DEFAULT 0')

        # Get question frequencies for priority scoring
        cursor = conn.execute('''
            SELECT LOWER(TRIM(question)) as nq, COUNT(*) as freq
            FROM feedback
            GROUP BY nq
        ''')
        freq_map = {row[0]: row[1] for row in cursor.fetchall()}

        # Get items needing review
        cursor = conn.execute('''
            SELECT id, question, ai_answer, user_correction, confidence_score,
                   sources, timestamp, user_rating, needs_review
            FROM feedback
            WHERE (user_rating = 'negative' OR needs_review = 1) AND reviewed = 0
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit * 2,))  # Get more, we'll sort and limit

        results = cursor.fetchall()

    items = []
    for row in results:
        question = row[1]
        normalized_q = question.lower().strip()
        frequency = freq_map.get(normalized_q, 1)
        confidence = row[4]
        rating = row[7]

        # Calculate priority
        priority = 0
        if rating == 'negative':
            priority += 50  # User flagged = high priority
        if confidence and confidence < 50:
            priority += 30
        elif confidence and confidence < 70:
            priority += 15
        priority += min(frequency * 5, 25)  # Frequency boost

        # Determine review type
        if rating == 'negative':
            review_type = 'user_flagged'
        elif rating == 'unrated':
            review_type = 'no_feedback'
        else:
            review_type = 'auto_flagged'

        items.append({
            'id': row[0],
            'question': question,
            'ai_answer': row[2],
            'user_correction': row[3],
            'confidence': confidence,
            'sources': json.loads(row[5]) if row[5] else [],
            'timestamp': row[6],
            'rating': rating,
            'needs_review': bool(row[8]),
            'review_type': review_type,
            'frequency': frequency,
            'priority': priority,
            'is_trending': frequency >= 3
        })

    # Sort by priority (highest first)
    items.sort(key=lambda x: x['priority'], reverse=True)

    return items[:limit]


def get_trending_issues(min_frequency=3, days=7):
    """Get trending problem areas (frequently asked with low confidence or negative feedback)"""
    with get_db(FEEDBACK_DB) as conn:
        cursor = conn.execute('''
            SELECT LOWER(TRIM(question)) as normalized_q,
                   COUNT(*) as frequency,
                   AVG(confidence_score) as avg_confidence,
                   SUM(CASE WHEN user_rating = 'negative' THEN 1 ELSE 0 END) as negative_count,
                   MAX(timestamp) as last_asked
            FROM feedback
            WHERE timestamp >= DATE('now', ? || ' days')
            GROUP BY normalized_q
            HAVING COUNT(*) >= ?
            ORDER BY frequency DESC
        ''', (f'-{days}', min_frequency))

        results = cursor.fetchall()

    trending = []
    for row in results:
        # Only include if there's a problem (low confidence or negative feedback)
        avg_conf = row[2]
        neg_count = row[3]

        if (avg_conf and avg_conf < 70) or neg_count > 0:
            trending.append({
                'question': row[0],
                'frequency': row[1],
                'avg_confidence': round(avg_conf, 1) if avg_conf else None,
                'negative_count': neg_count,
                'last_asked': row[4],
                'severity': 'high' if (avg_conf and avg_conf < 50) or neg_count >= 2 else 'medium'
            })

    return sorted(trending, key=lambda x: (x['severity'] == 'high', x['frequency']), reverse=True)


# Table initialization is now handled by chat_history.py's _init_feedback_tables()
# No import-time init needed here.

if __name__ == "__main__":
    print("\n" + "="*80)
    print("FEEDBACK SYSTEM TEST")
    print("="*80 + "\n")

    # Save some test feedback
    print("Saving test feedback...")

    save_feedback(
        question="What fungicide for dollar spot?",
        ai_answer="Use recommended rate of fungicide",
        rating="negative",
        correction="Heritage at 0.16 fl oz/1000 sq ft, 14-21 day interval",
        confidence=0.4
    )

    save_feedback(
        question="When to apply pre-emergent?",
        ai_answer="Apply when soil temps reach 55F",
        rating="positive",
        confidence=0.85
    )

    # Get negative feedback
    negative = get_negative_feedback()
    print(f"\nNegative feedback items: {len(negative)}")

    if negative:
        print("\nExample:")
        print(f"  Q: {negative[0]['question']}")
        print(f"  Bad answer: {negative[0]['ai_answer']}")
        print(f"  User correction: {negative[0]['user_correction']}")

        # Approve it
        approve_for_training(
            negative[0]['id'],
            negative[0]['user_correction']
        )
        print("\nApproved for training")

    # Get stats
    stats = get_feedback_stats()
    print("\n" + "="*80)
    print("FEEDBACK STATS")
    print("="*80)
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Generate training file
    print("\n" + "="*80)
    print("GENERATING TRAINING FILE")
    print("="*80)
    result = generate_training_file(min_examples=1)

    if result:
        filepath, count = result
        print(f"\nTraining file ready: {filepath} ({count} examples)")
