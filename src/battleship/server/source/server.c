/**
 * Battleship authoritative server state.
 *
 * @authors Adam Foflonker, Muddathir Firfirey
 * @date 07 Oct 2026
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
 * Helpers
 */

static size_t put(char* out, const char* str)
{
    size_t len = strlen(str);
    memcpy(out, str, len);

    return len;
}

static size_t nack(char* out, const char* reason)
{
    size_t len = put(out, "NACK:");
    return len + put(out + len, reason);
}

/**
 * Parsing
 */

// Returns "P1" -> 0, "P2" -> 1, else -1
static int parse_player(const char* str)
{
    if ((str[0] == 'P') && ((str[1] == '1') || (str[1] == '2')) && (str[2] == '\0'))
        return (int)(str[1] - '1');

    return -1;
}

static int ship_index_from_char(char c)
{
    for (int i = 0; i < BS_NUM_SHIPS; ++i)
        if (c == SHIP_CHAR[i])
            return i;

    return -1;
}

// str must be one of: { 'C', 'B', 'R', 'S', 'D' }
static int parse_ship(const char* str)
{
    if (!str)
        return -1;

    if (strlen(str) > 2)
        return -1;

    if (str[0] == '\0')
        return -1;

    return ship_index_from_char(str[0]);
}

typedef enum cell_result_t
{
    CELL_BAD = 0,
    CELL_OOR,
    CELL_OK
} cell_result_t;

// A valid cell is one uppercase letter followed by an integral number
// Examples:
//  Correct form but off the board: (K3, A10) -> CELL_OOR (out of range)
//  Malformed cell: (5F, D-21): CELL_BAD
//
// Returns CELL_OK if the cell could be parsed
static cell_result_t parse_cell(const char* str, uint8_t* out_index)
{
    // First char is not an uppercase letter
    if ((str[0] < 'A') || (str[0] > 'Z'))
        return CELL_BAD;

    const char* num = str + 1;
    if ((num[0] == '\0') || ((num[0] == '0') && (num[1] != '\0')))  // Letter only or leading zero
        return CELL_BAD;

    uint32_t col = 0;
    for (const char* p = num; *p; ++p)
    {
        if ((*p < '0') || (*p > '9'))
            return CELL_BAD;

        if (col < 1000)
            col = col * 10 + (uint32_t)(*p - '0');
    }

    uint32_t row = (uint32_t)(str[0] - 'A');
    if ((row >= 10) || (col >= 10))
        return CELL_OOR;

    *out_index = (uint8_t)(row * 10 + col);
    return CELL_OK;
}

/**
 * Game logic and command handlers.
 */

static size_t command_connect(bs_server_t* server, char* out)
{
    server->session = true;
    return put(out, "OK");
}

static size_t command_disconnect(bs_server_t* server, char* out)
{
    // Don't disconnect while the game is in progress
    if ((server->state == BS_IN_PROGRESS_FIRING) || (server->state == BS_IN_PROGRESS_PLANNING))
        return nack(out, "BADSTATE");

    game_reset(server);
    server->session = false;

    return put(out, "OK");
}

static size_t command_new(bs_server_t* server, char* out)
{
    // Don't start a new game while one is already in-progress
    if ((server->state == BS_IN_PROGRESS_FIRING) || (server->state == BS_IN_PROGRESS_PLANNING))
        return nack(out, "BADSTATE");

    game_reset(server);
    server->state = BS_IN_PROGRESS_PLANNING;

    return put(out, "OK:PLACE");
}

static size_t command_resign(bs_server_t* server, char* out)
{
    // Can't forfeit a game that hasn't started
    if ((server->state != BS_IN_PROGRESS_FIRING) && (server->state != BS_IN_PROGRESS_PLANNING))
        return nack(out, "NOGAME");

    server->state = BS_GAME_OVER;
    return put(out, "OK:GAMEOVER");
}

// Format: BOARD:<turn>:<own>:<target>
static size_t command_state(bs_server_t* server, int player, char* out)
{
    // Can't update game state when there's no game
    if (server->state == BS_IDLE)
        return nack(out, "NOGAME");

    const bs_fleet_t* me  = &server->fleet[player];
    const bs_fleet_t* opp = &server->fleet[1 - player];
    size_t len            = put(out, "BOARD:");

    if (server->state == BS_GAME_OVER)
    {
        out[len++] = '-';
        out[len++] = '-';
    }
    else
    {
        // <turn>
        out[len++] = 'P';
        out[len++] = (char)('1' + server->turn);
    }

    out[len++] = ':';

    // <own>: Ship letters, 'X' where the opp hit, 'o' where it missed.
    for (int i = 0; i < BS_NUM_CELLS; ++i)
    {
        char c = me->cell[i];
        if (me->shot[i])
            c = (c == '.') ? 'o' : 'X';

        out[len++] = c;
    }

    out[len++] = ':';

    // <target>: What this player's shots have revealed.
    for (int i = 0; i < BS_NUM_CELLS; ++i)
    {
        char c = '.';
        if (opp->shot[i])
            c = (opp->cell[i] == '.') ? 'o' : 'X';

        out[len++] = c;
    }

    return len;
}

