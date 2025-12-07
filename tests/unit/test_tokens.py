from __future__ import annotations
from unittest.mock import MagicMock, patch
from meridian.utils.tokens import OpenAITokenCounter, AnthropicTokenCounter


def test_openai_token_counter_basic() -> None:
    # We expect tiktoken to be installed
    counter = OpenAITokenCounter()
    text = "Hello world"
    count = counter.count(text)
    # tiktoken: "Hello" (1) + " world" (1) = 2 usually
    assert count > 0


def test_anthropic_token_counter_mocked() -> None:
    # Patch the global anthropic class since it is imported inside the method
    # but refers to the installed package.
    with patch("anthropic.Anthropic") as MockAnthropic:
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.input_tokens = 5

        mock_client.beta.messages.count_tokens.return_value = mock_response

        # 2. Test Count with Caching
        cnt = AnthropicTokenCounter()

        # First call hits API
        assert cnt.count("Hello") == 5
        mock_client.beta.messages.count_tokens.assert_called_once()

        # Second call should hit cache (no new API call)
        assert cnt.count("Hello") == 5
        assert mock_client.beta.messages.count_tokens.call_count == 1

        # New content hits API
        assert cnt.count("New") == 5
        assert mock_client.beta.messages.count_tokens.call_count == 2
