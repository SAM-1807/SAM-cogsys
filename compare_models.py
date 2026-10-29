"""compare_models.py - measure each candidate model on YOUR key and connection.

Run (needs GEMINI_API_KEY and network):
    python3 compare_models.py
    python3 compare_models.py gemini-2.5-flash gemini-3.8-flash   # your own list

It sends the six scenarios from try_gemini.py to each model, ONE model at a
time, and counts: ok (valid reply), INVALID (answered but broke a rule),
API ERROR (rate limit, overload, bad model id, timeout). It prints average and
slowest time. Pick the model with 6/6 ok and the lowest slowest-time; put the
runner-up second in your order. Run it twice, a few minutes apart, at least
once at the time of day you will demo.
"""
import json
import sys
import time

import cogsys_logic as cl
from gemini_client import DEFAULT_MODELS, make_call_model
from try_gemini import SCENARIOS, SECRET

PAUSE_BETWEEN_CALLS = 1.0     # seconds; gentle on per-minute rate limits


def run_model(model_name):
    call = make_call_model(models=[model_name], timeout_s=15, per_model_s=15)
    outcomes, times = [], []
    for name, history in SCENARIOS.items():
        payload = cl.build_payload(history, 100, SECRET, "SAM")
        phase = cl.PHASES[history[-1]["game_status"]]
        start = time.monotonic()
        try:
            raw = call(cl.SYSTEM_PROMPT, json.dumps(payload))
            cl.validate_reply(raw, SECRET, phase)
            outcomes.append("ok")
        except cl.InvalidReply as err:
            outcomes.append(f"INVALID ({err})")
        except Exception as err:   # noqa: BLE001 - diagnostic script
            outcomes.append(f"API ERROR ({type(err).__name__})")
        times.append(time.monotonic() - start)
        time.sleep(PAUSE_BETWEEN_CALLS)
    return outcomes, times


def main():
    models = sys.argv[1:] or DEFAULT_MODELS
    table = []
    for model_name in models:
        print(f"--- {model_name}")
        outcomes, times = run_model(model_name)
        ok = sum(1 for o in outcomes if o == "ok")
        for scenario, outcome, secs in zip(SCENARIOS, outcomes, times):
            print(f"    {scenario:<40} {outcome:<40} {secs:4.1f}s")
        table.append((model_name, ok, sum(times) / len(times), max(times)))

    print("\nSummary (best first):")
    for model_name, ok, avg, worst in sorted(table, key=lambda r: (-r[1], r[3])):
        print(f"  {model_name:<28} ok {ok}/{len(SCENARIOS)}   avg {avg:4.1f}s   slowest {worst:4.1f}s")


if __name__ == "__main__":
    main()
