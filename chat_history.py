"""
Chat History & Context Awareness System
Stores conversations and allows AI to reference previous questions
"""

import sqlite3
from datetime import datetime
import json
import hashlib
import re

DB_PATH = 'greenside_conversations.db'

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
    
    # Indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_session ON conversations(session_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conv_time ON messages(conversation_id, timestamp)')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

def create_session():
    """Create a new conversation session"""
    session_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO conversations (session_id)
        VALUES (?)
    ''', (session_id,))
    
    conversation_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return session_id, conversation_id

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

def calculate_confidence_score(sources, answer_text, question=""):
    """
    Calculate confidence score based on sources and answer quality.
    Simplified scoring that produces more reasonable results.
    """
    if not sources:
        return 30.0  # Base score even without sources

    score = 40.0  # Start with base score
    answer_lower = answer_text.lower()

    # Factor 1: Number of sources (up to +30)
    num_sources = len(sources)
    if num_sources >= 5:
        score += 30
    elif num_sources >= 3:
        score += 25
    elif num_sources >= 2:
        score += 20
    elif num_sources >= 1:
        score += 15

    # Factor 2: Answer has specific information (up to +20)
    # Check for numbers, rates, product names
    has_numbers = bool(re.search(r'\d+', answer_text))
    has_rates = any(unit in answer_lower for unit in [
        'oz', 'lb', 'fl oz', 'pint', 'gallon', 'acre', '1000 sq ft',
        'per 1000', '/1000', '/acre', 'ppm', 'percent', '%'
    ])
    has_products = any(product in answer_lower for product in [
        'heritage', 'daconil', 'banner', 'primo', 'bayleton', 'propiconazole',
        'chlorothalonil', 'azoxystrobin', 'fludioxonil', 'roundup', 'certainty'
    ])

    if has_rates:
        score += 15
    elif has_numbers:
        score += 10

    if has_products:
        score += 5

    # Factor 3: Answer length/detail (up to +10)
    if len(answer_text) > 500:
        score += 10
    elif len(answer_text) > 300:
        score += 7
    elif len(answer_text) > 150:
        score += 5

    # Cap at 100
    return min(score, 100.0)

def get_confidence_label(score):
    """Convert numeric score (0-100) to label"""
    if score >= 80:
        return "High Confidence"
    elif score >= 60:
        return "Medium Confidence"
    else:
        return "Low Confidence"

# Initialize database on import
init_database()

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