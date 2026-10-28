#ifndef GAME_H
#define GAME_H

#include <stdlib.h>

/**
 * struct GameTelemetry - Shared memory blueprint with Python
 * @range_max: The maximum number for the current difficulty
 * @trials_remaining: The number of trials the player has left
 * @secret_number: The number the player is trying to guess
 * @last_guess: The player's most recent guess
 * @space_velocity: Percentage of search space eliminated (0-100)
 * @logical_entropy: 1 if the guess broke boundaries, 0 otherwise
 * @distance_vector: Absolute difference between guess and secret
 * @game_status: 0 = Playing, 1 = Won, 2 = Lost
 * @current_min: The lowest possible valid number remaining
 * @current_max: The highest possible valid number remaining
 */
typedef struct GameTelemetry
{
	int range_max;
	int trials_remaining;
	int secret_number;
	int last_guess;
	int space_velocity;
	int logical_entropy;
	int distance_vector;
	int game_status;
	int current_min;
	int current_max;
} GameTelemetry;

void init_game(GameTelemetry *metrics, int difficulty);
void process_turn(int guess, GameTelemetry *metrics);

#endif
