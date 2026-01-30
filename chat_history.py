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
    Calculate confidence score based on question type and answer quality.
    Different criteria for different question types.
    """
    
    if not sources:
        return 0.0
    
    score = 0.0
    answer_lower = answer_text.lower()
    question_lower = question.lower() if question else ""
    
    # Detect question type
    is_product_question = any(word in question_lower for word in ['fungicide', 'herbicide', 'insecticide', 'pgr', 'product', 'rate', 'spray'])
    is_equipment_question = any(word in question_lower for word in ['equipment', 'irrigation', 'mower', 'sprayer', 'calibrate', 'repair', 'install'])
    is_cultural_question = any(word in question_lower for word in ['mowing', 'aerify', 'topdress', 'fertilize', 'water', 'practice', 'when to', 'how often'])
    is_diagnostic_question = any(word in question_lower for word in ['dying', 'yellowing', 'spots', 'patches', 'problem', 'what is', 'identify'])
    
    # PRODUCT QUESTIONS - Focus on rates and label sources
    if is_product_question:
        # Factor 1: Specific rates (max 0.4)
        has_specific_rate = any(unit in answer_lower for unit in ['oz/1000', 'fl oz/1000', 'lb/1000', 'pints/acre', 'oz/acre'])
        if has_specific_rate:
            score += 0.4
        elif 'rate' in answer_lower or 'application' in answer_lower:
            score += 0.2
        
        # Factor 2: Product labels (max 0.3)
        label_sources = sum(1 for s in sources if 'label' in s.get('type', '').lower())
        if label_sources >= 2:
            score += 0.3
        elif label_sources >= 1:
            score += 0.15
        
        # Factor 3: Multiple sources (max 0.2)
        if len(sources) >= 4:
            score += 0.2
        elif len(sources) >= 2:
            score += 0.1
        
        # Factor 4: Both chemical and cultural (max 0.1)
        if 'chemical' in answer_lower and 'cultural' in answer_lower:
            score += 0.1
    
    # EQUIPMENT/MAINTENANCE QUESTIONS - Focus on procedures and specs
    elif is_equipment_question:
        # Factor 1: Step-by-step or numbered list (max 0.4)
        has_steps = bool(re.search(r'\d+\.', answer_text)) or 'step' in answer_lower
        has_specific_numbers = bool(re.search(r'\d+\s*(inch|psi|gpm|rpm|degree)', answer_lower))
        if has_steps and has_specific_numbers:
            score += 0.4
        elif has_steps or has_specific_numbers:
            score += 0.25
        
        # Factor 2: Technical detail (max 0.3)
        technical_terms = ['valve', 'pressure', 'flow', 'solenoid', 'decoder', 'controller', 'wire', 'hydraulic']
        tech_count = sum(1 for term in technical_terms if term in answer_lower)
        if tech_count >= 3:
            score += 0.3
        elif tech_count >= 1:
            score += 0.15
        
        # Factor 3: Multiple sources (max 0.2)
        if len(sources) >= 3:
            score += 0.2
        elif len(sources) >= 1:
            score += 0.1
        
        # Factor 4: Completeness (max 0.1)
        if len(answer_text) > 300:
            score += 0.1
    
    # CULTURAL PRACTICE QUESTIONS - Focus on specific measurements and frequencies
    elif is_cultural_question:
        # Factor 1: Specific measurements/frequencies (max 0.4)
        has_measurements = bool(re.search(r'\d+\.?\d*\s*(inch|lb|oz|day|week|month|year)', answer_lower))
        has_frequency = any(word in answer_lower for word in ['daily', 'weekly', 'monthly', 'times per', 'every'])
        if has_measurements and has_frequency:
            score += 0.4
        elif has_measurements or has_frequency:
            score += 0.25
        
        # Factor 2: Grass type specificity (max 0.2)
        grass_types = ['bentgrass', 'bermudagrass', 'poa', 'ryegrass', 'fescue', 'bluegrass', 'zoysia']
        if any(grass in answer_lower for grass in grass_types):
            score += 0.2
        
        # Factor 3: Multiple sources (max 0.2)
        if len(sources) >= 3:
            score += 0.2
        elif len(sources) >= 1:
            score += 0.1
        
        # Factor 4: Reasoning provided (max 0.2)
        reasoning_indicators = ['why:', '→ why:', 'because', 'ensures', 'helps']
        if any(indicator in answer_lower for indicator in reasoning_indicators):
            score += 0.2
    
    # DIAGNOSTIC QUESTIONS - Focus on specificity and differential diagnosis
    elif is_diagnostic_question:
        # Factor 1: Specific diagnosis (max 0.3)
        diseases = ['dollar spot', 'brown patch', 'pythium', 'anthracnose', 'fairy ring', 'summer patch']
        if any(disease in answer_lower for disease in diseases):
            score += 0.3
        
        # Factor 2: Multiple possibilities or confidence qualifier (max 0.2)
        if 'could be' in answer_lower or 'likely' in answer_lower or 'possibly' in answer_lower:
            score += 0.2
        
        # Factor 3: Questions back to user (max 0.3)
        if '?' in answer_text:
            score += 0.3
        
        # Factor 4: Multiple sources (max 0.2)
        if len(sources) >= 3:
            score += 0.2
        elif len(sources) >= 1:
            score += 0.1
    
    # GENERAL QUESTIONS - Basic scoring
    else:
        # Factor 1: Number of sources (max 0.4)
        if len(sources) >= 5:
            score += 0.4
        elif len(sources) >= 3:
            score += 0.25
        elif len(sources) >= 1:
            score += 0.15
        
        # Factor 2: Answer length/detail (max 0.3)
        if len(answer_text) > 400:
            score += 0.3
        elif len(answer_text) > 200:
            score += 0.2
        elif len(answer_text) > 100:
            score += 0.1
        
        # Factor 3: Specific information (max 0.3)
        has_numbers = bool(re.search(r'\d+', answer_text))
        has_specifics = bool(re.search(r'\d+\.?\d*\s*\w+', answer_text))
        if has_specifics:
            score += 0.3
        elif has_numbers:
            score += 0.15
    
    return min(score, 1.0)  # Cap at 1.0

def get_confidence_label(score):
    """Convert numeric score to label"""
    if score >= 0.75:
        return "HIGH CONFIDENCE"
    elif score >= 0.5:
        return "MODERATE CONFIDENCE"
    elif score >= 0.25:
        return "LOW CONFIDENCE"
    else:
        return "VERY LOW CONFIDENCE - VERIFY"

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