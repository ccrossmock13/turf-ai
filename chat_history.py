"""
Chat History & Context Awareness System
Stores conversations and allows AI to reference previous questions
"""

import os
import logging
from datetime import datetime
import json
import hashlib
import re

from db import get_db, is_postgres, add_column, CONVERSATIONS_DB, FEEDBACK_DB

logger = logging.getLogger(__name__)

DATA_DIR = os.environ.get('DATA_DIR', 'data' if os.path.exists('data') else '.')
DB_PATH = os.path.join(DATA_DIR, 'greenside_conversations.db')

def init_database():
    """Initialize database for chat history. Works with both SQLite and PostgreSQL."""
    with get_db() as conn:
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
        add_column(conn, 'users', 'is_admin', 'BOOLEAN DEFAULT 0')
        conn.execute('UPDATE users SET is_admin = 1 WHERE id = 1 AND is_admin = 0')

        # Course profiles table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS course_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                course_name TEXT NOT NULL DEFAULT 'My Course',
                is_active INTEGER DEFAULT 1,
                city TEXT, state TEXT, region TEXT,
                primary_grass TEXT, secondary_grasses TEXT,
                turf_type TEXT, role TEXT,
                greens_grass TEXT, fairways_grass TEXT, rough_grass TEXT, tees_grass TEXT,
                soil_type TEXT, irrigation_source TEXT,
                mowing_heights TEXT, annual_n_budget TEXT,
                notes TEXT, cultivars TEXT,
                greens_acreage REAL, fairways_acreage REAL, rough_acreage REAL, tees_acreage REAL,
                default_gpa REAL, tank_size REAL,
                soil_ph REAL, soil_om REAL, water_ph REAL, water_ec REAL,
                green_speed_target REAL, budget_tier TEXT, climate_zone TEXT,
                common_problems TEXT, preferred_products TEXT, overseeding_program TEXT,
                irrigation_schedule TEXT, aerification_program TEXT,
                topdressing_program TEXT, pgr_program TEXT,
                wetting_agent_program TEXT, maintenance_calendar TEXT, bunker_sand TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, course_name),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # Indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_session ON conversations(session_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_conv_time ON messages(conversation_id, timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_profiles_user ON course_profiles(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_profiles_active ON course_profiles(user_id, is_active)')

        # Migration: add user_id to conversations (idempotent)
        add_column(conn, 'conversations', 'user_id', 'INTEGER REFERENCES users(id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id)')

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
                products_json TEXT,
                application_method TEXT,
                efficacy_rating INTEGER,
                efficacy_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_spray_user ON spray_applications(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_spray_date ON spray_applications(user_id, date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_spray_area ON spray_applications(user_id, area)')

        # Custom products table
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

        # Sprayers table
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

        # User inventory
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

        # Spray program templates
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS spray_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                products_json TEXT NOT NULL,
                application_method TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_templates_user ON spray_templates(user_id)')

        # Inventory quantity tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory_quantities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id TEXT NOT NULL,
                quantity REAL DEFAULT 0,
                unit TEXT DEFAULT 'lbs',
                supplier TEXT,
                cost_per_unit REAL,
                notes TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, product_id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_inv_qty_user ON inventory_quantities(user_id)')

        # SQLite-only migration: fix old schema with UNIQUE(user_id) on course_profiles
        if not is_postgres():
            try:
                cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='course_profiles'")
                schema_row = cursor.fetchone()
                if schema_row and 'user_id INTEGER NOT NULL UNIQUE' in (schema_row[0] or ''):
                    cursor.execute("UPDATE course_profiles SET course_name = 'My Course' WHERE course_name IS NULL OR course_name = ''")
                    cursor.execute('''
                        CREATE TABLE course_profiles_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            course_name TEXT NOT NULL DEFAULT 'My Course',
                            is_active INTEGER DEFAULT 1,
                            city TEXT, state TEXT, region TEXT,
                            primary_grass TEXT, secondary_grasses TEXT,
                            turf_type TEXT, role TEXT,
                            greens_grass TEXT, fairways_grass TEXT, rough_grass TEXT, tees_grass TEXT,
                            soil_type TEXT, irrigation_source TEXT,
                            mowing_heights TEXT, annual_n_budget TEXT,
                            notes TEXT, cultivars TEXT,
                            greens_acreage REAL, fairways_acreage REAL, rough_acreage REAL, tees_acreage REAL,
                            default_gpa REAL, tank_size REAL,
                            soil_ph REAL, soil_om REAL, water_ph REAL, water_ec REAL,
                            green_speed_target REAL, budget_tier TEXT, climate_zone TEXT,
                            common_problems TEXT, preferred_products TEXT, overseeding_program TEXT,
                            irrigation_schedule TEXT, aerification_program TEXT,
                            topdressing_program TEXT, pgr_program TEXT,
                            wetting_agent_program TEXT, maintenance_calendar TEXT, bunker_sand TEXT,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE(user_id, course_name),
                            FOREIGN KEY (user_id) REFERENCES users(id)
                        )
                    ''')
                    cursor.execute('''
                        INSERT INTO course_profiles_new (
                            id, user_id, course_name, is_active,
                            city, state, region,
                            primary_grass, secondary_grasses, turf_type, role,
                            greens_grass, fairways_grass, rough_grass, tees_grass,
                            soil_type, irrigation_source, mowing_heights, annual_n_budget,
                            notes, cultivars,
                            greens_acreage, fairways_acreage, rough_acreage, tees_acreage,
                            default_gpa, tank_size,
                            soil_ph, soil_om, water_ph, water_ec,
                            green_speed_target, budget_tier, climate_zone,
                            common_problems, preferred_products, overseeding_program,
                            irrigation_schedule, aerification_program,
                            topdressing_program, pgr_program,
                            wetting_agent_program, maintenance_calendar, bunker_sand,
                            updated_at
                        )
                        SELECT
                            id, user_id, COALESCE(course_name, 'My Course'), COALESCE(is_active, 1),
                            city, state, region,
                            primary_grass, secondary_grasses, turf_type, role,
                            greens_grass, fairways_grass, rough_grass, tees_grass,
                            soil_type, irrigation_source, mowing_heights, annual_n_budget,
                            notes, cultivars,
                            greens_acreage, fairways_acreage, rough_acreage, tees_acreage,
                            default_gpa, tank_size,
                            soil_ph, soil_om, water_ph, water_ec,
                            green_speed_target, budget_tier, climate_zone,
                            common_problems, preferred_products, overseeding_program,
                            irrigation_schedule, aerification_program,
                            topdressing_program, pgr_program,
                            wetting_agent_program, maintenance_calendar, bunker_sand,
                            updated_at
                        FROM course_profiles
                    ''')
                    cursor.execute('DROP TABLE course_profiles')
                    cursor.execute('ALTER TABLE course_profiles_new RENAME TO course_profiles')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_profiles_user ON course_profiles(user_id)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_profiles_active ON course_profiles(user_id, is_active)')
                    logger.info("Multi-course migration completed")
            except Exception as e:
                logger.warning(f"Multi-course migration skipped: {e}")

    # Also initialize feedback database tables
    _init_feedback_tables()

    print("✅ Database initialized")


def _init_feedback_tables():
    """Initialize feedback tables. Uses FEEDBACK_DB for SQLite, same PG database."""
    db_path = FEEDBACK_DB if not is_postgres() else None
    with get_db(db_path) as conn:
        cursor = conn.cursor()

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
                needs_review BOOLEAN DEFAULT 0,
                notes TEXT
            )
        ''')

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

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rating ON feedback(user_rating)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_reviewed ON feedback(reviewed)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_approved ON feedback(approved_for_training)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mod_actions ON moderator_actions(feedback_id)')


def create_session(user_id=None):
    """Create a new conversation session, optionally bound to a user."""
    session_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO conversations (session_id, user_id)
                VALUES (?, ?)
            ''', (session_id, user_id))
            conversation_id = cursor.lastrowid
    except Exception as e:
        logger.error(f"DB error in create_session: {e}")
        return session_id, 0

    return session_id, conversation_id


