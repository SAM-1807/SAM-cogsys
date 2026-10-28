CC = gcc
CFLAGS = -Wall -Wextra -Wpedantic -std=c99 -fPIC
LIB = libgame.so

all: $(LIB)

$(LIB): game.c game.h
	$(CC) -shared $(CFLAGS) -o $(LIB) game.c

test: $(LIB)
	python3 test_engine.py

clean:
	rm -f $(LIB)

.PHONY: all test clean
