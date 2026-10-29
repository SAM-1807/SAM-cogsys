"""test_engine.py - multi-turn tests for the C engine (libgame.so) via bridge.py.

Build, then run from this folder:
    gcc -shared -fPIC -Wall -Wextra -o libgame.so game.c
    python3 test_engine.py

Before running, write down which tests you expect to FAIL (if any).
Python owns the struct, so tests set secret_number directly after new_game()
to make the scenarios deterministic.
"""
import ctypes
import sys

from bridge import lib, GameTelemetry, new_game

FIELDS = [name for name, _ in GameTelemetry._fields_]
EXPECTED_FIELDS = [
        "range_max", "trials_remaining", "secret_number", "last_guess",
        "space_velocity", "logical_entropy", "distance_vector", "game_status",
        "current_min", "current_max",
        ]
LEVELS = {1: (100, 7), 2: (500, 9), 3: (1000, 10)}   # difficulty: (range, trials)
results = []


def snap(t):
    """Copy every field into a plain dict (later turns can't change it)."""
    return {f: getattr(t, f) for f in FIELDS}


def check(name, cond, info=""):
    results.append(bool(cond))
    if cond:
        print("PASS  " + name)
    else:
        print("FAIL  " + name + "   -> " + str(info))


def turn(t, guess):
    """Play one guess and return a snapshot of the struct afterwards."""
    lib.process_turn(guess, ctypes.byref(t))
    return snap(t)


def midpoint(t):
    return (t.current_min + t.current_max) // 2


def show(history):
    print(" | ".join(f"{f[:9]:>9}" for f in FIELDS))
    for row in history:
        print(" | ".join(f"{row[f]:>9}" for f in FIELDS))


# ------------------------------------------------------------ Step 0
print("--- Step 0: fresh games for difficulty 1, 2, 3 and an invalid 4 ---")
for arg in (1, 2, 3, 4):
    print(arg, snap(new_game(arg)))
print()

# ------------------------------------------------------------ T1: layout
check("T1 struct size is 40 bytes", ctypes.sizeof(GameTelemetry) == 40,
      ctypes.sizeof(GameTelemetry))
check("T1 field names and order match game.h", FIELDS == EXPECTED_FIELDS, FIELDS)

# ------------------------------------------------------------ T2: fresh state
for diff, (rng, trials) in LEVELS.items():
    s = snap(new_game(diff))
    check(f"T2 difficulty {diff}: range and trials",
          s["range_max"] == rng and s["trials_remaining"] == trials, s)
    check(f"T2 difficulty {diff}: starts Playing with clean telemetry",
          s["game_status"] == 0 and s["logical_entropy"] == 0
          and s["space_velocity"] == 0 and s["distance_vector"] == 0
          and s["last_guess"] == 0, s)
    check(f"T2 difficulty {diff}: bounds are 1..range_max",
          s["current_min"] == 1 and s["current_max"] == rng, s)
    check(f"T2 difficulty {diff}: secret inside 1..range_max",
          1 <= s["secret_number"] <= rng, s)

# ------------------------------------------------------------ T3: first-guess win
t = new_game(1)
secret = t.secret_number
s = turn(t, secret)
check("T3 first-guess win: status Won", s["game_status"] == 1, s)
check("T3 first-guess win: distance 0, no entropy",
      s["distance_vector"] == 0 and s["logical_entropy"] == 0, s)
check("T3 first-guess win: velocity is 100", s["space_velocity"] == 100, s)
check("T3 first-guess win: bounds collapsed onto the secret",
      s["current_min"] == secret and s["current_max"] == secret, s)
check("T3 first-guess win: one trial used", s["trials_remaining"] == 6, s)

# ------------------------------------------------------------ T4: wrong in-bounds guess
t = new_game(1)
secret = t.secret_number
wrong = secret + 1 if secret + 1 <= t.current_max else secret - 1
s = turn(t, wrong)
check("T4 distance_vector == |secret - guess|",
      s["distance_vector"] == abs(secret - wrong), s)
