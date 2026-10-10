import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from openai import AsyncOpenAI

env_file = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_file, override=True)

base_url = os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
api_key = os.getenv("OPENAI_API_KEY")
default_model = "qwen/qwen3.8-27b" if (base_url and "groq" in base_url) else "gpt-4o-mini"
model_name = os.getenv("AGENT_MODEL", default_model)

SYSTEM_PROMPT = (
    "You are My Personal Agent, a friendly, helpful, and highly intelligent AI assistant. "
    "Help the user with coding, studies, projects, and daily tasks. "
    "Explain concepts clearly, concisely, and step by step."
)

class PersonalAgent:
    def __init__(self, api_key: str, base_url: str | None = None, model: str = model_name):
        # Normalize base_url if empty string
        endpoint = base_url.strip() if (base_url and base_url.strip()) else None
        self.client = AsyncOpenAI(api_key=api_key, base_url=endpoint)
        self.model = model
        self.history: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def reset(self):
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]

    async def run(self, user_prompt: str, stream: bool = True) -> str:
        self.history.append({"role": "user", "content": user_prompt})
        try:
            if stream:
                response_stream = await self.client.chat.completions.create(
                    model=self.model,
                    messages=self.history,
                    stream=True,
                )
                chunks = []
                async for chunk in response_stream:
                    delta = chunk.choices[0].delta.content or ""
                    print(delta, end="", flush=True)
                    chunks.append(delta)
                print()
                reply = "".join(chunks)
            else:
                completion = await self.client.chat.completions.create(
                    model=self.model,
                    messages=self.history,
                    stream=False,
                )
                reply = completion.choices[0].message.content or ""
                print(reply)

            self.history.append({"role": "assistant", "content": reply})
            return reply

        except Exception as e:
            err_msg = str(e)
            if "authentication" in err_msg.lower() or "api_key" in err_msg.lower() or "401" in err_msg:
                print(f"\n[Agent Error]: Invalid API key. Please check your OPENAI_API_KEY in .env.")
            else:
                print(f"\n[Agent Error]: {e}")
            return ""

if sys.platform == "win32":
    try:
        if sys.stdout.encoding != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr.encoding != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def print_banner():
    print("=" * 60)
    print("  [AGENT] MY PERSONAL AGENT")
    print(f"  Endpoint : {base_url or 'OpenAI Official'}")
    print(f"  Model    : {model_name}")
    print("=" * 60)

async def main():
    print_banner()

    if not api_key or not api_key.strip():
        print("\n(!) [Agent Notice]: OPENAI_API_KEY is not set.")
        print("-" * 60)
        print("To run this agent for FREE using Groq:")
        print("1. Go to: https://console.groq.com/keys")
        print("2. Sign in and create a free API key (starts with 'gsk_')")
        print("3. Open .env and paste it on line 4:")
        print("   OPENAI_API_KEY=gsk_your_api_key_here")
        print("-" * 60)
        return

    agent = PersonalAgent(api_key=api_key, base_url=base_url, model=model_name)

    # Check if a single prompt was provided via command line arguments
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(f"\n[You]: {query}")
        print("\n[Agent]: ", end="", flush=True)
        await agent.run(query, stream=True)
        return

    # Interactive chat loop
    print("\nChat mode started! Commands: 'exit' to quit, 'clear' to reset memory.")
    print("-" * 60)

    # Introductory self-introduction
    print("\n[Agent]: ", end="", flush=True)
    await agent.run("Hello! Introduce yourself briefly and tell me how you can assist me today.", stream=True)

    while True:
        try:
            user_input = input("\n[You]: ").strip()
            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                print("\nGoodbye! Have a productive day!")
                break

            if user_input.lower() in ("clear", "reset"):
                agent.reset()
                print("\nConversation memory cleared.")
                continue

            print("\n[Agent]: ", end="", flush=True)
            await agent.run(user_input, stream=True)

        except (KeyboardInterrupt, EOFError):
            print("\n\nSession ended.")
            break

if __name__ == "__main__":
    asyncio.run(main())
