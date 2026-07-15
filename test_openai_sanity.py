"""Make one real OpenAI Responses API call to verify local configuration."""

import os
import sys

from dotenv import load_dotenv
from openai import OpenAI


def main() -> None:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not set. Copy .env.example to .env and add it.")
        sys.exit(1)

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model="gpt-5.6-terra",
        input="Say hello in one short sentence.",
    )
    print(response.output_text)


if __name__ == "__main__":
    main()
