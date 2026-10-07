/**
 * Battleship authoritative server state.
 *
 * @authors Adam Foflonker, Muddathir Firfirey
 * @date 06 Oct 2026
 * @version 1.0
 */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>


#define BS_MAX_REQUEST        64u                  // bytes, excluding the line terminator
#define BS_MAX_REPLY          213u
#define BS_REPLY_BUF          (BS_MAX_REPLY + 3u)  // CRLF + NUL
#define BS_PARTIAL_TIMEOUT_MS 500u
#define BS_NUM_CELLS          100

/**
 * Enum of all possible game states.
 */
typedef enum bs_state_t
{
    // The server is idle - game has not yet started.
    BS_IDLE,

    // The game is in the planning phase.
    BS_IN_PROGRESS_PLANNING,

    // The game is in the firing phase.
    BS_IN_PROGRESS_FIRING,

    // The game has ended.
    BS_GAME_OVER
} bs_state_t;

/**
 * The state of a player's board.
 */
typedef struct bs_fleet_t
{
    // Ship letter (C, B, R, S, D) or '.' for empty water.
    char cell[BS_NUM_CELLS];

    // Tracks which cells the opponent has fired on.
    uint8_t shot[BS_NUM_CELLS];

    // Tracks which cells contain ships.
    uint8_t placed_mask;

    // The number of ship placements.
    uint8_t placed_count;

    // Unhit cells left per ship.
    uint8_t remaining[5];
} bs_fleet_t;

/**
 * The authoritative server state.
 */
typedef struct bs_server_t
{
    // The state of each player's board.
    bs_fleet_t fleet[2];

    // The current state of the server.
    bs_state_t state;

    // Which player's turn is it: P1 = 0, P2 = 1.
    uint8_t turn;

    // Tracks if a client has sent a CONNECT request.
    bool session;

    // UART framing
    uint8_t rx_buf[BS_MAX_REQUEST + 1];  // One extra byte for a trailing '\r'.
    uint8_t rx_len;
    bool rx_overflow;
    bool rx_active;                      // Tracks if a frame is partially received.
    uint32_t rx_last_ms;
} bs_server_t;

/**
 * Initializes the server state.
 */
void bs_server_init(bs_server_t* server);

/**
 * Reset the server state and move to IDLE when the
 * physical reset button (NRST) is pressed.
 */
void bs_server_reset(bs_server_t* s);

/**
 * Push one received byte.
 *
 * @param `now_ms` a free running millisecond tick (HAL_GetTick()); wraparound is handled.
 *
 * @returns
 * the length of the reply written to `out` (which must be at least
 * `BS_REPLY_BUF` bytes long), or 0 if there is nothing to send. The
 * reply already
 * includes the terminating "\r\n" and is also null-terminated for convenience.
 * At most one reply is produced per call.

 */
size_t bs_server_feed(bs_server_t* s, uint8_t byte, uint32_t now_ms, char* out);

/**
 * Get the state of the server for the status LED.
 *
 * @returns The `bs_state_t` of the server.
 */
bs_state_t bs_server_get_state(const bs_server_t* s);

/**
 * Get which player's turn it is.
 *
 * @returns `0` = P1, `1` = P2.
 */
uint8_t bs_server_get_turn(const bs_server_t* s);
