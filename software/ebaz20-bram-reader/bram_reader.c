#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#define BRAM_BASE UINT32_C(0x40000000)
#define BRAM_SIZE ((size_t)8192)
#define DEFAULT_WORDS 16UL
#define MAX_WORDS (BRAM_SIZE / sizeof(uint32_t))

static int usage(const char *program, int exit_code) {
    fprintf(exit_code ? stderr : stdout,
            "Usage: %s [--words N] [--help]\n"
            "Read-only 32-bit snapshot of EBAZ4205 AXI BRAM at 0x40000000.\n"
            "Default: 16 words; allowed range: 1..%zu words.\n"
            "No writes to memory, FPGA configuration, or NAND.\n",
            program, MAX_WORDS);
    return exit_code;
}

int main(int argc, char **argv) {
    unsigned long count = DEFAULT_WORDS;
    if (argc == 2 && strcmp(argv[1], "--help") == 0) {
        return usage(argv[0], 0);
    }
    if (argc == 3 && strcmp(argv[1], "--words") == 0) {
        char *end = NULL;
        errno = 0;
        count = strtoul(argv[2], &end, 10);
        if (errno != 0 || end == argv[2] || *end != '\0' ||
            count == 0UL || count > MAX_WORDS) {
            fprintf(stderr, "Invalid word count: %s\n", argv[2]);
            return usage(argv[0], 2);
        }
    } else if (argc != 1) {
        return usage(argv[0], 2);
    }

    const int fd = open("/dev/mem", O_RDONLY | O_CLOEXEC | O_SYNC);
    if (fd < 0) {
        perror("open /dev/mem");
        return 1;
    }

    void *mapped = mmap(NULL, BRAM_SIZE, PROT_READ, MAP_SHARED,
                        fd, (off_t)BRAM_BASE);
    if (mapped == MAP_FAILED) {
        perror("mmap AXI BRAM");
        (void)close(fd);
        return 1;
    }
    (void)close(fd);

    const volatile uint32_t * const words =
        (const volatile uint32_t *)mapped;
    printf("EBAZ20_BRAM_READ_BEGIN base=0x%08" PRIx32 " words=%lu\n",
           BRAM_BASE, count);
    for (unsigned long i = 0; i < count; ++i) {
        const uint32_t value = words[i];
        const uint32_t address = BRAM_BASE + (uint32_t)(i * 4UL);
        printf("0x%08" PRIx32 " 0x%08" PRIx32 "\n", address, value);
    }

    if (munmap(mapped, BRAM_SIZE) != 0) {
        perror("munmap AXI BRAM");
        return 1;
    }
    puts("EBAZ20_BRAM_READ_PASS");
    return 0;
}
