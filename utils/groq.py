def send_message_to_groq(system_prompt: str, user_message: str) -> str:
    from services.groq_client import get_groq_client, normalize_groq_model

    client = get_groq_client()
    response = client.chat.completions.create(
        model=normalize_groq_model("groq/openai/gpt-oss-20b"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],  # type: ignore[arg-type]
        temperature=1,
        max_completion_tokens=8192,
    )

    content = response.choices[0].message.content if response.choices else None
    return (content or "").strip()
