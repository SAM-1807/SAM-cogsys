"""bridge.py - ctypes bridge between Python and the C engine (libgame.so).

Build the library first (from this folder):
    gcc -shared -fPIC -Wall -Wextra -o libgame.so game.c
"""
import ctypes
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB_PATH = os.path.join(_HERE, "libgame.so")

try:
    lib = ctypes.CDLL(_LIB_PATH)
except OSError as err:
    raise OSError(
            f"Could not load {_LIB_PATH}. Build it first with:\n"
            "  gcc -shared -fPIC -Wall -Wextra -o libgame.so game.c"
            ) from err

# game_status values reported by the C engine
STATUS_ERROR = -1   # invalid difficulty
STATUS_PLAYING = 0
STATUS_WON = 1
STATUS_LOST = 2


class GameTelemetry(ctypes.Structure):
    """Must match struct GameTelemetry in game.h: same fields, same order."""
    _fields_ = [
            ("range_max", ctypes.c_int),
            ("trials_remaining", ctypes.c_int),
            ("secret_number", ctypes.c_int),
            ("last_guess", ctypes.c_int),
            ("space_velocity", ctypes.c_int),
            ("logical_entropy", ctypes.c_int),
            ("distance_vector", ctypes.c_int),
            ("game_status", ctypes.c_int),      # -1 = Error, 0 = Playing, 1 = Won, 2 = Lost
            ("current_min", ctypes.c_int),
            ("current_max", ctypes.c_int),
            ]


lib.init_game.argtypes = [ctypes.POINTER(GameTelemetry), ctypes.c_int]
lib.init_game.restype = None

lib.process_turn.argtypes = [ctypes.c_int, ctypes.POINTER(GameTelemetry)]
lib.process_turn.restype = None


def new_game(difficulty=1):
    """Create a fresh telemetry struct for difficulty 1 (Easy), 2 or 3 (Hard).

    Any other difficulty returns a struct in the error state
    (game_status == -1, trials_remaining == 0). Callers must check for it.
    """
    telemetry = GameTelemetry()
    lib.init_game(ctypes.byref(telemetry), difficulty)
    return telemetry


if __name__ == "__main__":
    # Quick smoke test: python3 bridge.py
    print("struct size:", ctypes.sizeof(GameTelemetry), "(expected 40)")
    game = new_game(1)
    print({name: getattr(game, name) for name, _ in GameTelemetry._fields_})