def get_user_conversations(user_id, limit=50):
    """Get conversation summaries for a user."""
    with get_db() as conn:
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

    return [{
        'id': r[0], 'session_id': r[1], 'created_at': r[2],
        'last_active': r[3], 'first_question': r[4], 'message_count': r[5]
    } for r in rows]

def get_conversation_id(session_id):
    """Get conversation ID from session ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM conversations WHERE session_id = ?
        ''', (session_id,))
        result = cursor.fetchone()

    return result[0] if result else None

def save_message(conversation_id, role, content, sources=None, confidence_score=None):
    """Save a message to the database"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            sources_json = json.dumps(sources) if sources else None

            cursor.execute('''
                INSERT INTO messages (conversation_id, role, content, sources, confidence_score)
                VALUES (?, ?, ?, ?, ?)
            ''', (conversation_id, role, content, sources_json, confidence_score))

            cursor.execute('''
                UPDATE conversations
                SET last_active = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (conversation_id,))
    except Exception as e:
        logger.error(f"DB error in save_message: {e}")

def get_conversation_history(conversation_id, limit=10):
    """Get recent messages from a conversation"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT role, content, sources, confidence_score, timestamp
            FROM messages
            WHERE conversation_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (conversation_id, limit))
        results = cursor.fetchall()

    # Return in chronological order (oldest first)
    messages = []
    for row in reversed(results):
        role, content, sources_json, confidence, timestamp = row[0], row[1], row[2], row[3], row[4]
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
    """
    if not sources:
        return 35.0

    answer_lower = answer_text.lower()
    question_lower = question.lower()

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
    rate_question = any(kw in question_lower for kw in [
        'rate', 'how much', 'dosage', 'application rate', 'oz per', 'lb per'
    ])
    if rate_question and not has_rates:
        score -= 10

    return max(25.0, min(score, 100.0))

def get_confidence_label(score):
    """Convert numeric score (0-100) to user-facing label"""
    if score >= 75:
        return "High Confidence"
    elif score >= 55:
        return "Good Confidence"
    elif score >= 40:
        return "Moderate Confidence"
    else:
        return "Low Confidence"

# Initialize database on import
try:
    init_database()
except Exception as e:
    logger.error(f"Failed to initialize chat database: {e}")

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
