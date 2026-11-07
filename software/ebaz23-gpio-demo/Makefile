CROSS_COMPILE ?= arm-linux-gnueabihf-
CC := $(CROSS_COMPILE)gcc
READELF := $(CROSS_COMPILE)readelf
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Wpedantic -Werror -mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard
LDFLAGS ?= -static
TARGET := build/ebaz23-gpio-buttons

.PHONY: all check clean
all: $(TARGET)

$(TARGET): gpio_buttons.c
	mkdir -p build
	$(CC) $(CFLAGS) $(LDFLAGS) -o "$@" "$<"

check: $(TARGET)
	$(READELF) -h "$(TARGET)" | grep -q 'Machine:.*ARM'
	$(READELF) -h "$(TARGET)" | grep -q 'hard-float ABI'
	@echo EBAZ23_ARM_ELF_HEADER_CHECK_PASS

clean:
	rm -rf build
