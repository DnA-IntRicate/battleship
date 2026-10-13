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
    uint8_t rx_byte;

    volatile uint8_t tx_ready;
    size_t tx_len;
    char tx_buf[BS_REPLY_BUF];
} g_uart_state;

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
static void recv(void);
static void send(void);

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

    // Begin receive loop (interrupt mode)
    g_uart_state.tx_ready = 0;
    recv();

    // Set initial state
    g_prev_state = bs_server_get_state(&g_server);
    g_prev_turn  = bs_server_get_turn(&g_server);
    status_led(g_prev_state);

    while (1)
    {
        // Handle reply transmission
        if (g_uart_state.tx_ready)
        {
            // Transmit reply
            send();
            g_uart_state.tx_ready = 0;

            // Resume reception after a reply has been sent
            recv();
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
    NVIC_EnableIRQ(USART1_IRQn);
}

// Override the UART rx callback
void HAL_UART_RxCpltCallback(UART_HandleTypeDef* huart)
{
    if (huart->Instance != USART1)
        return;

    const size_t len = bs_server_feed(&g_server, g_uart_state.rx_byte, HAL_GetTick(), g_uart_state.tx_buf);
    if (len > 0)
    {
        // Handle invalid reply lengths
        if ((len > sizeof(g_uart_state.tx_buf)) || (len > UINT16_MAX))
            err_handler();

        g_uart_state.tx_len   = len;
        g_uart_state.tx_ready = 1;

        // Pause reception until the main loop transmits the reply
        return;
    }

    // The frame is incomplete, so receive the next byte
    recv();
}

// Override the UART interrupt handler
void USART1_IRQHandler(void)
{
    HAL_UART_IRQHandler(&g_uart_state.huart1);
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

static void recv(void)
{
    if (HAL_UART_Receive_IT(&g_uart_state.huart1, &g_uart_state.rx_byte, 1) != HAL_OK)
        err_handler();
}

static void send(void)
{
    const uint16_t len  = (uint16_t)g_uart_state.tx_len;
    const uint8_t* data = (uint8_t*)g_uart_state.tx_buf;

    if (HAL_UART_Transmit(&g_uart_state.huart1, data, len, HAL_MAX_DELAY) != HAL_OK)
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
