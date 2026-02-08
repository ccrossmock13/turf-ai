"""
Feedback & Learning System
Collects user corrections and builds training data for continuous improvement
"""

import sqlite3
import os
from datetime import datetime
import json

# Use data directory for Docker persistence, fallback to current dir for local dev
DATA_DIR = os.environ.get('DATA_DIR', 'data' if os.path.exists('data') else '.')
DB_PATH = os.path.join(DATA_DIR, 'greenside_feedback.db')

def init_feedback_database():
    """Initialize SQLite database for feedback collection"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Feedback table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            ai_answer TEXT NOT NULL,
            user_rating TEXT NOT NULL,
            user_correction TEXT,
            sources TEXT,
            confidence_score REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed BOOLEAN DEFAULT 0,
            approved_for_training BOOLEAN DEFAULT 0,
            notes TEXT
        )
    ''')
    
    # Training examples generated from feedback
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS training_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feedback_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            ideal_answer TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            used_in_training BOOLEAN DEFAULT 0,
            training_run_id TEXT,
            FOREIGN KEY (feedback_id) REFERENCES feedback (id)
        )
    ''')
    
    # Training runs tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS training_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL UNIQUE,
            num_examples INTEGER NOT NULL,
            status TEXT NOT NULL,
            model_id TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            notes TEXT
        )
    ''')

    # Moderator actions audit trail
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS moderator_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feedback_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            moderator TEXT DEFAULT 'admin',
            original_answer TEXT,
            corrected_answer TEXT,
            reason TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (feedback_id) REFERENCES feedback (id)
        )
    ''')

    # Indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_rating ON feedback(user_rating)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reviewed ON feedback(reviewed)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_approved ON feedback(approved_for_training)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_mod_actions ON moderator_actions(feedback_id)')
    
    conn.commit()
    conn.close()
    print("✅ Feedback database initialized")

def save_feedback(question, ai_answer, rating, correction=None, sources=None, confidence=None):
    """Save user feedback (when user rates)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    sources_json = json.dumps(sources) if sources else None

    cursor.execute('''
        INSERT INTO feedback
        (question, ai_answer, user_rating, user_correction, sources, confidence_score)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (question, ai_answer, rating, correction, sources_json, confidence))

    feedback_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return feedback_id


def save_query(question, ai_answer, sources=None, confidence=None, topic=None, needs_review=False):
    """Save every query automatically (before user rates)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    sources_json = json.dumps(sources) if sources else None

    # Check if needs_review column exists, add if not
    try:
        cursor.execute('SELECT needs_review FROM feedback LIMIT 1')
    except sqlite3.OperationalError:
        cursor.execute('ALTER TABLE feedback ADD COLUMN needs_review BOOLEAN DEFAULT 0')

    # Use 'unrated' as the default rating
    cursor.execute('''
        INSERT INTO feedback
        (question, ai_answer, user_rating, sources, confidence_score, needs_review)
        VALUES (?, ?, 'unrated', ?, ?, ?)
    ''', (question, ai_answer, sources_json, confidence, 1 if needs_review else 0))

    query_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return query_id


def get_queries_needing_review(limit=100):
    """Get queries flagged for human review (confidence < 70% or grounding issues)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if needs_review column exists
    try:
        cursor.execute('''
            SELECT id, question, ai_answer, confidence_score, sources, timestamp
            FROM feedback
            WHERE needs_review = 1 AND reviewed = 0
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
    except sqlite3.OperationalError:
        # Fallback to confidence-based query if column doesn't exist
        cursor.execute('''
            SELECT id, question, ai_answer, confidence_score, sources, timestamp
            FROM feedback
            WHERE confidence_score < 70 AND reviewed = 0
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))

    results = cursor.fetchall()
    conn.close()

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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Find the most recent query with this question
    cursor.execute('''
        UPDATE feedback
        SET user_rating = ?, user_correction = ?
        WHERE id = (
            SELECT id FROM feedback
            WHERE question = ? AND user_rating = 'unrated'
            ORDER BY timestamp DESC LIMIT 1
        )
    ''', (rating, correction, question))

    conn.commit()
    conn.close()

def get_negative_feedback(limit=50, unreviewed_only=True):
    """Get feedback that needs review"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = '''
        SELECT id, question, ai_answer, user_correction, timestamp
        FROM feedback
        WHERE user_rating = 'negative'
    '''
    
    if unreviewed_only:
        query += ' AND reviewed = 0'
    
    query += ' ORDER BY timestamp DESC LIMIT ?'
    
    cursor.execute(query, (limit,))
    results = cursor.fetchall()
    conn.close()
    
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get original question
    cursor.execute('SELECT question FROM feedback WHERE id = ?', (feedback_id,))
    question = cursor.fetchone()[0]
    
    # Mark feedback as reviewed and approved
    cursor.execute('''
        UPDATE feedback 
        SET reviewed = 1, approved_for_training = 1
        WHERE id = ?
    ''', (feedback_id,))
    
    # Create training example
    cursor.execute('''
        INSERT INTO training_examples (feedback_id, question, ideal_answer)
        VALUES (?, ?, ?)
    ''', (feedback_id, question, ideal_answer))
    
    conn.commit()
    conn.close()

def reject_feedback(feedback_id, notes=None):
    """Mark feedback as reviewed but not approved"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE feedback 
        SET reviewed = 1, approved_for_training = 0, notes = ?
        WHERE id = ?
    ''', (notes, feedback_id))
    
    conn.commit()
    conn.close()

def get_training_examples(unused_only=True, limit=1000):
    """Get training examples ready for fine-tuning"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = '''
        SELECT id, question, ideal_answer
        FROM training_examples
    '''
    
    if unused_only:
        query += ' WHERE used_in_training = 0'
    
    query += ' ORDER BY created_at DESC LIMIT ?'
    
    cursor.execute(query, (limit,))
    results = cursor.fetchall()
    conn.close()
    
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
        print(f"⚠️  Only {len(examples)} examples available. Need at least {min_examples} for training.")
        return None
    
    with open(output_path, 'w') as f:
        for ex in examples:
            training_obj = {
                "messages": [
                    {"role": "system", "content": "You are a specialized expert in turfgrass science."},
                    {"role": "user", "content": ex['question']},
                    {"role": "assistant", "content": ex['ideal_answer']}
                ]
            }
            f.write(json.dumps(training_obj) + '\n')
    
    print(f"✅ Generated training file: {output_path}")
    print(f"   Examples: {len(examples)}")
    
    return output_path, len(examples)

def mark_examples_used(run_id):
    """Mark training examples as used in a training run"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE training_examples 
        SET used_in_training = 1, training_run_id = ?
        WHERE used_in_training = 0
    ''', (run_id,))
    
    conn.commit()
    conn.close()

def create_training_run(run_id, num_examples, notes=None):
    """Record a new training run"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO training_runs (run_id, num_examples, status, notes)
        VALUES (?, ?, 'started', ?)
    ''', (run_id, num_examples, notes))
    
    conn.commit()
    conn.close()

