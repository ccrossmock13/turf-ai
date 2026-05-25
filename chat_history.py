"""
Chat History & Context Awareness System
Stores conversations and allows AI to reference previous questions
"""

import hashlib
import json
import logging
import os
import re
import sqlite3
import uuid
from datetime import datetime

from config import Config
from persistence_backend import dynamodb_query_all, dynamodb_scan_all, dynamodb_table, to_plain_value, using_dynamodb

try:  # pragma: no cover - boto3 is deployment-specific
    from boto3.dynamodb.conditions import Attr, Key
except Exception:  # pragma: no cover
    Attr = None
    Key = None

# Use data directory for Docker persistence, fallback to current dir for local dev
DATA_DIR = os.environ.get('DATA_DIR', 'data' if os.path.exists('data') else '.')
DB_PATH = os.path.join(DATA_DIR, 'greenside_conversations.db')

def init_database():
    """Initialize SQLite database for chat history"""
    if using_dynamodb():
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Conversations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            account_id TEXT,
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
    
    cursor.execute("PRAGMA table_info(conversations)")
    columns = {row[1] for row in cursor.fetchall()}
    if "account_id" not in columns:
        cursor.execute("ALTER TABLE conversations ADD COLUMN account_id TEXT")

    # Indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_session ON conversations(session_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_account_session ON conversations(account_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conv_time ON messages(conversation_id, timestamp)')
    
    conn.commit()
    conn.close()
    logging.getLogger(__name__).debug("Chat history database initialized")


def create_session(account_id=None, user_info=None):
    """Create a new conversation session"""
    session_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()
    if using_dynamodb():
        conversation_id = uuid.uuid4().hex
        now = datetime.utcnow().isoformat()
        table = dynamodb_table(Config.DYNAMODB_CHAT_TABLE)
        table.put_item(
            Item={
                "pk": f"conversation#{conversation_id}",
                "sk": "meta",
                "entity_type": "conversation",
                "conversation_id": conversation_id,
                "session_id": session_id,
                "account_id": account_id,
                "created_at": now,
                "last_active": now,
                "user_info": user_info or {},
            }
        )
        table.put_item(
            Item={
                "pk": f"session#{session_id}",
                "sk": f"conversation#{conversation_id}",
                "entity_type": "session_lookup",
                "conversation_id": conversation_id,
                "session_id": session_id,
                "account_id": account_id,
                "created_at": now,
            }
        )
        return session_id, conversation_id
    init_database()

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        user_info_json = json.dumps(user_info) if user_info else None

        cursor.execute('''
            INSERT INTO conversations (session_id, account_id, user_info)
            VALUES (?, ?, ?)
        ''', (session_id, account_id, user_info_json))

        conversation_id = cursor.lastrowid
        conn.commit()
        conn.close()
    except Exception as e:
        logging.getLogger(__name__).error(f"DB error in create_session: {e}")
        return session_id, 0

    return session_id, conversation_id


def set_conversation_account(conversation_id, account_id, user_info=None):
    """Associate an existing conversation with an account."""
    if not conversation_id or not account_id:
        return
    if using_dynamodb():
        table = dynamodb_table(Config.DYNAMODB_CHAT_TABLE)
        response = table.get_item(Key={"pk": f"conversation#{conversation_id}", "sk": "meta"})
        item = to_plain_value(response.get("Item") or {})
        if not item:
            return
        item["account_id"] = account_id
        item["last_active"] = datetime.utcnow().isoformat()
        if user_info is not None:
            item["user_info"] = user_info
        table.put_item(Item=item)
        return
    init_database()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        user_info_json = json.dumps(user_info) if user_info else None
        if user_info_json is not None:
            cursor.execute(
                '''
                UPDATE conversations
                SET account_id = ?, user_info = ?, last_active = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (account_id, user_info_json, conversation_id),
            )
        else:
            cursor.execute(
                '''
                UPDATE conversations
                SET account_id = ?, last_active = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (account_id, conversation_id),
            )
        conn.commit()
        conn.close()
    except Exception as e:
        logging.getLogger(__name__).error(f"DB error in set_conversation_account: {e}")

