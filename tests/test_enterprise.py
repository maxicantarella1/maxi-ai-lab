from unittest.mock import patch
from fastapi import HTTPException
from pydantic import ValidationError
import pytest
from backend.enterprise import AgentRequest, enforce_limit


def test_prompt_validation():
    with pytest.raises(ValidationError):
        AgentRequest(prompt='short')


def test_rate_limit():
    with patch('backend.enterprise.MAX_PER_HOUR', 1):
        enforce_limit('test-client-unique')
        with pytest.raises(HTTPException) as exc:
            enforce_limit('test-client-unique')
        assert exc.value.status_code == 429
