from groq import Groq
import os

client = Groq(api_key=os.getenv("GROQ_API_KEY"))  

def send_message_to_groq(system_prompt: str, user_message: str) -> str:
    completion = client.chat.completions.create(
        model="openai/gpt-oss-20b",  # Use  supported model
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
        top_p=1,
        stream=False
    )

    return completion.choices[0].message.content.strip()