check("T4 last_guess recorded", s["last_guess"] == wrong, s)
check("T4 still Playing, no entropy",
      s["game_status"] == 0 and s["logical_entropy"] == 0, s)
check("T4 velocity between 1 and 99 for a non-winning guess",
      1 <= s["space_velocity"] <= 99, s)

# ------------------------------------------------------------ T5: binary search invariants
for diff in (1, 2, 3):
    t = new_game(diff)
    prev = snap(t)
    history = []
    problems = []
    for _ in range(100):                       # hard stop: a bug can't loop forever
        cur = turn(t, midpoint(t))
        history.append(cur)
        if not 0 <= cur["space_velocity"] <= 100:
            problems.append(("velocity outside 0-100", cur))
        if cur["trials_remaining"] != prev["trials_remaining"] - 1:
            problems.append(("trials did not drop by exactly 1", cur))
        if cur["logical_entropy"] != 0:
            problems.append(("perfect play was flagged", cur))
        if not cur["current_min"] <= cur["secret_number"] <= cur["current_max"]:
            problems.append(("secret fell outside the bounds", cur))
        prev = cur
        if cur["game_status"] != 0:
            break
    check(f"T5 difficulty {diff}: per-turn invariants hold", not problems, problems[:2])
    check(f"T5 difficulty {diff}: perfect play ends in a win",
          history[-1]["game_status"] == 1, history[-1])
    check(f"T5 difficulty {diff}: winning turn velocity is 100",
          history[-1]["space_velocity"] == 100, history[-1])
    if diff == 1:
        show(history)

# ------------------------------------------------------------ T6: bounds, penalty, off-by-one
t = new_game(1)
t.secret_number = 50
s1 = turn(t, 100)                              # too high, legal: max becomes 99
check("T6 legal wrong guess tightens max to 99",
      s1["current_max"] == 99 and s1["logical_entropy"] == 0, s1)
before = snap(t)
flagged = turn(t, 100)                         # above the new max: illegal
check("T6 guess above new max is flagged", flagged["logical_entropy"] == 1, flagged)
check("T6 flagged guess costs exactly one trial",
      flagged["trials_remaining"] == before["trials_remaining"] - 1,
      (before["trials_remaining"], flagged["trials_remaining"]))
check("T6 flagged guess does not move the bounds",
      flagged["current_min"] == before["current_min"]
      and flagged["current_max"] == before["current_max"], (before, flagged))
check("T6 flagged guess still updates distance and last_guess",
      flagged["distance_vector"] == 50 and flagged["last_guess"] == 100, flagged)
check("T6 flagged guess reports velocity 0 and game continues",
      flagged["space_velocity"] == 0 and flagged["game_status"] == 0, flagged)
nxt = turn(t, midpoint(t))
check("T6 flag resets on the next legal guess (per-turn flag)",
      nxt["logical_entropy"] == 0, nxt)

t = new_game(1)
t.secret_number = 50
turn(t, 100)                                   # max becomes 99
edge = turn(t, 99)                             # exactly the new max: legal
check("T6 guess ON the new max is NOT flagged (inclusive bounds)",
      edge["logical_entropy"] == 0 and edge["current_max"] == 98, edge)

t = new_game(1)
t.secret_number = 50
turn(t, 1)                                     # too low, legal: min becomes 2
low = turn(t, 1)                               # below the new min: illegal
check("T6 guess below new min is flagged", low["logical_entropy"] == 1, low)

# ------------------------------------------------------------ T7: losing, and play after game over
t = new_game(1)
t.secret_number = 50
for _ in range(7):                             # guess 1 every time: 1 legal, 6 flagged
    s = turn(t, 1)
check("T7 using all trials: status Lost", s["game_status"] == 2, s)
check("T7 using all trials: trials_remaining is exactly 0",
      s["trials_remaining"] == 0, s)
frozen = snap(t)
after = turn(t, 50)                            # a would-be winning guess after the end
check("T7 guesses after a loss are ignored", after == frozen, (frozen, after))

t = new_game(1)
turn(t, t.secret_number)                       # win immediately
frozen = snap(t)
after = turn(t, 1)
check("T7 guesses after a win are ignored", after == frozen, (frozen, after))

