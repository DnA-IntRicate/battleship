/**
 * Battleship authoritative server state.
 *
 * @authors Adam Foflonker, Muddathir Firfirey
 * @date 06 Oct 2026
 * @version 1.0
 */
#include <server.h>
#include <string.h>


#define BS_NUM_SHIPS  5
#define BS_MAX_FIELDS 5

// Parallel arrays defining ship types mapped to their lengths
static const char SHIP_CHAR[BS_NUM_SHIPS]   = { 'C', 'B', 'R', 'S', 'D' };
static const uint8_t SHIP_LEN[BS_NUM_SHIPS] = { 5, 4, 3, 3, 2 };

/**
 * Game state
 */

static void fleet_clear(bs_fleet_t* fleet)
{
    memset(fleet, 0, sizeof(bs_fleet_t));
    memset(fleet->cell, '.', BS_NUM_CELLS);  // Open waters must be marked with a '.'
}

static void game_reset(bs_server_t* server)
{
    fleet_clear(&server->fleet[0]);
    fleet_clear(&server->fleet[1]);

    server->state = BS_IDLE;
    server->turn  = 0;
}

/**
 * Public API
 */

void bs_server_init(bs_server_t* server)
{
    memset(server, 0, sizeof(bs_server_t));
    game_reset(server);
}

void bs_server_reset(bs_server_t* s)
{
    game_reset(s);
}

size_t bs_server_feed(bs_server_t* s, uint8_t byte, uint32_t now_ms, char* out)
{
    return 0u;
}

bs_state_t bs_server_get_state(const bs_server_t* server)
{
    return server->state;
}

uint8_t bs_server_get_turn(const bs_server_t* server)
{
    return server->turn;
}