def get_conversation_id(session_id):
    """Get conversation ID from session ID"""
    if using_dynamodb():
        if Key is None:
            raise RuntimeError("boto3 is required for the DynamoDB persistence backend.")
        table = dynamodb_table(Config.DYNAMODB_CHAT_TABLE)
        items = dynamodb_query_all(
            table,
            KeyConditionExpression=Key("pk").eq(f"session#{session_id}"),
        )
        return items[0].get("conversation_id") if items else None
    init_database()
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
        if using_dynamodb():
            table = dynamodb_table(Config.DYNAMODB_CHAT_TABLE)
            now = datetime.utcnow().isoformat()
            message_id = uuid.uuid4().hex
            table.put_item(
                Item={
                    "pk": f"conversation#{conversation_id}",
                    "sk": f"message#{now}#{message_id}",
                    "entity_type": "message",
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "role": role,
                    "content": content,
                    "sources": sources or [],
                    "confidence_score": confidence_score,
                    "timestamp": now,
                }
            )
            meta_response = table.get_item(Key={"pk": f"conversation#{conversation_id}", "sk": "meta"})
            meta = to_plain_value(meta_response.get("Item") or {})
            if meta:
                meta["last_active"] = now
                table.put_item(Item=meta)
            return
        init_database()
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
    if using_dynamodb():
        if Key is None:
            raise RuntimeError("boto3 is required for the DynamoDB persistence backend.")
        table = dynamodb_table(Config.DYNAMODB_CHAT_TABLE)
        items = dynamodb_query_all(
            table,
            KeyConditionExpression=Key("pk").eq(f"conversation#{conversation_id}"),
        )
        messages = [
            {
                "role": item.get("role"),
                "content": item.get("content"),
                "sources": item.get("sources"),
                "confidence_score": item.get("confidence_score"),
                "timestamp": item.get("timestamp"),
            }
            for item in items
            if item.get("entity_type") == "message"
        ]
        messages.sort(key=lambda item: item.get("timestamp") or "")
        return messages[-limit:]
    init_database()
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


def export_account_conversations(account_id):
    """Export all stored conversations and messages for one account."""
    if not account_id:
        return []
    if using_dynamodb():
        if Attr is None:
            raise RuntimeError("boto3 is required for the DynamoDB persistence backend.")
        table = dynamodb_table(Config.DYNAMODB_CHAT_TABLE)
        conversations = dynamodb_scan_all(
            table,
            FilterExpression=Attr("entity_type").eq("conversation") & Attr("account_id").eq(account_id),
        )
        exports = []
        for convo in sorted(conversations, key=lambda item: item.get("created_at") or ""):
            messages = get_conversation_history(convo.get("conversation_id"), limit=1000)
            exports.append(
                {
                    "conversation_id": convo.get("conversation_id"),
                    "session_id": convo.get("session_id"),
                    "created_at": convo.get("created_at"),
                    "last_active": convo.get("last_active"),
                    "user_info": convo.get("user_info"),
                    "messages": messages,
                }
            )
        return exports
    init_database()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT id, session_id, created_at, last_active, user_info
        FROM conversations
        WHERE account_id = ?
        ORDER BY created_at ASC
        ''',
        (account_id,),
    )
    conversation_rows = cursor.fetchall()
    exports = []
    for conversation_id, session_id, created_at, last_active, user_info_json in conversation_rows:
        cursor.execute(
            '''
            SELECT role, content, sources, confidence_score, timestamp
            FROM messages
            WHERE conversation_id = ?
            ORDER BY timestamp ASC, id ASC
            ''',
            (conversation_id,),
        )
        message_rows = cursor.fetchall()
        messages = []
        for role, content, sources_json, confidence_score, timestamp in message_rows:
            messages.append(
                {
                    "role": role,
                    "content": content,
                    "sources": json.loads(sources_json) if sources_json else None,
                    "confidence_score": confidence_score,
                    "timestamp": timestamp,
                }
            )
        exports.append(
            {
                "conversation_id": conversation_id,
                "session_id": session_id,
                "created_at": created_at,
                "last_active": last_active,
                "user_info": json.loads(user_info_json) if user_info_json else None,
                "messages": messages,
            }
        )
    conn.close()
    return exports


def delete_account_conversations(account_id):
    """Purge all conversations and messages tied to one account."""
    if not account_id:
        return 0
    if using_dynamodb():
        if Attr is None or Key is None:
            raise RuntimeError("boto3 is required for the DynamoDB persistence backend.")
        table = dynamodb_table(Config.DYNAMODB_CHAT_TABLE)
        conversations = dynamodb_scan_all(
            table,
            FilterExpression=Attr("entity_type").eq("conversation") & Attr("account_id").eq(account_id),
        )
        for convo in conversations:
            convo_id = convo.get("conversation_id")
            session_id = convo.get("session_id")
            items = dynamodb_query_all(
                table,
                KeyConditionExpression=Key("pk").eq(f"conversation#{convo_id}"),
            )
            for item in items:
                table.delete_item(Key={"pk": item["pk"], "sk": item["sk"]})
            if session_id:
                table.delete_item(Key={"pk": f"session#{session_id}", "sk": f"conversation#{convo_id}"})
        return len(conversations)
    init_database()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM conversations WHERE account_id = ?', (account_id,))
    conversation_ids = [row[0] for row in cursor.fetchall()]
    deleted = len(conversation_ids)
    for conversation_id in conversation_ids:
        cursor.execute('DELETE FROM messages WHERE conversation_id = ?', (conversation_id,))
    cursor.execute('DELETE FROM conversations WHERE account_id = ?', (account_id,))
    conn.commit()
    conn.close()
    return deleted

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
        'structured_reference', 'knowledge base'
    ]
    if any(kw in source_name or kw in source_type or kw in source_url for kw in high_quality):
        return 1.3

    # Good quality: Manufacturer technical docs
    good_quality = [
        'bayer', 'syngenta', 'basf', 'corteva', 'nufarm', 'pbi gordon',
        'fmc', 'envu', 'quali-pro', 'primesource', 'solution sheet',
        'technical bulletin', 'tech sheet'
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