# ------------------------------------------------------------ T8: reusing one struct
t = new_game(1)
turn(t, t.secret_number)                       # finish a game
lib.init_game(ctypes.byref(t), 2)              # re-init the SAME object as a new level
s = snap(t)
check("T8 re-init resets every per-game field",
      s["game_status"] == 0 and s["logical_entropy"] == 0
      and s["space_velocity"] == 0 and s["distance_vector"] == 0
      and s["last_guess"] == 0, s)
check("T8 re-init applies the new difficulty",
      s["range_max"] == 500 and s["trials_remaining"] == 9
      and s["current_min"] == 1 and s["current_max"] == 500, s)

# ------------------------------------------------------------ T9: hostile input
for bad in (-5, 0, 10 ** 6):
    t = new_game(1)
    s = turn(t, bad)
    check(f"T9 guess {bad}: flagged, still Playing, one trial used",
          s["logical_entropy"] == 1 and s["game_status"] == 0
          and s["trials_remaining"] == 6, s)
    check(f"T9 guess {bad}: distance is |secret - guess|",
          s["distance_vector"] == abs(s["secret_number"] - bad), s)

# ------------------------------------------------------------ T10: flagged guess on the last trial
t = new_game(1)
t.secret_number = 50
for _ in range(6):                             # 1 legal + 5 flagged, 1 trial left
    s = turn(t, 1)
check("T10 setup: one trial left and still Playing",
      s["trials_remaining"] == 1 and s["game_status"] == 0, s)
s = turn(t, 1)                                 # flagged guess on the last trial
check("T10 flagged guess on the last trial ends the game as Lost",
      s["game_status"] == 2 and s["logical_entropy"] == 1
      and s["trials_remaining"] == 0, s)

# ------------------------------------------------------------ T11: perfect play always wins
for diff, (rng, _) in LEVELS.items():
    losses = []
    for secret in range(1, rng + 1):
        t = new_game(diff)
        t.secret_number = secret
        for _ in range(50):
            if t.game_status != 0:
                break
            turn(t, midpoint(t))
        if t.game_status != 1:
            losses.append(secret)
    check(f"T11 difficulty {diff}: perfect play wins for every secret 1..{rng}",
          not losses, f"{len(losses)} losses, e.g. {losses[:5]}")

# ------------------------------------------------------------ T12: invalid difficulty
for bad in (0, 4, -1, 42):
    t = new_game(bad)
    before = snap(t)
    check(f"T12 difficulty {bad}: error state (status -1, 0 trials)",
          before["game_status"] == -1 and before["trials_remaining"] == 0, before)
    check(f"T12 difficulty {bad}: every other field is 0",
          all(before[f] == 0 for f in FIELDS if f != "game_status"), before)
    check(f"T12 difficulty {bad}: turns on an error game are ignored",
          turn(t, 5) == before)

# ------------------------------------------------------------ T13: seeding
secrets = {new_game(3).secret_number for _ in range(30)}
check("T13 secrets differ between games started back to back",
      len(secrets) > 1, secrets)

# T14: a legal guess never reports velocity 0
t = new_game(3)
t.secret_number = 500
s = turn(t, 1000)              # legal edge guess: removes only 1 of 1000 numbers
check("T14 legal edge guess: velocity >= 1, no entropy flag",
      s["space_velocity"] >= 1 and s["logical_entropy"] == 0, s)
check("T14 illegal guess still reports velocity 0",
      turn(new_game(3), 2000)["space_velocity"] == 0)

# T15: extreme guesses do not overflow distance_vector
t = new_game(1)
t.secret_number = 50
s = turn(t, 2147483647)        # INT_MAX: distance fits in int, exact value
check("T15 INT_MAX guess: distance is |secret - guess|, no wrap",
      s["distance_vector"] == 2147483647 - 50, s)
s = turn(t, -2147483648)       # INT_MIN: true distance exceeds INT_MAX, clamps
check("T15 INT_MIN guess: distance clamps to INT_MAX",
      s["distance_vector"] == 2147483647, s)

# ------------------------------------------------------------ summary
print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
