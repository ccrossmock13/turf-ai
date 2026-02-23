"""
Chat History & Context Awareness System
Stores conversations and allows AI to reference previous questions
"""

import sqlite3
import os
import logging
from datetime import datetime
import json
import hashlib
import re

# Use data directory for Docker persistence, fallback to current dir for local dev
DATA_DIR = os.environ.get('DATA_DIR', 'data' if os.path.exists('data') else '.')
DB_PATH = os.path.join(DATA_DIR, 'greenside_conversations.db')

def init_database():
    """Initialize SQLite database for chat history"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Conversations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_info TEXT
        )
    ''')
    
    # Messages table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            sources TEXT,
            confidence_score REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id)
        )
    ''')
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    ''')

    # Course profiles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            course_name TEXT,
            city TEXT,
            state TEXT,
            region TEXT,
            primary_grass TEXT,
            secondary_grasses TEXT,
            turf_type TEXT,
            role TEXT,
            greens_grass TEXT,
            fairways_grass TEXT,
            rough_grass TEXT,
            tees_grass TEXT,
            soil_type TEXT,
            irrigation_source TEXT,
            mowing_heights TEXT,
            annual_n_budget TEXT,
            notes TEXT,
            cultivars TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_session ON conversations(session_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conv_time ON messages(conversation_id, timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_profiles_user ON course_profiles(user_id)')

    # Migration: add user_id to conversations (idempotent)
    try:
        cursor.execute('ALTER TABLE conversations ADD COLUMN user_id INTEGER REFERENCES users(id)')
    except sqlite3.OperationalError:
        pass  # Column already exists
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id)')

    # Migration: add tees_grass and cultivars columns to course_profiles (idempotent)
    for col_name, col_type in [('tees_grass', 'TEXT'), ('cultivars', 'TEXT')]:
        try:
            cursor.execute(f'ALTER TABLE course_profiles ADD COLUMN {col_name} {col_type}')
        except sqlite3.OperationalError:
            pass  # Column already exists

    # Migration: add acreage columns to course_profiles (idempotent)
    for col_name in ['greens_acreage', 'fairways_acreage', 'rough_acreage', 'tees_acreage']:
        try:
            cursor.execute(f'ALTER TABLE course_profiles ADD COLUMN {col_name} REAL')
        except sqlite3.OperationalError:
            pass  # Column already exists

    # Migration: add sprayer config columns to course_profiles (idempotent)
    for col_name, col_type in [('default_gpa', 'REAL'), ('tank_size', 'REAL')]:
        try:
            cursor.execute(f'ALTER TABLE course_profiles ADD COLUMN {col_name} {col_type}')
        except sqlite3.OperationalError:
            pass  # Column already exists

    # Migration: add tank mix support to spray_applications (idempotent)
    try:
        cursor.execute('ALTER TABLE spray_applications ADD COLUMN products_json TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Migration: add application method to spray_applications (idempotent)
    try:
        cursor.execute('ALTER TABLE spray_applications ADD COLUMN application_method TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Spray tracker tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS spray_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            area TEXT NOT NULL,
            product_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            product_category TEXT NOT NULL,
            rate REAL NOT NULL,
            rate_unit TEXT NOT NULL,
            area_acreage REAL NOT NULL,
            carrier_volume_gpa REAL,
            total_product REAL,
            total_product_unit TEXT,
            total_carrier_gallons REAL,
            nutrients_applied TEXT,
            weather_temp REAL,
            weather_wind TEXT,
            weather_conditions TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_spray_user ON spray_applications(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_spray_date ON spray_applications(user_id, date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_spray_area ON spray_applications(user_id, area)')

    # Custom products table (user-entered fertilizers/products)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS custom_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            brand TEXT,
            product_type TEXT NOT NULL DEFAULT 'fertilizer',
            npk TEXT,
            secondary_nutrients TEXT,
            form_type TEXT,
            density_lbs_per_gallon REAL,
            sgn INTEGER,
            default_rate REAL,
            rate_unit TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_custom_products_user ON custom_products(user_id)')

    # Sprayers table — multiple sprayers per user, each assigned to areas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sprayers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            gpa REAL NOT NULL,
            tank_size REAL NOT NULL,
            nozzle_type TEXT,
            areas TEXT NOT NULL DEFAULT '[]',
            is_default INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sprayers_user ON sprayers(user_id)')

    # User inventory — curated product subset per user
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id TEXT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, product_id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_inventory_user ON user_inventory(user_id)')

    conn.commit()
    conn.close()
    print("✅ Database initialized")

def create_session(user_id=None):
    """Create a new conversation session, optionally bound to a user."""
    session_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO conversations (session_id, user_id)
            VALUES (?, ?)
        ''', (session_id, user_id))

        conversation_id = cursor.lastrowid
        conn.commit()
        conn.close()
    except Exception as e:
        logging.getLogger(__name__).error(f"DB error in create_session: {e}")
        return session_id, 0

    return session_id, conversation_id


def get_user_conversations(user_id, limit=50):
    """Get conversation summaries for a user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.id, c.session_id, c.created_at, c.last_active,
               (SELECT content FROM messages WHERE conversation_id = c.id AND role = 'user'
                ORDER BY timestamp ASC LIMIT 1) as first_question,
               (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id) as message_count
        FROM conversations c
        WHERE c.user_id = ?
        ORDER BY c.last_active DESC
        LIMIT ?
    ''', (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [{
        'id': r[0], 'session_id': r[1], 'created_at': r[2],
        'last_active': r[3], 'first_question': r[4], 'message_count': r[5]
    } for r in rows]

def get_conversation_id(session_id):
    """Get conversation ID from session ID"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id FROM conversations WHERE session_id = ?
    ''', (session_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else None

def save_message(conversation_id, role, content, sources=None, confidence_score=None):
    """Save a message to the database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        sources_json = json.dumps(sources) if sources else None

        cursor.execute('''
            INSERT INTO messages (conversation_id, role, content, sources, confidence_score)
            VALUES (?, ?, ?, ?, ?)
        ''', (conversation_id, role, content, sources_json, confidence_score))

        # Update last_active timestamp
        cursor.execute('''
            UPDATE conversations
            SET last_active = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (conversation_id,))

        conn.commit()
        conn.close()
    except Exception as e:
        logging.getLogger(__name__).error(f"DB error in save_message: {e}")

def get_conversation_history(conversation_id, limit=10):
    """Get recent messages from a conversation"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT role, content, sources, confidence_score, timestamp
        FROM messages
        WHERE conversation_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (conversation_id, limit))
    
    results = cursor.fetchall()
    conn.close()
    
    # Return in chronological order (oldest first)
    messages = []
    for row in reversed(results):
        role, content, sources_json, confidence, timestamp = row
        sources = json.loads(sources_json) if sources_json else None
        
        messages.append({
            'role': role,
            'content': content,
            'sources': sources,
            'confidence_score': confidence,
            'timestamp': timestamp
        })
    
    return messages

