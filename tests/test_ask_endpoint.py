"""
Integration tests for the /ask endpoint.
Tests the full pipeline with mocked OpenAI and Pinecone services.
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test env vars before any app imports
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key")
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")
os.environ.setdefault("PINECONE_API_KEY", "test-key-not-real")
os.environ.setdefault("PINECONE_INDEX", "turf-research")
os.environ.setdefault("DATA_DIR", "data")
os.environ.setdefault("DEMO_MODE", "false")

# Mock Pinecone at the module level BEFORE app is imported.
# app.py calls pc.Index() at import time, so we must intercept
# the Pinecone class in the pinecone package itself.
_mock_pinecone_cls = MagicMock()
_mock_index = MagicMock()
_mock_pinecone_cls.return_value.Index.return_value = _mock_index

with patch('pinecone.Pinecone', _mock_pinecone_cls):
    from app import app as _app


@pytest.fixture
def app_client():
    """Create a Flask test client with mocked external services."""
    _app.config['TESTING'] = True
    _app.config['SECRET_KEY'] = 'test-secret'
    with _app.test_client() as client:
        # Simulate logged-in user session
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_name'] = 'Test User'
            sess['user_email'] = 'test@example.com'
            sess['session_id'] = 'test-session-123'
            sess['conversation_id'] = 1
        yield client


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI chat completion response."""
    mock_choice = MagicMock()
    mock_choice.message.content = (
        "Heritage (azoxystrobin, FRAC 11) should be applied at 0.2-0.4 oz/1,000 sq ft "
        "for dollar spot control on bentgrass greens. Apply on 14-21 day intervals."
    )
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 500
    mock_usage.completion_tokens = 100

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage
    return mock_response


@pytest.fixture
def mock_pinecone_results():
    """Mock Pinecone query results."""
    return {
        'matches': [
            {
                'id': 'chunk-1',
                'score': 0.92,
                'metadata': {
                    'text': 'Heritage (azoxystrobin) rate: 0.2-0.4 oz per 1000 sq ft.',
                    'source': 'heritage-label.pdf',
                }
            },
            {
                'id': 'chunk-2',
                'score': 0.85,
                'metadata': {
                    'text': 'Dollar spot control on bentgrass: rotate FRAC 11 and FRAC 7.',
                    'source': 'dollar-spot-program.pdf',
                }
            }
        ]
    }


class TestAskEndpointBasics:
    """Test basic /ask endpoint behavior."""

    def test_empty_question_returns_prompt(self, app_client):
        """Empty question should return a friendly prompt."""
        response = app_client.post('/ask',
            data=json.dumps({'question': ''}),
            content_type='application/json')
        assert response.status_code == 200
        data = response.get_json()
        assert 'Please enter a question' in data['answer']
        assert data['confidence']['score'] == 0

    def test_whitespace_question_returns_prompt(self, app_client):
        """Whitespace-only question should return a friendly prompt."""
        response = app_client.post('/ask',
            data=json.dumps({'question': '   '}),
            content_type='application/json')
        assert response.status_code == 200
        data = response.get_json()
        assert 'Please enter a question' in data['answer']

    def test_unauthenticated_request_returns_401(self):
        """Request without session should return 401."""
        _app.config['TESTING'] = True
        with patch('config.Config.DEMO_MODE', False):
            with _app.test_client() as client:
                response = client.post('/ask',
                    data=json.dumps({'question': 'test'}),
                    content_type='application/json',
                    headers={'X-Requested-With': 'XMLHttpRequest'})
                assert response.status_code == 401


class TestAskEndpointPipeline:
    """Test the full pipeline with mocked services."""

    @patch('pipeline.search_all_parallel')
    @patch('pipeline.classify_query')
    @patch('pipeline.rewrite_query')
    @patch('pipeline.check_feasibility')
    @patch('pipeline.check_answer_grounding')
    def test_full_pipeline_returns_answer(self, mock_grounding, mock_feasibility,
                                          mock_rewrite, mock_classify,
                                          mock_search, app_client,
                                          mock_openai_response, mock_pinecone_results):
        """Full pipeline should return a structured response with answer, sources, confidence."""
        # Setup mocks
        mock_classify.return_value = {'category': 'chemical', 'reason': ''}
        mock_rewrite.return_value = 'Heritage fungicide rate for bentgrass greens dollar spot'
        mock_feasibility.return_value = None  # No feasibility issues
        mock_search.return_value = {
            'general': mock_pinecone_results,
            'product': {'matches': []},
            'timing': {'matches': []}
        }
        mock_grounding.return_value = {
            'grounded': True,
            'confidence': 0.9,
            'issues': [],
            'unsupported_claims': [],
            'supported_ratio': 0.95
        }

        with patch('app.openai_client') as mock_openai_client:
            mock_openai_client.chat.completions.create.return_value = mock_openai_response

            response = app_client.post('/ask',
                data=json.dumps({
                    'question': 'What is the Heritage rate for bentgrass greens?'
                }),
                content_type='application/json')

        # Should always return 200 (errors are graceful)
        assert response.status_code == 200
        data = response.get_json()

        # Response must have required fields
        assert 'answer' in data
        assert 'sources' in data
        assert 'confidence' in data
        assert isinstance(data['answer'], str)
        assert len(data['answer']) > 0

    @patch('pipeline.classify_query')
    def test_off_topic_intercepted(self, mock_classify, app_client):
        """Off-topic questions should be intercepted by the classifier."""
        mock_classify.return_value = {'category': 'off_topic', 'reason': 'Not about turfgrass'}

        with patch('pipeline.get_response_for_category') as mock_response:
            mock_response.return_value = {
                'answer': 'I can only help with turfgrass questions.',
                'sources': [],
                'confidence': {'score': 0, 'label': 'Off Topic'}
            }
            with patch('pipeline.rewrite_query', return_value='test'):
                with patch('pipeline.check_feasibility', return_value=None):
                    response = app_client.post('/ask',
                        data=json.dumps({'question': 'What is the weather in Paris?'}),
                        content_type='application/json')

        assert response.status_code == 200
        data = response.get_json()
        assert 'turfgrass' in data['answer'].lower() or 'only help' in data['answer'].lower()


class TestAskResponseStructure:
    """Test that response objects have the expected shape."""

    def test_error_response_has_required_fields(self, app_client):
        """Even error responses should have answer, sources, confidence."""
        with patch('pipeline.RateLimiter') as mock_rl:
            mock_rl.check_rate_limit.return_value = {'allowed': False}
            response = app_client.post('/ask',
                data=json.dumps({'question': 'test'}),
                content_type='application/json')

        data = response.get_json()
        assert 'answer' in data
        assert 'sources' in data
        assert 'confidence' in data

    def test_confidence_has_score_and_label(self, app_client):
        """Confidence should always have score (number) and label (string)."""
        response = app_client.post('/ask',
            data=json.dumps({'question': ''}),
            content_type='application/json')

        data = response.get_json()
        assert 'score' in data['confidence']
        assert 'label' in data['confidence']
        assert isinstance(data['confidence']['score'], (int, float))
        assert isinstance(data['confidence']['label'], str)
