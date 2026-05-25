import os
from dotenv import load_dotenv
from datetime import timedelta

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
    VISION_MODEL = os.getenv("VISION_MODEL", "gpt-4o-mini")
    MAX_IMAGE_UPLOAD_BYTES = int(os.getenv("MAX_IMAGE_UPLOAD_BYTES", str(5 * 1024 * 1024)))

    # Optional: Web Search (Tavily)
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

    # Optional: Weather (OpenWeatherMap)
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

    # Demo mode — returns cached responses for common questions (zero API cost)
    DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
    APP_ENV = (os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or "development").lower()
    DATA_DIR = os.getenv("DATA_DIR", "data")
    DEPLOYMENT_MODE = os.getenv("DEPLOYMENT_MODE", "development").lower()
    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() != "false"
    MAIL_FROM = os.getenv("MAIL_FROM")
    REQUIRE_EMAIL_VERIFICATION = os.getenv("REQUIRE_EMAIL_VERIFICATION", "false").lower() == "true"
    # Keep admin closed by default in every environment. If a developer wants
    # a temporary unauthenticated admin surface locally, they should opt into it
    # explicitly with ALLOW_PUBLIC_ADMIN=true.
    ALLOW_PUBLIC_ADMIN = os.getenv("ALLOW_PUBLIC_ADMIN", "false").lower() == "true"
    SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "greenside_session")
    SESSION_LIFETIME_HOURS = int(os.getenv("SESSION_LIFETIME_HOURS", "12"))
    ENFORCE_KB_TRUST_GATE = os.getenv("ENFORCE_KB_TRUST_GATE", "false").lower() == "true"
    KB_TRUST_MIN_HUMAN_REVIEW_PERCENT = float(os.getenv("KB_TRUST_MIN_HUMAN_REVIEW_PERCENT", "35"))
    KB_TRUST_MIN_REI_COVERAGE_PERCENT = float(os.getenv("KB_TRUST_MIN_REI_COVERAGE_PERCENT", "80"))
    KB_TRUST_MIN_IRRIGATION_COVERAGE_PERCENT = float(os.getenv("KB_TRUST_MIN_IRRIGATION_COVERAGE_PERCENT", "85"))
    KB_TRUST_MIN_TANK_MIX_COVERAGE_PERCENT = float(os.getenv("KB_TRUST_MIN_TANK_MIX_COVERAGE_PERCENT", "80"))
    KB_TRUST_MIN_MAX_RATE_COVERAGE_PERCENT = float(os.getenv("KB_TRUST_MIN_MAX_RATE_COVERAGE_PERCENT", "75"))
    PERSISTENCE_BACKEND = os.getenv("PERSISTENCE_BACKEND", "local").lower()
    AWS_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    DYNAMODB_ACCOUNTS_TABLE = os.getenv("DYNAMODB_ACCOUNTS_TABLE", "greenside-accounts")
    DYNAMODB_ACCOUNT_TOKENS_TABLE = os.getenv("DYNAMODB_ACCOUNT_TOKENS_TABLE", "greenside-account-tokens")
    DYNAMODB_COURSE_PROFILES_TABLE = os.getenv("DYNAMODB_COURSE_PROFILES_TABLE", "greenside-course-profiles")
    DYNAMODB_CHAT_TABLE = os.getenv("DYNAMODB_CHAT_TABLE", "greenside-chat")
    DYNAMODB_RATE_LIMIT_TABLE = os.getenv("DYNAMODB_RATE_LIMIT_TABLE", "greenside-rate-limits")
    DYNAMODB_FEEDBACK_TABLE = os.getenv("DYNAMODB_FEEDBACK_TABLE", "greenside-feedback")

    @classmethod
    def validate_runtime(cls):
        """Raise on unsafe production defaults."""
        if cls.APP_ENV == "production":
            if cls.FLASK_SECRET_KEY == "greenside-secret-key-change-in-production":
                raise RuntimeError("FLASK_SECRET_KEY must be set in production.")
            if not cls.OPENAI_API_KEY:
                raise RuntimeError("OPENAI_API_KEY must be set in production.")
            if not cls.PINECONE_API_KEY:
                raise RuntimeError("PINECONE_API_KEY must be set in production.")

            if cls.DEPLOYMENT_MODE not in {"single_node_persistent", "managed_storage"}:
                raise RuntimeError(
                    "DEPLOYMENT_MODE must be set to 'single_node_persistent' or 'managed_storage' in production."
                )
            if cls.PERSISTENCE_BACKEND not in {"local", "dynamodb"}:
                raise RuntimeError("PERSISTENCE_BACKEND must be 'local' or 'dynamodb'.")
            if cls.PERSISTENCE_BACKEND == "dynamodb" and not cls.AWS_REGION:
                raise RuntimeError("AWS_REGION must be set when PERSISTENCE_BACKEND=dynamodb.")

    @classmethod
    def session_lifetime(cls):
        return timedelta(hours=max(1, cls.SESSION_LIFETIME_HOURS))

    @classmethod
    def is_serverless(cls) -> bool:
        return any(
            os.getenv(name)
            for name in (
                "AWS_LAMBDA_FUNCTION_NAME",
                "FUNCTIONS_WORKER_RUNTIME",
                "WEBSITE_INSTANCE_ID",
                "K_SERVICE",
            )
        )
