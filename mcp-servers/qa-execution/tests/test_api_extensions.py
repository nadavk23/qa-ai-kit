"""Unit tests for Phase 1 API extension features (GraphQL, WebSocket, gRPC, CLI)."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from qa_execution.yaml_runner import run_steps, _do_graphql, _extract_json_path, BrowserSession
from qa_execution.runner_base import TestFailure


class FakeSession:
    """Minimal session for testing YAML runners."""
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None


# ============================================================================
# GraphQL Tests
# ============================================================================


@pytest.mark.asyncio
async def test_graphql_query_success():
    """Test successful GraphQL query with mocked httpx response."""
    session = FakeSession()

    step = {
        "url": "https://api.example.com/graphql",
        "query": "query GetUser($id: ID!) { user(id: $id) { id name } }",
        "variables": {"id": "123"},
        "operation_name": "GetUser",
        "expected_status": 200,
    }

    with patch("qa_execution.yaml_runner.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"user": {"id": "123", "name": "Alice"}}
        }
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        result = await _do_graphql(session, step)
        assert "200" in result
        assert "GetUser" in result
        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_graphql_error_response():
    """Test GraphQL query with errors in response."""
    session = FakeSession()

    step = {
        "url": "https://api.example.com/graphql",
        "query": "query Invalid { user { id } }",
        "expected_status": 200,
    }

    with patch("qa_execution.yaml_runner.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "Field 'user' is not defined"}]
        }
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        with pytest.raises(TestFailure, match="GraphQL errors"):
            await _do_graphql(session, step)


@pytest.mark.asyncio
async def test_graphql_status_mismatch():
    """Test GraphQL query with unexpected status code."""
    session = FakeSession()

    step = {
        "url": "https://api.example.com/graphql",
        "query": "query GetUser { user { id } }",
        "expected_status": 200,
    }

    with patch("qa_execution.yaml_runner.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"errors": [{"message": "Server error"}]}
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        with pytest.raises(TestFailure, match="expected status 200"):
            await _do_graphql(session, step)


@pytest.mark.asyncio
async def test_graphql_assert_path():
    """Test GraphQL query with JSON path assertion."""
    session = FakeSession()

    step = {
        "url": "https://api.example.com/graphql",
        "query": "query GetUser { user { name } }",
        "assert_path": "data.user.name",
        "assert_value": "Alice",
    }

    with patch("qa_execution.yaml_runner.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"user": {"name": "Alice"}}
        }
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        result = await _do_graphql(session, step)
        assert "200" in result


@pytest.mark.asyncio
async def test_graphql_assert_path_mismatch():
    """Test GraphQL query with failed JSON path assertion."""
    session = FakeSession()

    step = {
        "url": "https://api.example.com/graphql",
        "query": "query GetUser { user { name } }",
        "assert_path": "data.user.name",
        "assert_value": "Alice",
    }

    with patch("qa_execution.yaml_runner.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"user": {"name": "Bob"}}
        }
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        with pytest.raises(TestFailure, match="expected 'Alice'"):
            await _do_graphql(session, step)


# ============================================================================
# JSON Path Extraction Tests
# ============================================================================


def test_extract_json_path_simple():
    """Test JSON path extraction with simple keys."""
    obj = {"user": {"name": "Alice", "id": 123}}
    assert _extract_json_path(obj, "user.name") == "Alice"
    assert _extract_json_path(obj, "user.id") == 123


def test_extract_json_path_nested():
    """Test JSON path extraction with nested structures."""
    obj = {"data": {"user": {"profile": {"email": "alice@test.com"}}}}
    assert _extract_json_path(obj, "data.user.profile.email") == "alice@test.com"


def test_extract_json_path_missing():
    """Test JSON path extraction with missing keys."""
    obj = {"user": {"name": "Alice"}}
    assert _extract_json_path(obj, "user.missing") is None
    assert _extract_json_path(obj, "missing.key") is None


def test_extract_json_path_array():
    """Test JSON path extraction with arrays (not supported in simple implementation)."""
    obj = {"items": [{"id": 1}, {"id": 2}]}
    # Simple implementation doesn't support array indexing
    assert _extract_json_path(obj, "items") == [{"id": 1}, {"id": 2}]


# ============================================================================
# GraphQL in YAML Test Runner
# ============================================================================


@pytest.mark.asyncio
async def test_graphql_in_web_batch():
    """Test GraphQL action in web_batch (via run_steps)."""
    session = FakeSession()

    steps = [
        {
            "action": "graphql",
            "url": "https://api.example.com/graphql",
            "query": "query { user { id } }",
            "expected_status": 200,
        }
    ]

    with patch("qa_execution.yaml_runner.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"user": {"id": "123"}}}
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        lines, passed, failed, skipped = await run_steps(session, steps)
        assert passed == 1
        assert failed == 0
        assert "[1] PASS graphql" in "\n".join(lines)


@pytest.mark.asyncio
async def test_graphql_failure_stops_batch():
    """Test that GraphQL failure stops batch when on_failure='stop'."""
    session = FakeSession()

    steps = [
        {
            "action": "graphql",
            "url": "https://api.example.com/graphql",
            "query": "query { invalid }",
            "expected_status": 200,
        },
        {
            "action": "graphql",
            "url": "https://api.example.com/graphql",
            "query": "query { user { id } }",
            "expected_status": 200,
        },
    ]

    with patch("qa_execution.yaml_runner.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errors": [{"message": "Invalid"}]}
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        lines, passed, failed, skipped = await run_steps(session, steps, on_failure="stop")
        assert passed == 0
        assert failed == 1
        assert skipped == 1  # Second step skipped
        assert "Stopped on first failure" in "\n".join(lines)


# ============================================================================
# WebSocket Tests
# ============================================================================


@pytest.mark.asyncio
async def test_ws_connect():
    """Test WebSocket connection."""
    from qa_execution.yaml_runner import _do_ws_connect

    session = FakeSession()
    step = {
        "url": "ws://localhost:8080",
    }

    async def mock_ws_connect(*args, **kwargs):
        return AsyncMock()

    with patch("websockets.connect", side_effect=mock_ws_connect):
        result = await _do_ws_connect(session, step)
        assert "connected" in result
        assert hasattr(session, "ws_connections")
        assert "default" in session.ws_connections


@pytest.mark.asyncio
async def test_ws_send():
    """Test WebSocket send."""
    from qa_execution.yaml_runner import _do_ws_send
    from qa_execution.ws_runner import WebSocketClient

    session = FakeSession()
    session.ws_connections = {}

    # Mock WebSocket client
    mock_ws = AsyncMock(spec=WebSocketClient)
    session.ws_connections["default"] = mock_ws

    step = {
        "message": '{"type": "ping"}',
        "connection_id": "default",
    }

    result = await _do_ws_send(session, step)
    assert "sent" in result
    mock_ws.send.assert_called_once_with('{"type": "ping"}')


@pytest.mark.asyncio
async def test_ws_send_and_wait():
    """Test WebSocket send with wait_response."""
    from qa_execution.yaml_runner import _do_ws_send
    from qa_execution.ws_runner import WebSocketClient

    session = FakeSession()
    session.ws_connections = {}

    mock_ws = AsyncMock(spec=WebSocketClient)
    mock_ws.recv = AsyncMock(return_value='{"type": "pong"}')
    session.ws_connections["default"] = mock_ws

    step = {
        "message": '{"type": "ping"}',
        "connection_id": "default",
        "wait_response": True,
        "timeout_ms": 5000,
    }

    result = await _do_ws_send(session, step)
    assert "received" in result
    assert hasattr(session, "ws_last_response")
    assert session.ws_last_response == '{"type": "pong"}'


@pytest.mark.asyncio
async def test_assert_ws_message_contains():
    """Test WebSocket message assertion with text match."""
    from qa_execution.yaml_runner import _do_assert_ws_message

    session = FakeSession()
    session.ws_last_response = '{"type": "message", "data": "hello"}'

    step = {
        "contains": '"type": "message"',
    }

    result = await _do_assert_ws_message(session, step)
    assert "passed" in result


@pytest.mark.asyncio
async def test_assert_ws_message_json_path():
    """Test WebSocket message assertion with JSON path."""
    from qa_execution.yaml_runner import _do_assert_ws_message

    session = FakeSession()
    session.ws_last_response = '{"type": "message", "data": {"id": 123}}'

    step = {
        "assert_path": "data.id",
        "assert_value": 123,
    }

    result = await _do_assert_ws_message(session, step)
    assert "passed" in result


@pytest.mark.asyncio
async def test_assert_ws_message_json_path_mismatch():
    """Test WebSocket message assertion with JSON path mismatch."""
    from qa_execution.yaml_runner import _do_assert_ws_message

    session = FakeSession()
    session.ws_last_response = '{"type": "message", "data": {"id": 999}}'

    step = {
        "assert_path": "data.id",
        "assert_value": 123,
    }

    with pytest.raises(TestFailure, match="expected 123"):
        await _do_assert_ws_message(session, step)


@pytest.mark.asyncio
async def test_ws_close():
    """Test WebSocket connection close."""
    from qa_execution.yaml_runner import _do_ws_close
    from qa_execution.ws_runner import WebSocketClient

    session = FakeSession()
    session.ws_connections = {}

    mock_ws = AsyncMock(spec=WebSocketClient)
    session.ws_connections["default"] = mock_ws

    step = {"connection_id": "default"}

    result = await _do_ws_close(session, step)
    assert "closed" in result
    mock_ws.close.assert_called_once()
    assert "default" not in session.ws_connections


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
