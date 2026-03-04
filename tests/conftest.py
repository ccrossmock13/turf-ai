"""
Pytest configuration and shared fixtures for Greenside AI tests.
"""

import os
import sys

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment variables before importing app
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key")
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")
os.environ.setdefault("PINECONE_API_KEY", "test-key-not-real")
os.environ.setdefault("PINECONE_INDEX", "turf-research")
os.environ.setdefault("DATA_DIR", "data")
os.environ.setdefault("DEMO_MODE", "true")


@pytest.fixture
def flask_app():
    """Create a Flask test app with in-memory SQLite and all blueprints."""
    # Monkey-patch Pinecone before importing app
    import pinecone

    class FakeIndex:
        def describe_index_stats(self):
            return {"total_vector_count": 0}

        def query(self, **kw):
            return {"matches": []}

    pinecone.Pinecone.__init__ = lambda self, *a, **kw: None
    pinecone.Pinecone.Index = lambda self, name: FakeIndex()

    import app as app_module

    app_module.app.config["TESTING"] = True
    return app_module.app


@pytest.fixture
def client(flask_app):
    """Unauthenticated Flask test client."""
    return flask_app.test_client()


@pytest.fixture
def auth_client(flask_app):
    """Authenticated Flask test client with user_id=1 in session."""
    with flask_app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = 1
            sess["user_name"] = "Test User"
            sess["user_email"] = "test@greenside.ai"
            sess["csrf_token"] = "test-csrf-token"
        # Patch all requests to include CSRF header
        original_open = c.open

        def csrf_open(*args, **kwargs):
            headers = kwargs.get("headers", {})
            if isinstance(headers, dict):
                headers.setdefault("X-CSRF-Token", "test-csrf-token")
            kwargs["headers"] = headers
            return original_open(*args, **kwargs)

        c.open = csrf_open
        yield c


@pytest.fixture
def sample_question():
    return "What is the Heritage fungicide rate for bentgrass greens?"


@pytest.fixture
def sample_answer():
    return (
        "Heritage (azoxystrobin) should be applied at 0.2-0.4 oz per 1,000 sq ft "
        "for dollar spot control on bentgrass greens. Apply on a 14-21 day interval. "
        "Heritage is a FRAC Group 11 strobilurin fungicide."
    )


@pytest.fixture
def sample_context():
    return (
        "[Source 1: heritage-label.pdf]\n"
        "Heritage Fungicide (azoxystrobin 50% WDG)\n"
        "Application Rate: 0.2-0.4 oz/1,000 sq ft\n"
        "Interval: 14-28 days\n"
        "FRAC Group 11\n\n---\n\n"
        "[Source 2: dollar-spot-program.pdf]\n"
        "Dollar spot management program for bentgrass greens.\n"
        "Rotate FRAC groups to prevent resistance."
    )


@pytest.fixture
def sample_sources():
    return [
        {"name": "heritage-label.pdf", "url": "/product-labels/heritage-label.pdf", "score": 0.92},
        {"name": "dollar-spot-program.pdf", "url": "/spray-programs/dollar-spot-program.pdf", "score": 0.85},
    ]


@pytest.fixture
def sample_search_results():
    """Mock Pinecone search results."""
    return [
        {
            "id": "chunk-1",
            "score": 0.92,
            "metadata": {
                "text": "Heritage (azoxystrobin) rate: 0.2-0.4 oz per 1000 sq ft for dollar spot.",
                "source": "heritage-label.pdf",
            },
        },
        {
            "id": "chunk-2",
            "score": 0.85,
            "metadata": {
                "text": "Dollar spot control on bentgrass: rotate FRAC 11 and FRAC 7 fungicides.",
                "source": "dollar-spot-program.pdf",
            },
        },
        {
            "id": "chunk-3",
            "score": 0.78,
            "metadata": {
                "text": "Daconil chlorothalonil rate for brown patch on tall fescue fairways.",
                "source": "daconil-label.pdf",
            },
        },
    ]
