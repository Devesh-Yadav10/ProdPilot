"""Make one real Groq Chat Completions call to verify local configuration."""

import os
import sys

from dotenv import load_dotenv
from openai import OpenAI


def main() -> None:
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("GROQ_API_KEY is not set. Copy .env.example to .env and add it.")
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "openai/gpt-oss-20b"),
        messages=[{"role": "user", "content": "Say hello in one short sentence."}],
    )
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
