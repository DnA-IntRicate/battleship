#include <main.h>
#include <server.h>
#include <lcd_stm32f0.h>
#include <stdio.h>
#include <string.h>


// LED port/pin arrays for easy indexing
const uint8_t LED_COUNT = 10;
uint16_t g_led_pins[10] = {
    GPIO_PIN_0, GPIO_PIN_1, GPIO_PIN_2, GPIO_PIN_3, GPIO_PIN_4, GPIO_PIN_5, GPIO_PIN_6, GPIO_PIN_7, GPIO_PIN_10, GPIO_PIN_11
};

bs_server_t g_server;
bs_state_t g_prev_state;
uint8_t g_prev_turn;

// UART state
struct uart_state_t
{
    UART_HandleTypeDef huart1;
    char tx_buf[BS_REPLY_BUF];
} g_uart_state;

// The max size of the receive ring buffer.
#define RX_RING_SIZE 256u

// Receive ring buffer.
// Filled by the USART1 ISR, drained by the main loop.
static volatile uint8_t g_rx_ring[RX_RING_SIZE];
static volatile uint32_t g_rx_head;
static volatile uint32_t g_rx_tail;

// Hardware initalization
static void syclk_config(void);
static void gpio_init(void);
static void usart1_uart_init(void);
static void startup_anim(void);

// Helpers
static void splashscreen(void);
static void set_leds(uint8_t mask);
static void clear_leds(void);
static void status_led(bs_state_t state);
static void status_lcd(bs_state_t state, uint8_t turn);

// Server & message handling
static bool rx_pop(uint8_t* out);
static void send(size_t len);

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{
    // MCU Configuration
    HAL_Init();

    // Configure the system clock
    syclk_config();

    // Initialize all configured peripherals
    gpio_init();
    usart1_uart_init();

    // Splash screen & startup animation
    startup_anim();

    // Initialize server state
    bs_server_init(&g_server);

    // Set initial state
    g_prev_state = bs_server_get_state(&g_server);
    g_prev_turn  = bs_server_get_turn(&g_server);
    status_led(g_prev_state);

    // Begin continuous reception
    USART1->CR1 |= USART_CR1_RXNEIE;

    while (1)
    {
        // Feed one received byte per iteration so the status update below
        // is never starved by a burst of input
        uint8_t byte;
        if (rx_pop(&byte))
        {
            const size_t len = bs_server_feed(&g_server, byte, HAL_GetTick(), g_uart_state.tx_buf);
            if (len > 0)
            {
                // Handle invalid reply lengths
                if ((len > sizeof(g_uart_state.tx_buf)) || (len > UINT16_MAX))
                    err_handler();

                // Bytes that arrive while we transmit are buffered by the ISR
                send(len);
            }
        }

        bs_state_t state = bs_server_get_state(&g_server);
        uint8_t turn     = bs_server_get_turn(&g_server);

        if ((state != g_prev_state) || (turn != g_prev_turn))
        {
            status_led(state);
            status_lcd(state, turn);

            g_prev_state = state;
            g_prev_turn  = turn;
        }
    }
}

static void syclk_config(void)
{
    RCC_OscInitTypeDef RCC_OscInitStruct   = {};
    RCC_ClkInitTypeDef RCC_ClkInitStruct   = {};
    RCC_PeriphCLKInitTypeDef PeriphClkInit = {};

    // Initializes the RCC Oscillators according to the specified parameters
    // in the RCC_OscInitTypeDef structure.
    RCC_OscInitStruct.OscillatorType      = RCC_OSCILLATORTYPE_HSI;
    RCC_OscInitStruct.HSIState            = RCC_HSI_ON;
    RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    RCC_OscInitStruct.PLL.PLLState        = RCC_PLL_NONE;

    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
        err_handler();

    // Initializes the CPU, AHB and APB buses clocks
    RCC_ClkInitStruct.ClockType      = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_PCLK1;
    RCC_ClkInitStruct.SYSCLKSource   = RCC_SYSCLKSOURCE_HSI;
    RCC_ClkInitStruct.AHBCLKDivider  = RCC_SYSCLK_DIV1;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;

    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_0) != HAL_OK)
        err_handler();

    PeriphClkInit.PeriphClockSelection = RCC_PERIPHCLK_USART1;
    PeriphClkInit.Usart1ClockSelection = RCC_USART1CLKSOURCE_PCLK1;
    if (HAL_RCCEx_PeriphCLKConfig(&PeriphClkInit) != HAL_OK)
        err_handler();
}

static void gpio_init(void)
{
    // Enable GPIO clocks
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();

    // Initialize the LCD
    init_LCD();
    lcd_command(CLEAR | CURSOR_HOME | TWOLINE_MODE);

    // Configure all LEDs
    GPIO_InitTypeDef gpio_init_struct = {};
    gpio_init_struct.Mode             = GPIO_MODE_OUTPUT_PP;
    gpio_init_struct.Pull             = GPIO_NOPULL;
    gpio_init_struct.Speed            = GPIO_SPEED_FREQ_HIGH;

    for (uint8_t i = 0; i < LED_COUNT; ++i)
    {
        gpio_init_struct.Pin = g_led_pins[i];
        HAL_GPIO_Init(GPIOB, &gpio_init_struct);
    }
}

