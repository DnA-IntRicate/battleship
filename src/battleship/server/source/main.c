#include <main.h>
#include <server.h>
#include <lcd_stm32f0.h>
#include <stdio.h>
#include <string.h>

bs_server_t server;
UART_HandleTypeDef huart1;

static void syclk_config(void);
static void gpio_init(void);
static void usart1_uart_init(void);

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

    // Splash screen
    init_LCD();
    lcd_command(CLEAR | CURSOR_HOME | TWOLINE_MODE);
    lcd_putstring("Welcome to");
    lcd_command(LINE_TWO);
    lcd_putstring("BATTLESHIP!");

    // Initialize all configured peripherals
    gpio_init();
    usart1_uart_init();

    // Initialize server state
    bs_server_init(&server);

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

        HAL_UART_Transmit(&huart1, (uint8_t*)message, (uint16_t)len, HAL_MAX_DELAY);

        // HAL_Delay(1000);
    }

    // Cleanup
    bs_server_reset(&server);
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
  * @brief USART1 Initialization Function
  * @param None
  * @retval None
  */
static void usart1_uart_init(void)
{
    huart1.Instance                    = USART1;
    huart1.Init.BaudRate               = 115200;
    huart1.Init.WordLength             = UART_WORDLENGTH_8B;
    huart1.Init.StopBits               = UART_STOPBITS_1;
    huart1.Init.Parity                 = UART_PARITY_NONE;
    huart1.Init.Mode                   = UART_MODE_TX_RX;
    huart1.Init.HwFlowCtl              = UART_HWCONTROL_NONE;
    huart1.Init.OverSampling           = UART_OVERSAMPLING_16;
    huart1.Init.OneBitSampling         = UART_ONE_BIT_SAMPLE_DISABLE;
    huart1.AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_NO_INIT;

    if (HAL_UART_Init(&huart1) != HAL_OK)
        err_handler();
}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void gpio_init(void)
{
    __HAL_RCC_GPIOA_CLK_ENABLE();
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
