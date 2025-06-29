# Tests for Slack MCP Server

This directory contains unit tests for the Slack MCP Server.

## Setup

Install test dependencies:
```bash
uv pip install -e ".[test]"
```

## Running Tests

Run all tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov
```

Run specific test file:
```bash
pytest tests/test_slack_oauth_provider.py
```

Run specific test:
```bash
pytest tests/test_slack_oauth_provider.py::TestSlackOAuthProvider::test_init
```

## Test Structure

- `conftest.py` - Shared fixtures and test configuration
- `test_slack_oauth_provider.py` - Tests for OAuth provider
- `test_storage.py` - Tests for storage implementations (local file and DynamoDB)
- `test_mcp_tools.py` - Tests for MCP tools (list_channels, post_message, get_auth_status)

## Markers

- `@pytest.mark.unit` - Unit tests (fast, no external dependencies)
- `@pytest.mark.integration` - Integration tests (may require external services)
- `@pytest.mark.slow` - Slow tests

Run only unit tests:
```bash
pytest -m unit
```

## Coverage

Coverage reports are generated in:
- Terminal output with missing lines
- HTML report in `htmlcov/` directory

View HTML coverage report:
```bash
open htmlcov/index.html
```

## Mocking

Tests use various mocking strategies:
- `mock_env` - Mock environment variables
- `mock_storage` - Mock storage interface
- `mock_httpx_client` - Mock HTTP client for API calls
- `@mock_dynamodb` - Mock DynamoDB using moto library