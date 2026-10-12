#include <main.h>
#include <server.h>
#include <lcd_stm32f0.h>
#include <stdio.h>
#include <string.h>


// LED port/pin arrays for easy indexing
const uint8_t LED_COUNT = 8;
GPIO_TypeDef* g_led_ports[8] = { GPIOB, GPIOB, GPIOB, GPIOB, GPIOB, GPIOB, GPIOB, GPIOB };
uint16_t g_led_pins[8]       = { GPIO_PIN_0, GPIO_PIN_1, GPIO_PIN_2, GPIO_PIN_3, GPIO_PIN_4, GPIO_PIN_5, GPIO_PIN_6, GPIO_PIN_7 };

bs_server_t g_server;
UART_HandleTypeDef g_huart1;

static void syclk_config(void);
static void gpio_init(void);
static void usart1_uart_init(void);
static void startup_anim(void);

static void set_leds(uint8_t mask);
static void clear_leds(void);

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

    uint8_t counter = 0;
    while (1)
    {
        // Ok so, we're gonna need a message builder or something
        // Strings in C, yay!
        // I wonder what happens on a nullptr dereference on the STM
        char message[64];
        int len = snprintf(message, sizeof(message), "Battleship broadcast from server %d!\r\n", counter++);
        if (len >= (int)sizeof(message))
            len = sizeof(message) - 1;  // Truncate

        HAL_UART_Transmit(&g_huart1, (uint8_t*)message, (uint16_t)len, HAL_MAX_DELAY);

        // HAL_Delay(1000);
    }

    // Cleanup
    bs_server_reset(&g_server);
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
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

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
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
        HAL_GPIO_Init(g_led_ports[i], &gpio_init_struct);
    }
}

/**
  * @brief USART1 Initialization Function
  * @param None
  * @retval None
  */
static void usart1_uart_init(void)
{
    g_huart1.Instance                    = USART1;
    g_huart1.Init.BaudRate               = 115200;
    g_huart1.Init.WordLength             = UART_WORDLENGTH_8B;
    g_huart1.Init.StopBits               = UART_STOPBITS_1;
    g_huart1.Init.Parity                 = UART_PARITY_NONE;
    g_huart1.Init.Mode                   = UART_MODE_TX_RX;
    g_huart1.Init.HwFlowCtl              = UART_HWCONTROL_NONE;
    g_huart1.Init.OverSampling           = UART_OVERSAMPLING_16;
    g_huart1.Init.OneBitSampling         = UART_ONE_BIT_SAMPLE_DISABLE;
    g_huart1.AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_NO_INIT;

    if (HAL_UART_Init(&g_huart1) != HAL_OK)
        err_handler();
}

static void startup_anim(void)
{
    // Splash screen
    lcd_putstring("Welcome to");
    lcd_command(LINE_TWO);
    lcd_putstring("BATTLESHIP!");

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

static void set_leds(uint8_t mask)
{
    GPIOB->BSRR = mask | ((~mask) << 16);
}

static void clear_leds(void)
{
    set_leds(0);
}

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void err_handler(void)
{
    __disable_irq();
    while (1)
    {
    }
}