def build_context_for_ai(conversation_id, current_question):
    """
    Build context string for AI including conversation history
    Helps AI understand references like "that product" or "the fungicide I mentioned"
    """
    history = get_conversation_history(conversation_id, limit=5)
    
    if not history:
        return current_question
    
    # Build context string
    context_parts = ["Previous conversation context:\n"]
    
    for msg in history:
        if msg['role'] == 'user':
            context_parts.append(f"User asked: {msg['content']}")
        elif msg['role'] == 'assistant':
            # Summarize AI's answer (first 200 chars)
            summary = msg['content'][:200] + "..." if len(msg['content']) > 200 else msg['content']
            context_parts.append(f"You answered: {summary}")
    
    context_parts.append(f"\nCurrent question: {current_question}")
    
    return "\n".join(context_parts)

def get_source_quality_score(source: dict) -> float:
    """
    Score source quality based on type and origin.
    Returns a multiplier (0.5 to 1.5) for confidence weighting.
    """
    source_name = (source.get('name') or '').lower()
    source_type = (source.get('type') or '').lower()
    source_url = (source.get('url') or '').lower()

    # Highest quality: Official labels and university extension
    high_quality = [
        'label', 'sds', 'msds', 'specimen', 'epa',
        '.edu', 'extension', 'university', 'usga', 'gcsaa', 'ntep',
        'ifas', 'ipm', 'agcenter', 'turffiles'
    ]
    if any(kw in source_name or kw in source_type or kw in source_url for kw in high_quality):
        return 1.3

    # Good quality: Manufacturer technical docs and curated disease/pest guides
    good_quality = [
        'bayer', 'syngenta', 'basf', 'corteva', 'nufarm', 'pbi gordon',
        'fmc', 'envu', 'quali-pro', 'primesource', 'solution sheet',
        'technical bulletin', 'tech sheet',
        'greencast', 'nc state', 'penn state', 'disease_guide',
        'weed_guide', 'pest_guide', 'nematode_guide', 'abiotic'
    ]
    if any(kw in source_name or kw in source_type for kw in good_quality):
        return 1.1

    # Unknown sources get lower weight
    return 0.8