static void usart1_uart_init(void)
{
    g_uart_state.huart1.Instance                    = USART1;
    g_uart_state.huart1.Init.BaudRate               = 115200;
    g_uart_state.huart1.Init.WordLength             = UART_WORDLENGTH_8B;
    g_uart_state.huart1.Init.StopBits               = UART_STOPBITS_1;
    g_uart_state.huart1.Init.Parity                 = UART_PARITY_NONE;
    g_uart_state.huart1.Init.Mode                   = UART_MODE_TX_RX;
    g_uart_state.huart1.Init.HwFlowCtl              = UART_HWCONTROL_NONE;
    g_uart_state.huart1.Init.OverSampling           = UART_OVERSAMPLING_16;
    g_uart_state.huart1.Init.OneBitSampling         = UART_ONE_BIT_SAMPLE_DISABLE;
    g_uart_state.huart1.AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_NO_INIT;

    if (HAL_UART_Init(&g_uart_state.huart1) != HAL_OK)
        err_handler();

    // Enable interrupts
    USART1->CR3 |= USART_CR3_EIE; // Error ORE/FE/NE
    NVIC_EnableIRQ(USART1_IRQn);
}

// Override the UART interrupt handler
void USART1_IRQHandler(void)
{
    // Clear any overrun / noise / framing / parity error flags
    if (USART1->ISR & (USART_ISR_ORE | USART_ISR_NE | USART_ISR_FE | USART_ISR_PE))
        USART1->ICR = USART_ICR_ORECF | USART_ICR_NCF | USART_ICR_FECF | USART_ICR_PECF;

    // Reading RDR clears RXNE
    if (USART1->ISR & USART_ISR_RXNE)
    {
        const uint8_t byte  = (uint8_t)USART1->RDR;
        const uint32_t head = g_rx_head;
        const uint32_t next = (head + 1u) & (RX_RING_SIZE - 1u);

        // If the ring is full the byte is dropped.
        // The server handles any garbage results.
        if (next != g_rx_tail)
        {
            g_rx_ring[head] = byte;
            g_rx_head       = next;
        }
    }
}

static void startup_anim(void)
{
    splashscreen();

    // Rolling LED startup animation
    for (int i = 0; i < LED_COUNT; ++i)
    {
        set_leds((uint8_t)(1 << i));
        HAL_Delay(50);
    }

    for (int i = LED_COUNT - 1; i >= 0; --i)
    {
        set_leds((uint8_t)(1 << i));
        HAL_Delay(50);
    }

    clear_leds();
    HAL_Delay(100);
    set_leds(0xFF);
}

static void splashscreen(void)
{
    lcd_command(CLEAR);
    lcd_putstring("Welcome to");
    lcd_command(LINE_TWO);
    lcd_putstring("BATTLESHIP!");
}

static void set_leds(uint8_t mask)
{
    GPIOB->BSRR = mask | ((~mask) << 16);
}

static void clear_leds(void)
{
    set_leds(0);
}

static void status_led(bs_state_t state)
{
    /**
     * Maps a game state to an LED colour for D9.
     *
     * Green: Idle
     * Orange: Planning-phase
     * Red: Firing phase
     * Off: Game over
     */

    // PB10 = Red; PB11 = Green
    switch (state)
    {
        case BS_IDLE:                 HAL_GPIO_WritePin(GPIOB, GPIO_PIN_11, SET); break;
        case BS_IN_PROGRESS_PLANNING: HAL_GPIO_WritePin(GPIOB, GPIO_PIN_10 | GPIO_PIN_11, SET); break;
        case BS_IN_PROGRESS_FIRING:   HAL_GPIO_WritePin(GPIOB, GPIO_PIN_10, SET); break;
        case BS_GAME_OVER:            HAL_GPIO_WritePin(GPIOB, GPIO_PIN_10 | GPIO_PIN_11, RESET); break;
    }
}

static void status_lcd(bs_state_t state, uint8_t turn)
{
    switch (state)
    {
        case BS_IDLE: splashscreen(); break;
        case BS_IN_PROGRESS_PLANNING:
        {
            lcd_command(CLEAR);
            lcd_putstring("Planning phase");
            lcd_command(LINE_TWO);

            char message[16];
            snprintf(message, sizeof(message), "Turn: P%d.", turn + 1);
            lcd_putstring(message);

            break;
        }
        case BS_IN_PROGRESS_FIRING:
        {
            lcd_command(CLEAR);
            lcd_putstring("Firing phase");
            lcd_command(LINE_TWO);

            char message[16];
            snprintf(message, sizeof(message), "Turn: P%d.", turn + 1);
            lcd_putstring(message);

            break;
        }
        case BS_GAME_OVER:
        {
            lcd_command(CLEAR);
            lcd_putstring("GAME OVER!");

            break;
        }
    }
}

static bool rx_pop(uint8_t* out)
{
    const uint32_t tail = g_rx_tail;
    if (tail == g_rx_head)
        return false;

    *out      = g_rx_ring[tail];
    g_rx_tail = (tail + 1u) & (RX_RING_SIZE - 1u);

    return true;
}

static void send(size_t len)
{
    const uint8_t* data = (uint8_t*)g_uart_state.tx_buf;
    if (HAL_UART_Transmit(&g_uart_state.huart1, data, (uint16_t)len, HAL_MAX_DELAY) != HAL_OK)
        err_handler();
}

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void err_handler(void)
{
    // TODO(Adam): Transmit a catastrophic error message back to the client here

    __disable_irq();
    while (1)
    {
    }
}
