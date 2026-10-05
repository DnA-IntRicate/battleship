#######################################################
# EEE3095S 2026 - Project
#
# Let's play Battleship!
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
src/battleship/server/source/main.c \
src/battleship/server/source/stm32f0xx_hal_msp.c \
src/battleship/server/source/stm32f0xx_it.c \
src/battleship/server/source/syscalls.c \
src/battleship/server/source/sysmem.c \
src/battleship/server/source/system_stm32f0xx.c \
src/battleship/server/drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal.c \
src/battleship/server/drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_cortex.c \
src/battleship/server/drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_dma.c \
src/battleship/server/drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_exti.c \
src/battleship/server/drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_flash.c \
src/battleship/server/drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_flash_ex.c \
src/battleship/server/drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_gpio.c \
src/battleship/server/drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_i2c.c \
src/battleship/server/drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_i2c_ex.c \
src/battleship/server/drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_pwr.c \
src/battleship/server/drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_pwr_ex.c \
src/battleship/server/drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_rcc.c \
src/battleship/server/drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_rcc_ex.c \
src/battleship/server/drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_tim.c \
src/battleship/server/drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_uart.c \
src/battleship/server/drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_tim_ex.c \
src/battleship/server/drivers/STM32F0xx_HAL_Driver/Src/stm32f0xx_hal_uart_ex.c \

# ASM sources
ASM_SOURCES =  \
src/battleship/server/asm/startup_stm32f051x8.s

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
# CFLAGS
#######################################

# CPU
CPU = -mcpu=cortex-m0

# FPU
# NONE for Cortex-M0/M0+/M3

# MCU
MCU = $(CPU) -mthumb $(FPU) $(FLOAT-ABI)

# Assembly defines
ASM_DEFS =

# C defines
C_DEFS =  \
-DSTM32F051x8 \
-DUSE_HAL_DRIVER

# Assembly includes
ASM_INCLUDES =

# C includes
C_INCLUDES =  \
-Isrc/battleship/server/include \
-Isrc/battleship/server/drivers/STM32F0xx_HAL_Driver/Inc \
-Isrc/battleship/server/drivers/STM32F0xx_HAL_Driver/Inc/Legacy \
-Isrc/battleship/server/drivers/CMSIS/Device/ST/STM32F0xx/Include \
-Isrc/battleship/server/drivers/CMSIS/Include

# Compile gcc flags
ASMFLAGS = $(MCU) $(ASM_DEFS) $(ASM_INCLUDES) $(OPT) -Wall -fdata-sections -ffunction-sections
CFLAGS += $(MCU) $(C_DEFS) $(C_INCLUDES) $(OPT) -Wall -fdata-sections -ffunction-sections

ifeq ($(DEBUG), 1)
CFLAGS += -g -gdwarf-2
endif

# Generate dependency information
CFLAGS += -MMD -MP -MF"$(@:%.o=%.d)"

# Linker script
LDSCRIPT = STM32F051xx_FLASH.ld

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
OBJECTS += $(addprefix $(BUILD_DIR)/,$(notdir $(ASMM_SOURCES:.S=.o)))
vpath %.S $(sort $(dir $(ASMM_SOURCES)))

$(BUILD_DIR)/%.o: %.c Makefile | $(BUILD_DIR)
	$(CC) -c $(CFLAGS) -Wa,-a,-ad,-alms=$(BUILD_DIR)/$(notdir $(<:.c=.lst)) $< -o $@

$(BUILD_DIR)/%.o: %.s Makefile | $(BUILD_DIR)
	$(AS) -c $(CFLAGS) $< -o $@
$(BUILD_DIR)/%.o: %.S Makefile | $(BUILD_DIR)
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

# Cleanup
clean:
	-rm -fR $(BUILD_DIR)

# Flash with OpenOCD (ships with the STM32 for VS Code extension's bundles)
OPENOCD ?= openocd

ELF := $(BUILD_DIR)/$(TARGET).elf
flash: $(ELF)
	$(OPENOCD) -f interface/stlink.cfg -f target/stm32f0x.cfg \
		-c "program $< verify reset exit"

.PHONY: all flash clean

# Dependencies
-include $(wildcard $(BUILD_DIR)/*.d)
