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
    
    # Indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_rating ON feedback(user_rating)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reviewed ON feedback(reviewed)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_approved ON feedback(approved_for_training)')
    
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


def save_query(question, ai_answer, sources=None, confidence=None, topic=None):
    """Save every query automatically (before user rates)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    sources_json = json.dumps(sources) if sources else None

    # Use 'unrated' as the default rating
    cursor.execute('''
        INSERT INTO feedback
        (question, ai_answer, user_rating, sources, confidence_score)
        VALUES (?, ?, 'unrated', ?, ?)
    ''', (question, ai_answer, sources_json, confidence))

    query_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return query_id


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

    conn.close()
    return stats

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