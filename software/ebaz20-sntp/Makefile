CROSS_COMPILE ?= arm-linux-gnueabihf-
CC := $(CROSS_COMPILE)gcc
READELF := $(CROSS_COMPILE)readelf
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Wpedantic -Werror -mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard
LDFLAGS ?= -static
TARGET := build/ebaz20-sntp

.PHONY: all check clean
all: $(TARGET)

$(TARGET): sntp_clock.c
	mkdir -p build
	$(CC) $(CFLAGS) $(LDFLAGS) -o "$@" "$<"

check: $(TARGET)
	sh ./check_elf.sh "$(TARGET)" "$(READELF)"

clean:
	rm -rf build