def update_training_run(run_id, status, model_id=None):
    """Update training run status"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if status == 'completed':
        cursor.execute('''
            UPDATE training_runs 
            SET status = ?, model_id = ?, completed_at = CURRENT_TIMESTAMP
            WHERE run_id = ?
        ''', (status, model_id, run_id))
    else:
        cursor.execute('''
            UPDATE training_runs 
            SET status = ?
            WHERE run_id = ?
        ''', (status, run_id))
    
    conn.commit()
    conn.close()

def get_review_queue(limit=100, queue_type='all'):
    """Get unified review queue: user-flagged negative + auto-flagged low-confidence"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ensure needs_review column exists
    try:
        cursor.execute('SELECT needs_review FROM feedback LIMIT 1')
    except sqlite3.OperationalError:
        cursor.execute('ALTER TABLE feedback ADD COLUMN needs_review BOOLEAN DEFAULT 0')

    if queue_type == 'negative':
        # Only user-flagged negative feedback
        cursor.execute('''
            SELECT id, question, ai_answer, user_correction, confidence_score,
                   sources, timestamp, user_rating, needs_review
            FROM feedback
            WHERE user_rating = 'negative' AND reviewed = 0
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
    elif queue_type == 'low_confidence':
        # Only auto-flagged low-confidence
        cursor.execute('''
            SELECT id, question, ai_answer, user_correction, confidence_score,
                   sources, timestamp, user_rating, needs_review
            FROM feedback
            WHERE needs_review = 1 AND reviewed = 0 AND user_rating != 'negative'
            ORDER BY confidence_score ASC, timestamp DESC
            LIMIT ?
        ''', (limit,))
    else:
        # All items needing review (both types)
        cursor.execute('''
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
    conn.close()

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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get original answer
    cursor.execute('SELECT question, ai_answer FROM feedback WHERE id = ?', (feedback_id,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        return {'success': False, 'error': 'Feedback not found'}

    question, original_answer = result

    # Log the moderation action
    cursor.execute('''
        INSERT INTO moderator_actions
        (feedback_id, action, moderator, original_answer, corrected_answer, reason)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (feedback_id, action, moderator, original_answer, corrected_answer, reason))

    if action == 'approve':
        # Use correction if provided, otherwise use original answer
        ideal_answer = corrected_answer if corrected_answer else original_answer

        # Mark as reviewed and approved
        cursor.execute('''
            UPDATE feedback
            SET reviewed = 1, approved_for_training = 1, notes = ?
            WHERE id = ?
        ''', (reason, feedback_id))

        # Create training example
        cursor.execute('''
            INSERT INTO training_examples (feedback_id, question, ideal_answer)
            VALUES (?, ?, ?)
        ''', (feedback_id, question, ideal_answer))

    elif action == 'reject':
        # Mark as reviewed but not approved
        cursor.execute('''
            UPDATE feedback
            SET reviewed = 1, approved_for_training = 0, notes = ?
            WHERE id = ?
        ''', (reason or 'Rejected by moderator', feedback_id))

    elif action == 'correct':
        # Save correction for later approval
        cursor.execute('''
            UPDATE feedback
            SET user_correction = ?, notes = ?
            WHERE id = ?
        ''', (corrected_answer, reason, feedback_id))

    conn.commit()
    conn.close()

    return {'success': True, 'action': action}


def get_moderator_history(limit=100):
    """Get audit trail of moderator actions"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT ma.id, ma.feedback_id, ma.action, ma.moderator,
                   ma.original_answer, ma.corrected_answer, ma.reason, ma.timestamp,
                   f.question
            FROM moderator_actions ma
            LEFT JOIN feedback f ON ma.feedback_id = f.id
            ORDER BY ma.timestamp DESC
            LIMIT ?
        ''', (limit,))

        results = cursor.fetchall()
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        results = []

    conn.close()

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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    stats = {}

    # Total queries (all)
    cursor.execute('SELECT COUNT(*) FROM feedback')
    stats['total_feedback'] = cursor.fetchone()[0]

    # Today's count
    cursor.execute('''
        SELECT COUNT(*) FROM feedback
        WHERE DATE(timestamp) = DATE('now')
    ''')
    stats['today_count'] = cursor.fetchone()[0]

    # Positive vs negative vs unrated
    cursor.execute('SELECT user_rating, COUNT(*) FROM feedback GROUP BY user_rating')
    ratings = cursor.fetchall()
    for rating, count in ratings:
        if rating:
            stats[f'{rating}_feedback'] = count

    # Unreviewed negative
    cursor.execute('SELECT COUNT(*) FROM feedback WHERE user_rating = "negative" AND reviewed = 0')
    stats['unreviewed_negative'] = cursor.fetchone()[0]

    # Approved for training
    cursor.execute('SELECT COUNT(*) FROM feedback WHERE approved_for_training = 1')
    stats['approved_for_training'] = cursor.fetchone()[0]

    # Training examples ready
    cursor.execute('SELECT COUNT(*) FROM training_examples WHERE used_in_training = 0')
    stats['examples_ready'] = cursor.fetchone()[0]

    # Total training runs
    cursor.execute('SELECT COUNT(*) FROM training_runs')
    stats['training_runs'] = cursor.fetchone()[0]

    # Average confidence
    cursor.execute('SELECT AVG(confidence_score) FROM feedback WHERE confidence_score IS NOT NULL')
    avg_conf = cursor.fetchone()[0]
    stats['avg_confidence'] = round(avg_conf, 1) if avg_conf else None

    # Confidence distribution
    cursor.execute('SELECT COUNT(*) FROM feedback WHERE confidence_score >= 80')
    high = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM feedback WHERE confidence_score >= 60 AND confidence_score < 80')
    medium = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM feedback WHERE confidence_score < 60 AND confidence_score IS NOT NULL')
    low = cursor.fetchone()[0]
    stats['confidence_distribution'] = {'high': high, 'medium': medium, 'low': low}

    # Auto-approval stats (70% threshold)
    cursor.execute('SELECT COUNT(*) FROM feedback WHERE confidence_score >= 70')
    stats['auto_approved'] = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM feedback WHERE confidence_score < 70 AND confidence_score IS NOT NULL')
    stats['flagged_for_review'] = cursor.fetchone()[0]

    # Needs review queue (if column exists)
    try:
        cursor.execute('SELECT COUNT(*) FROM feedback WHERE needs_review = 1 AND reviewed = 0')
        stats['pending_review'] = cursor.fetchone()[0]
    except sqlite3.OperationalError:
        stats['pending_review'] = stats.get('flagged_for_review', 0)

    conn.close()
    return stats


# =============================================================================
# BULK OPERATIONS
# =============================================================================

def bulk_moderate(feedback_ids, action, reason=None, moderator='admin'):
    """Bulk approve or reject multiple feedback items"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    results = {'success': 0, 'failed': 0, 'errors': []}

    for feedback_id in feedback_ids:
        try:
            # Get original data
            cursor.execute('SELECT question, ai_answer FROM feedback WHERE id = ?', (feedback_id,))
            result = cursor.fetchone()
            if not result:
                results['failed'] += 1
                results['errors'].append(f"ID {feedback_id} not found")
                continue

            question, original_answer = result

            # Log the action
            cursor.execute('''
                INSERT INTO moderator_actions
                (feedback_id, action, moderator, original_answer, reason)
                VALUES (?, ?, ?, ?, ?)
            ''', (feedback_id, action, moderator, original_answer, reason or f'Bulk {action}'))

            if action == 'approve':
                cursor.execute('''
                    UPDATE feedback
                    SET reviewed = 1, approved_for_training = 1, notes = ?
                    WHERE id = ?
                ''', (reason or 'Bulk approved', feedback_id))

                # Create training example
                cursor.execute('''
                    INSERT INTO training_examples (feedback_id, question, ideal_answer)
                    VALUES (?, ?, ?)
                ''', (feedback_id, question, original_answer))

            elif action == 'reject':
                cursor.execute('''
                    UPDATE feedback
                    SET reviewed = 1, approved_for_training = 0, notes = ?
                    WHERE id = ?
                ''', (reason or 'Bulk rejected', feedback_id))

            results['success'] += 1

        except Exception as e:
            results['failed'] += 1
            results['errors'].append(f"ID {feedback_id}: {str(e)}")

    conn.commit()
    conn.close()

    return results


def bulk_approve_high_confidence(min_confidence=80, limit=100):
    """Auto-approve all high-confidence items that haven't been reviewed"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Find high-confidence unreviewed items
    cursor.execute('''
        SELECT id FROM feedback
        WHERE confidence_score >= ? AND reviewed = 0
        LIMIT ?
    ''', (min_confidence, limit))

    ids = [row[0] for row in cursor.fetchall()]
    conn.close()

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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, question, ai_answer, user_rating, user_correction,
               confidence_score, timestamp, reviewed, approved_for_training, notes
        FROM feedback
        ORDER BY timestamp DESC
    ''')

    rows = cursor.fetchall()
    conn.close()

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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT te.id, te.question, te.ideal_answer, te.created_at,
               te.used_in_training, f.confidence_score
        FROM training_examples te
        LEFT JOIN feedback f ON te.feedback_id = f.id
        ORDER BY te.created_at DESC
    ''')

    rows = cursor.fetchall()
    conn.close()

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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT ma.id, ma.feedback_id, ma.action, ma.moderator,
               ma.reason, ma.timestamp, f.question
        FROM moderator_actions ma
        LEFT JOIN feedback f ON ma.feedback_id = f.id
        ORDER BY ma.timestamp DESC
    ''')

    rows = cursor.fetchall()
    conn.close()

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

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Daily query counts (last 30 days)
    cursor.execute('''
        SELECT DATE(timestamp) as day, COUNT(*) as count
        FROM feedback
        WHERE timestamp >= DATE('now', '-30 days')
        GROUP BY DATE(timestamp)
        ORDER BY day
    ''')
    daily_counts = [{'date': row[0], 'count': row[1]} for row in cursor.fetchall()]

    # Rating distribution by day
    cursor.execute('''
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
    cursor.execute('''
        SELECT DATE(timestamp) as day, AVG(confidence_score) as avg_conf
        FROM feedback
        WHERE timestamp >= DATE('now', '-30 days') AND confidence_score IS NOT NULL
        GROUP BY DATE(timestamp)
        ORDER BY day
    ''')
    confidence_trend = [{'date': row[0], 'avg_confidence': round(row[1], 1) if row[1] else None}
                        for row in cursor.fetchall()]

    conn.close()

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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Use fuzzy matching by normalizing questions
    cursor.execute('''
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
    conn.close()

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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ensure needs_review column exists
    try:
        cursor.execute('SELECT needs_review FROM feedback LIMIT 1')
    except sqlite3.OperationalError:
        cursor.execute('ALTER TABLE feedback ADD COLUMN needs_review BOOLEAN DEFAULT 0')

    # Get question frequencies for priority scoring
    cursor.execute('''
        SELECT LOWER(TRIM(question)) as nq, COUNT(*) as freq
        FROM feedback
        GROUP BY nq
    ''')
    freq_map = {row[0]: row[1] for row in cursor.fetchall()}

    # Get items needing review
    cursor.execute('''
        SELECT id, question, ai_answer, user_correction, confidence_score,
               sources, timestamp, user_rating, needs_review
        FROM feedback
        WHERE (user_rating = 'negative' OR needs_review = 1) AND reviewed = 0
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (limit * 2,))  # Get more, we'll sort and limit

    results = cursor.fetchall()
    conn.close()

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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
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
    conn.close()

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


# Initialize on import
init_feedback_database()

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
        ai_answer="Apply when soil temps reach 55°F",
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
        print("\n✅ Approved for training")
    
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
        print(f"\n✅ Training file ready: {filepath} ({count} examples)")