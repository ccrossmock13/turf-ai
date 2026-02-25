import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "greenside-secret-key-change-in-production")
    DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    PORT = int(os.getenv("FLASK_PORT", "5001"))

    # API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

    # Pinecone
    PINECONE_INDEX = os.getenv("PINECONE_INDEX", "turf-research")

    # OpenAI Models
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o")
    CHAT_MAX_TOKENS = int(os.getenv("CHAT_MAX_TOKENS", "1500"))
    CHAT_TEMPERATURE = float(os.getenv("CHAT_TEMPERATURE", "0.2"))

    # Optional: Web Search (Tavily)
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

    # Optional: Weather (OpenWeatherMap)
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

    # Demo mode — returns cached responses for common questions (zero API cost)
    DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

    # --- Enterprise Intelligence: Cost Tracking ---
    # Per-token cost rates (USD) — update when pricing changes
    COST_RATES = {
        'gpt-4o': {'prompt': 2.50 / 1_000_000, 'completion': 10.00 / 1_000_000},
        'gpt-4o-mini': {'prompt': 0.150 / 1_000_000, 'completion': 0.600 / 1_000_000},
        'text-embedding-3-small': {'prompt': 0.020 / 1_000_000, 'completion': 0.0},
    }
    COST_BUDGET_DAILY = float(os.getenv("COST_BUDGET_DAILY", "10.00"))
    COST_BUDGET_MONTHLY = float(os.getenv("COST_BUDGET_MONTHLY", "200.00"))

    # --- Enterprise Intelligence: Alerting ---
    ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL")  # Slack/Teams/Discord
    ALERT_EMAIL_ENABLED = os.getenv("ALERT_EMAIL_ENABLED", "false").lower() == "true"
    ALERT_EMAIL_SMTP_HOST = os.getenv("ALERT_EMAIL_SMTP_HOST", "smtp.gmail.com")
    ALERT_EMAIL_SMTP_PORT = int(os.getenv("ALERT_EMAIL_SMTP_PORT", "587"))
    ALERT_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM")
    ALERT_EMAIL_PASSWORD = os.getenv("ALERT_EMAIL_PASSWORD")
    ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO")

    # --- Enterprise Intelligence: Circuit Breaker ---
    CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "5"))  # failures before open
    CIRCUIT_BREAKER_WINDOW = int(os.getenv("CIRCUIT_BREAKER_WINDOW", "300"))  # seconds
    CIRCUIT_BREAKER_RECOVERY = int(os.getenv("CIRCUIT_BREAKER_RECOVERY", "600"))  # seconds

    # --- Anthropic-Grade: Rate Limiting ---
    RATE_LIMIT_ASK_PER_MIN = int(os.getenv("RATE_LIMIT_ASK_PER_MIN", "30"))
    RATE_LIMIT_API_PER_MIN = int(os.getenv("RATE_LIMIT_API_PER_MIN", "100"))
    RATE_LIMIT_GLOBAL_PER_MIN = int(os.getenv("RATE_LIMIT_GLOBAL_PER_MIN", "500"))

    # --- Anthropic-Grade: Input Sanitization ---
    SANITIZATION_BLOCK_THRESHOLD = int(os.getenv("SANITIZATION_BLOCK_THRESHOLD", "8"))
    SANITIZATION_WARN_THRESHOLD = int(os.getenv("SANITIZATION_WARN_THRESHOLD", "4"))