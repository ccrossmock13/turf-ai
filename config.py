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
    CHAT_MAX_TOKENS = int(os.getenv("CHAT_MAX_TOKENS", "1000"))
    CHAT_TEMPERATURE = float(os.getenv("CHAT_TEMPERATURE", "0.2"))

    # Optional: Web Search (Tavily)
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

    # Optional: Weather (OpenWeatherMap)
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

    # Demo mode — returns cached responses for common questions (zero API cost)
    DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"