def calculate_confidence_score(sources, answer_text, question=""):
    """
    Calculate confidence score based on source quality and answer characteristics.

    Score philosophy:
    - Having sources at all means we found relevant documents → start at a solid base
    - Quality sources, specific details, and longer answers boost further
    - Only penalize for real red flags (rate question with no rates)
    """
    if not sources:
        return 35.0  # No sources = genuinely low confidence

    answer_lower = answer_text.lower()
    question_lower = question.lower()

    # Start with base score — we have sources, so baseline is reasonable
    score = 55.0

    # Factor 1: Source quality weighted count (up to +20)
    quality_sum = sum(get_source_quality_score(s) for s in sources)
    if quality_sum >= 4.0:
        score += 20
    elif quality_sum >= 3.0:
        score += 16
    elif quality_sum >= 2.0:
        score += 12
    elif quality_sum >= 1.0:
        score += 8
    else:
        score += 4

    # Factor 2: Answer specificity (up to +15)
    has_rates = any(unit in answer_lower for unit in [
        'oz', 'lb', 'fl oz', 'pint', 'gallon', 'acre', '1000 sq ft',
        'per 1000', '/1000', '/acre', 'ppm', 'percent', '%'
    ])
    has_numbers = bool(re.search(r'\d+\.?\d*\s*(oz|lb|gal|pint|acre|sq ft)', answer_lower))
    has_products = any(product in answer_lower for product in [
        'heritage', 'daconil', 'banner', 'primo', 'bayleton', 'propiconazole',
        'chlorothalonil', 'azoxystrobin', 'fludioxonil', 'roundup', 'certainty',
        'revolver', 'celsius', 'tenacity', 'mirage', 'bravo', 'medallion',
        'insignia', 'headway', 'lexicon', 'velista', 'pillar', 'appear'
    ])

    if has_rates and has_numbers:
        score += 12
    elif has_rates:
        score += 8
    elif has_numbers:
        score += 5

    if has_products:
        score += 5

    # Factor 3: Answer completeness (up to +8)
    if len(answer_text) > 400:
        score += 8
    elif len(answer_text) > 250:
        score += 5
    elif len(answer_text) > 100:
        score += 3

    # Factor 4: Question type risk adjustment
    # Rate-specific questions need higher bar - penalize if no verified rate
    rate_question = any(kw in question_lower for kw in [
        'rate', 'how much', 'dosage', 'application rate', 'oz per', 'lb per'
    ])
    if rate_question and not has_rates:
        score -= 10  # Can't answer rate question without rates

    # Cap at 100, floor at 25
    return max(25.0, min(score, 100.0))

def get_confidence_label(score):
    """Convert numeric score (0-100) to user-facing label"""
    if score >= 75:
        return "High Confidence"
    elif score >= 55:
        return "Good Confidence"
    elif score >= 40:
        return "Moderate Confidence"  # Needs review
    else:
        return "Low Confidence"  # Needs review

# Initialize database on import
try:
    init_database()
except Exception as e:
    logging.getLogger(__name__).error(f"Failed to initialize chat database: {e}")

if __name__ == "__main__":
    
    print("\nTesting Chat History System...\n")
    
    
    session_id, conv_id = create_session()
    print(f"Created session: {session_id}")
    print(f"Conversation ID: {conv_id}")
    
   
    save_message(conv_id, 'user', 'What fungicide for dollar spot?')
    save_message(conv_id, 'assistant', 'Heritage at 0.16 oz/1000 sq ft', 
                sources=[{'name': 'Heritage Label', 'type': 'label'}],
                confidence_score=0.85)
    
    save_message(conv_id, 'user', 'Can I tank mix that with Primo?')
    
   
    context = build_context_for_ai(conv_id, 'Can I tank mix that with Primo?')
    print(f"\nContext built:\n{context}\n")
    
    
    history = get_conversation_history(conv_id)
    print(f"\nConversation history ({len(history)} messages):")
    for msg in history:
        print(f"  {msg['role']}: {msg['content'][:50]}...")
        if msg['confidence_score']:
            label = get_confidence_label(msg['confidence_score'])
            print(f"    Confidence: {msg['confidence_score']:.2f} ({label})")