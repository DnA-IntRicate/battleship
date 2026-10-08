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

// We need this for payload encoding
static uint8_t xor_sum(const void* data, size_t len)
{
    const uint8_t* p = data;
    uint8_t x        = 0;

    while (len--)
        x ^= *p++;

    return x;
}

// Uppercase hex only
static int hex_value(uint8_t c)
{
    if ((c >= '0') && (c <= '9'))
        return c - '0';

    if ((c >= 'A') && (c <= 'F'))
        return c - 'A' + 10;

    return -1;
}

// Encodes the end of a message, optionally including a checksum.
static size_t finish_message(char* out, size_t len, bool use_checksum)
{
    static const char HEX_DIGITS[] = "0123456789ABCDEF";

    if (use_checksum)
    {
        uint8_t x  = xor_sum(out, len);
        out[len++] = '*';
        out[len++] = HEX_DIGITS[x >> 4];
        out[len++] = HEX_DIGITS[x & 0x0F];
    }

    out[len++] = '\r';
    out[len++] = '\n';
    out[len]   = '\0';

    return len;
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

    if (server->state == BS_IN_PROGRESS_PLANNING)
        return nack(out, "NOTREADY");

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

    size_t len = put(out, "OK:SUNK:");
    out[len++] = SHIP_CHAR[ship];

    return len;
}

/**
 * Command dispatching
 */

typedef enum cmd_t
{
    CMD_CONNECT,
    CMD_NEW,
    CMD_PLACE,
    CMD_MOVE,
    CMD_STATE,
    CMD_RESIGN,
    CMD_DISCONNECT,
    CMD_COUNT
} cmd_t;

static const struct
{
    // The name of the command
    const char* name;

    // The number of fields in the command (including the command name)
    uint8_t fields;

    // Field 1 is <player>
    bool has_player;

} COMMANDS[CMD_COUNT] = {
    [CMD_CONNECT]    = { "CONNECT",    1, false },
    [CMD_NEW]        = { "NEW",        1, false },
    [CMD_PLACE]      = { "PLACE",      5, true  },
    [CMD_MOVE]       = { "MOVE",       3, true  },
    [CMD_STATE]      = { "STATE",      2, true  },
    [CMD_RESIGN]     = { "RESIGN",     2, true  },
    [CMD_DISCONNECT] = { "DISCONNECT", 1, false }
};

// Splits `str` in-place on ':'.
// Returns the field count, or `MAX + 1` if there are more than `max` fields.
static int split_fields(char* str, char** fields, int max)
{
    int count = 0;
    char* p   = str;

    while (count < max)
    {
        fields[count++] = p;
        while (*p && (*p != ':'))
            ++p;

        if (*p == '\0')
            return count;

        *p++ = '\0';
    }

    // There may be another field after max
    return (*p) ? (max + 1) : count;
}

static size_t dispatch_command(bs_server_t* server, char* payload, char* out)
{
    char* fields[BS_MAX_FIELDS];
    int field_count = split_fields(payload, fields, BS_MAX_FIELDS);

    int c;
    for (c = 0; c < CMD_COUNT; ++c)
        if (strcmp(fields[0], COMMANDS[c].name) == 0)
            break;

    if ((c == CMD_COUNT || (field_count != COMMANDS[c].fields)))
        return nack(out, "BADCMD");

    int player = -1;
    if (COMMANDS[c].has_player)
    {
        player = parse_player(fields[1]);
        if (player < 0)
            return nack(out, "BADCMD");
    }

    // Cannot dispatch a game command without an active session
    if ((c != CMD_CONNECT) && !server->session)
        return nack(out, "NOSESSION");

    switch ((cmd_t)c)
    {
        case CMD_CONNECT:    return command_connect(server, out);
        case CMD_NEW:        return command_new(server, out);
        case CMD_PLACE:      return command_place(server, player, fields, out);
        case CMD_MOVE:       return command_move(server, player, fields, out);
        case CMD_STATE:      return command_state(server, player, out);
        case CMD_RESIGN:     return command_resign(server, out);
        case CMD_DISCONNECT: return command_disconnect(server, out);
        case CMD_COUNT:      break;
    }

    return nack(out, "BADCMD");
}

/**
 * Message framing & processing
 */

static size_t process_frame(bs_server_t* server, const uint8_t* line, size_t len, char* out)
{
    // A trailing "*HH" means the client wants a checksummed reply, even if
    // the request itself turns out to be bad.
    bool has_checksum = (len >= 3) && (line[len - 3] == '*');
    size_t my_len     = has_checksum ? (len - 3) : len;

    // Invalid bytes, then checksum (a frame containing any byte outside the range 0x20 - 0x7E is rejected).
    for (size_t i = 0; i < len; ++i)
        if ((line[i] < 0x20) || (line[i] > 0x7E))
            return finish_message(out, nack(out, "BADCMD"), has_checksum);

    if (has_checksum)
    {
        int hi = hex_value(line[len - 2]);
        int lo = hex_value(line[len - 1]);

        if ((hi < 0) || (lo < 0) || ((uint8_t)((hi << 4) | lo) != xor_sum(line, my_len)))
            return finish_message(out, nack(out, "CHECKSUM"), has_checksum);
    }

    char payload[BS_MAX_REQUEST + 1];
    memcpy(payload, line, my_len);
    payload[my_len] = '\0';

    return finish_message(out, dispatch_command(server, payload, out), has_checksum);
}

static void rx_reset(bs_server_t* server)
{
    server->rx_len      = 0;
    server->rx_overflow = false;
    server->rx_active   = false;
}

/**
 * Public API
 */

void bs_server_init(bs_server_t* server)
{
    memset(server, 0, sizeof(bs_server_t));
    game_reset(server);
}

void bs_server_reset(bs_server_t* server)
{
    game_reset(server);
}

size_t bs_server_feed(bs_server_t* server, uint8_t byte, uint32_t now_ms, char* out)
{
    // A partial frame that has been silent for 500 ms is dropped
    // without a reply. Evaluated lazily when the next byte arrives, which
    // is indistinguishable from dropping it exactly at 500 ms.
    if (server->rx_active && ((uint32_t)(now_ms - server->rx_last_ms) >= BS_PARTIAL_TIMEOUT_MS))
        rx_reset(server);

    server->rx_last_ms = now_ms;

    if (byte != '\n')
    {
        server->rx_active = true;
        if (server->rx_len < sizeof server->rx_buf)
            server->rx_buf[server->rx_len++] = byte;
        else
            server->rx_overflow = true;  // Keep discarding up to '\n'

        return 0;
    }

    // End of line
    size_t len = server->rx_len;
    bool over  = server->rx_overflow;
    if (!over && (len > 0) && ((server->rx_buf[len - 1] == '\r')))
        len--;  // "\r\n" terminator

    size_t reply = 0;
    if (over || (len > BS_MAX_REQUEST))
        reply = finish_message(out, nack(out, "TOOLONG"), false);  // Frame exceeded max length
    else if (len > 0)
        reply = process_frame(server, server->rx_buf, len, out);

    rx_reset(server);
    return reply;
}

bs_state_t bs_server_get_state(const bs_server_t* server)
{
    return server->state;
}

uint8_t bs_server_get_turn(const bs_server_t* server)
{
    return server->turn;
}
