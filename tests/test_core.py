import pytest
from unittest.mock import patch, MagicMock
from autodial.config import SYSTEM_PROMPT, LLM_PROVIDER
from autodial.session import PhoneSession

def test_system_prompt_exists():
    """Ensure the baseline system prompt is properly configured."""
    assert SYSTEM_PROMPT is not None
    assert "CRITICAL INSTRUCTION" in SYSTEM_PROMPT

def test_phone_session_initialization():
    """Verify that PhoneSession properly parses context and builds history."""
    mock_ws = MagicMock()
    mock_stt = MagicMock()
    
    session = PhoneSession(
        websocket=mock_ws,
        stream_sid="TEST_STREAM",
        call_sid="TEST_CALL",
        stt_model=mock_stt,
        context="User is testing the app",
        goals="Make sure the test passes",
        system_instructions="Be a helpful bot",
        provider="twilio"
    )
    
    assert session.provider == "twilio"
    assert session.call_sid == "TEST_CALL"
    assert session.stream_sid == "TEST_STREAM"
    
    # Check that system instructions, context, and goals were injected into the first history prompt
    assert len(session.history) == 1
    sys_prompt = session.history[0]["content"]
    assert "GUARDRAILS: Be a helpful bot" in sys_prompt
    assert "CONTEXT: User is testing the app" in sys_prompt
    assert "GOALS: Make sure the test passes" in sys_prompt

@patch('autodial.cli.requests.post')
def test_nlp_parsing_mock(mock_post):
    """Ensure the NLP command parser can handle a mocked LLM response."""
    from autodial.cli import parse_nlp_command
    
    # Create a mock response
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    
    # Depending on LLM_PROVIDER, the parsing logic differs, so we mock the structure for 'ollama' (default)
    # We will temporarily patch LLM_PROVIDER just for this test, but since it's hard to patch a module-level 
    # variable that is already imported, we'll just mock the response structure expected by the active provider.
    if LLM_PROVIDER == "openai" or LLM_PROVIDER == "mistral":
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"target_number": "123", "context": "test", "goals": "test"}'}}]
        }
    elif LLM_PROVIDER == "gemini":
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": '{"target_number": "123", "context": "test", "goals": "test"}'}]}}]
        }
    else:
        # Default Ollama structure
        mock_response.json.return_value = {
            "message": {"content": '{"target_number": "123", "context": "test", "goals": "test"}'}
        }
        
    mock_post.return_value = mock_response
    
    result = parse_nlp_command("call bob at 123 for a test")
    assert result is not None
    assert result["target_number"] == "123"
    assert result["context"] == "test"
