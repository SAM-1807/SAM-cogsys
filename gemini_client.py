"""gemini_client.py - the real call_model(system_prompt, payload_json) -> str.

Setup (inside your venv):
    pip install -q -U google-genai python-dotenv
    nano .env        # one line:  GEMINI_API_KEY=your_key_here
                     # optional:  GEMINI_MODEL=<exact model id from AI Studio>

.env is in .gitignore. Never paste the key into code, chat or a commit.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:          # python-dotenv is optional if the variable is already set
    pass

# CHECK: confirm this id in Google AI Studio (model list) before the demo.
DEFAULT_MODEL = "gemini-3.5-flash-lite"
TIMEOUT_SECONDS = 3

_pool = ThreadPoolExecutor(max_workers=2)


def make_call_model(model=None, timeout_s=TIMEOUT_SECONDS):
    """Build a call_model function for cogsys_logic.get_reply.

    The SDK is imported here (not at module level) so the rest of the project
    and its tests run without the package or a network connection.
    The timeout is enforced in Python: if Gemini is slow, get_reply falls back.
    """
    from google import genai
    from google.genai import types

    client = genai.Client()    # reads GEMINI_API_KEY from the environment
    model_name = model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL

    def call_model(system_prompt, payload_json):
        def _request():
            response = client.models.generate_content(
                    model=model_name,
                    contents=payload_json,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json",
                        temperature=0.4,
                        ),
                    )
            return response.text

        future = _pool.submit(_request)
        try:
            return future.result(timeout=timeout_s)
        except FutureTimeout as err:
            raise TimeoutError(f"Gemini did not answer within {timeout_s}s") from err

    return call_model
