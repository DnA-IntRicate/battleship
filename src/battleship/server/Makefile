#######################################################
# EEE3095S 2026 - Project
#
# Let's play Battleship!
#
# Generic gcc Makefile.
#######################################################

TARGET = battleship-server
DEBUG = 1
OPT = -Og
BUILD_DIR = build

######################################
# Source
######################################

# C sources
C_SOURCES =  \
core/source/main.c \
core/source/stm32f0xx_hal_msp.c \
core/source/stm32f0xx_it.c \
core/source/syscalls.c \
core/source/sysmem.c \
core/source/system_stm32f0xx.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_adc.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_adc_ex.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_cortex.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_dac.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_dac_ex.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_dma.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_exti.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_flash.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_flash_ex.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_gpio.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_i2c.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_i2c_ex.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_pwr.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_pwr_ex.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_rcc.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_rcc_ex.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_tim.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_tim_ex.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_ll_exti.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_ll_gpio.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_ll_rcc.c \
drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_ll_utils.c \
# drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_uart.c \
# drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_uart_ex.c \

# ASM sources
ASM_SOURCES =  \
core/asm/startup_stm32f051c8tx.s


#######################################
# Binaries
#######################################
PREFIX = arm-none-eabi-

# STM32CubeIDE puts its GNU toolchain on the PATH when it runs this Makefile.
# From a plain terminal, if arm-none-eabi-gcc is not on PATH, fall back to the
# toolchain inside a standard STM32CubeIDE install, or pass GCC_PATH=...
ifndef GCC_PATH
	ifeq ($(shell command -v $(PREFIX)gcc 2>/dev/null),)
		GCC_PATH := $(firstword $(wildcard \
		  /Applications/STM32CubeIDE.app/Contents/Eclipse/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.*/tools/bin \
		  $(HOME)/st/stm32cubeide*/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.*/tools/bin \
		  /opt/st/stm32cubeide*/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.*/tools/bin))
	endif
endif

# The gcc compiler bin path can be either defined in make command via GCC_PATH variable (> make GCC_PATH=xxx)
# either it can be added to the PATH environment variable.
ifdef GCC_PATH
	CC = $(GCC_PATH)/$(PREFIX)gcc
	AS = $(GCC_PATH)/$(PREFIX)gcc -x assembler-with-cpp
	CP = $(GCC_PATH)/$(PREFIX)objcopy
	SZ = $(GCC_PATH)/$(PREFIX)size
else
	CC = $(PREFIX)gcc
	AS = $(PREFIX)gcc -x assembler-with-cpp
	CP = $(PREFIX)objcopy
	SZ = $(PREFIX)size
endif

HEX = $(CP) -O ihex
BIN = $(CP) -O binary -S

#######################################
# Flags
#######################################

# CPU
CPU = -mcpu=cortex-m0

# FPU
# NONE for Cortex-M0/M0+/M3

# Mcu
MCU = $(CPU) -mthumb # $(FPU) $(FLOAT-ABI)

# Assembly defines
ASM_DEFS =

# C defines
C_DEFS =  \
-DSTM32F051x8 \
-DUSE_FULL_LL_DRIVER \
-DUSE_HAL_DRIVER \
-DHSE_VALUE=8000000 \
-DHSE_STARTUP_TIMEOUT=100 \
-DLSE_STARTUP_TIMEOUT=5000 \
-DLSE_VALUE=32768 \
-DHSI_VALUE=8000000 \
-DLSI_VALUE=40000 \
-DVDD_VALUE=3300 \
-DPREFETCH_ENABLE=1 \
-DINSTRUCTION_CACHE_ENABLE=0 \
-DDATA_CACHE_ENABLE=0

# Assembly includes
ASM_INCLUDES =

# C includes
C_INCLUDES =  \
-Icore/include \
-Idrivers/STM32F0xx_HAL_Driver/Inc \
-Idrivers/CMSIS/Device/ST/STM32F0xx/Include \
-Idrivers/CMSIS/Include

# Compile gcc flags
ASMFLAGS = $(MCU) $(ASM_DEFS) $(ASM_INCLUDES) $(OPT) -Wall -fdata-sections -ffunction-sections
CFLAGS += $(MCU) $(C_DEFS) $(C_INCLUDES) $(OPT) -Wall -fdata-sections -ffunction-sections

ifeq ($(DEBUG), 1)
	CFLAGS += -g -gdwarf-2
endif

# Generate dependency information
CFLAGS += -MMD -MP -MF"$(@:%.o=%.d)"

# Linker script
LDSCRIPT = STM32F051C8TX_FLASH.ld

# Libraries
LIBS = -lc -lm -lnosys
LIBDIR =
LDFLAGS = $(MCU) -specs=nano.specs -T$(LDSCRIPT) $(LIBDIR) $(LIBS) -Wl,-Map=$(BUILD_DIR)/$(TARGET).map,--cref -Wl,--gc-sections

# Default action: build all
all: $(BUILD_DIR)/$(TARGET).elf $(BUILD_DIR)/$(TARGET).hex $(BUILD_DIR)/$(TARGET).bin

# List of objects
OBJECTS = $(addprefix $(BUILD_DIR)/,$(notdir $(C_SOURCES:.c=.o)))
vpath %.c $(sort $(dir $(C_SOURCES)))

# List of ASM program objects
OBJECTS += $(addprefix $(BUILD_DIR)/,$(notdir $(ASM_SOURCES:.s=.o)))
vpath %.s $(sort $(dir $(ASM_SOURCES)))

$(BUILD_DIR)/%.o: %.c Makefile | $(BUILD_DIR)
	$(CC) -c $(CFLAGS) -Wa,-a,-ad,-alms=$(BUILD_DIR)/$(notdir $(<:.c=.lst)) $< -o $@

$(BUILD_DIR)/%.o: %.s Makefile | $(BUILD_DIR)
	$(AS) -c $(CFLAGS) $< -o $@

$(BUILD_DIR)/$(TARGET).elf: $(OBJECTS) Makefile
	$(CC) $(OBJECTS) $(LDFLAGS) -o $@
	$(SZ) $@

$(BUILD_DIR)/%.hex: $(BUILD_DIR)/%.elf | $(BUILD_DIR)
	$(HEX) $< $@

$(BUILD_DIR)/%.bin: $(BUILD_DIR)/%.elf | $(BUILD_DIR)
	$(BIN) $< $@

$(BUILD_DIR):
	mkdir $@

clean:
	-rm -fR $(BUILD_DIR)

-include $(wildcard $(BUILD_DIR)/*.d)
