from services import ai_prompt_builder


def test_default_system_prompt_mentions_agent_name_and_fallback():
    prompt = ai_prompt_builder.default_system_prompt("Agent Smith")

    assert "Agent Smith" in prompt, (
        "Expected agent name to appear in system prompt; "
        f"prompt={prompt!r}"
    )
    assert "Fallback Response" in prompt, (
        "Expected system prompt to include fallback response section; "
        f"prompt={prompt!r}"
    )


def test_generate_system_prompt_from_text_truncates_to_6000_chars():
    training_text = "A" * 7000

    prompt = ai_prompt_builder.generate_system_prompt_from_text(training_text, "Helper")

    assert "A" * 6000 in prompt, (
        "Expected prompt to include a 6000-char summary of training text"
    )
    assert "A" * 6001 not in prompt, (
        "Expected training text summary to be truncated at 6000 characters"
    )


def test_send_message_to_groq_uses_litellm_completion(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured["kwargs"] = kwargs

        class Message:
            content = "Reply"

        class Choice:
            message = Message()

        class Response:
            choices = [Choice()]

        return Response()

    monkeypatch.setattr("litellm.completion", fake_completion)

    result = ai_prompt_builder.send_message_to_groq("sys", "hello")

    assert result == "Reply", (
        "Expected send_message_to_groq to return the message content; "
        f"got {result!r}"
    )
    assert captured["kwargs"]["model"] == "groq/llama-3.1-8b-instant", (
        "Expected groq model to match default"
    )
    assert captured["kwargs"]["messages"][0]["role"] == "system", (
        "Expected system message to be first in payload"
    )
