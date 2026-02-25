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
