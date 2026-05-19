def send_message_to_groq(system_prompt: str, user_message: str) -> str:
    from litellm import completion

    response = completion(
        model="groq/openai/gpt-oss-20b",
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        temperature=1,
        max_tokens=8192,
    )

    return response.choices[0].message.content.strip()