// Format: PLACE:<player>:<ship>:<cell>:<H|V>
static size_t command_place(bs_server_t* server, int player, char* const* f, char* out)
{
    if (server->state == BS_IDLE)
        return nack(out, "NOGAME");

    if (server->state != BS_IN_PROGRESS_PLANNING)
        return nack(out, "BADSTATE");

    if (player != server->turn)
        return nack(out, "NOTURN");

    // Validate the field values
    char orientation = f[4][0];
    if ((f[4][1] != '\0') || ((orientation != 'H') && (orientation != 'V')))
        return nack(out, "BADCMD");

    uint8_t bow      = 0;
    cell_result_t cr = parse_cell(f[3], &bow);
    if (cr != CELL_OK)
        return nack(out, (cr == CELL_BAD) ? "BADCMD" : "RANGE");

    // Validate the ship index/char
    int ship = parse_ship(f[3]);
    if (ship < 0)
        return nack(out, "BADSHIP");

    // Validate duplicate ship
    bs_fleet_t* fleet = &server->fleet[player];
    if (fleet->placed_mask & (1 << ship))
        return nack(out, "DUPSHIP");

    // Extract the ship coordinates
    uint32_t len    = SHIP_LEN[ship];
    bool horizontal = (orientation == 'H');
    uint32_t row    = bow / 10;
    uint32_t col    = bow % 10;

    if (horizontal ? (col + len > 10) : (row + len > 10))
        return nack(out, "RANGE");

    // Handle overlapping ships
    uint32_t step = horizontal ? 1 : 10;
    for (uint32_t i = 0; i < len; ++i)
        if (fleet->cell[bow + i * step] != '.')
            return nack(out, "OVERLAP");

    // Commit a valid ship placement
    for (uint32_t i = 0; i < len; ++i)
        fleet->cell[bow + i * step] = SHIP_CHAR[ship];

    fleet->remaining[ship]  = (uint8_t)len;
    fleet->placed_mask     |= (uint8_t)(1 << ship);
    ++fleet->placed_count;

    if (fleet->placed_count == BS_NUM_SHIPS)
    {
        // Move to P2
        if (player == 0)
            server->turn = 1;
        else
        {
            // Enter firing phase
            server->state = BS_IN_PROGRESS_FIRING;
            server->turn  = 0;

            return put(out, "OK:READY");
        }
    }

    return put(out, "OK:PLACED");
}

// Format: MOVE:<player>:<cell>
// NOTE(Adam): Move means to make a shot (move on the board) - NOT to physically move a ship.
static size_t command_move(bs_server_t* server, int player, char* const* f, char* out)
{
    if (server->state == BS_IDLE)
        return nack(out, "NOGAME");

    if (server->state != BS_IN_PROGRESS_PLANNING)
        return nack(out, "BADSTATE");

    if (player != server->turn)
        return nack(out, "NOTURN");

    uint8_t idx      = 0;
    cell_result_t cr = parse_cell(f[2], &idx);
    if (cr != CELL_OK)
        return nack(out, (cr == CELL_BAD) ? "BADCMD" : "RANGE");

    bs_fleet_t* target = &server->fleet[1 - player];
    if (target->shot[idx])
        return nack(out, "OCCUPIED");  // The player has already fired on this cell

    // Commit a valid shot/move and rotate to the next player
    target->shot[idx] = 1;
    char c            = target->cell[idx];
    server->turn      = (uint8_t)(1 - player);

    // Shot landed in open waters
    if (c == '.')
        return put(out, "OK:MISS");

    int ship = ship_index_from_char(c);
    if (--target->remaining[ship] > 0)
        return put(out, "OK:HIT");

    bool fleet_dead = true;
    for (int i = 0; i < BS_NUM_SHIPS; ++i)
        if (target->remaining[i] != 0)
            fleet_dead = false;

    if (fleet_dead)
    {
        server->state = BS_GAME_OVER;
        size_t len    = put(out, "WIN:P");
        out[len++]    = (char)('1' + player);

        return len;
    }

    size_t len = put(out, "OK:SUNK");
    out[len++] = SHIP_CHAR[ship];

    return len;
}

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

// TODO: Implement this!
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
