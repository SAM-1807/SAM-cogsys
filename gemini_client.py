"""gemini_client.py - the real call_model(system_prompt, payload_json) -> str.

Setup (inside your venv):
    pip install -q -U google-genai python-dotenv
    nano .env        # GEMINI_API_KEY=your_key_here
                     # optional: GEMINI_MODELS=model-a,model-b,model-c  (try in this order)

.env is in .gitignore. Never paste the key into code, chat or a commit.

Reliability: models are tried in order. A fast error (rate limit, overload,
unknown model) moves straight on to the next model. Everything shares one
time budget, so the player never waits longer than TIMEOUT_SECONDS. If every
model fails, the caller (cogsys_logic.get_reply) uses the local fallback.
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:          # python-dotenv is optional if the variable is already set
    pass

# CHECK: pick the order after running compare_models.py on YOUR key.
DEFAULT_MODELS = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-2.5-flash"]
TIMEOUT_SECONDS = 8          # total budget for one reply, across all models
PER_MODEL_SECONDS = 5        # cap for a single model attempt

_pool = ThreadPoolExecutor(max_workers=4)


def _model_names(models):
    if models:
        return list(models)
    from_env = os.environ.get("GEMINI_MODELS", "")
    names = [name.strip() for name in from_env.split(",") if name.strip()]
    return names or list(DEFAULT_MODELS)


def _generate(client, types, model_name, system_prompt, payload_json):
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


def make_call_model(models=None, timeout_s=TIMEOUT_SECONDS, per_model_s=PER_MODEL_SECONDS):
    """Build a call_model function for cogsys_logic.get_reply.

    The SDK is imported here (not at module level) so the rest of the project
    and its tests run without the package or a network connection.
    """
    from google import genai
    from google.genai import types

    client = genai.Client()    # reads GEMINI_API_KEY from the environment
    names = _model_names(models)

    def call_model(system_prompt, payload_json):
        deadline = time.monotonic() + timeout_s
        last_error = TimeoutError("Gemini: no model answered in time")
        for model_name in names:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            future = _pool.submit(_generate, client, types, model_name,
                                  system_prompt, payload_json)
            try:
                return future.result(timeout=min(remaining, per_model_s))
            except FutureTimeout:
                last_error = TimeoutError(f"{model_name} did not answer in time")
            except Exception as err:   # noqa: BLE001 - rate limit, overload, bad model id...
                last_error = err
        raise last_error

    return call_model
