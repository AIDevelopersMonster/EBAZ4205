// SPDX-License-Identifier: MIT
// EBAZ-23: two PS MIO buttons, sysfs GPIO reader for Linux 4.6.
// Independent implementation. Does NOT change FPGA, GPIO direction or NAND.
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define GPIO_BASE_DEFAULT 906
#define GPIO_S2_OFFSET 20
#define GPIO_S3_OFFSET 32
#define SAMPLE_NS 25000000L
#define DEBOUNCE_SAMPLES 3

static volatile sig_atomic_t interrupted = 0;

struct button {
    const char *name;
    int number;
    int fd;
    bool exported_here;
    int stable;
    int candidate;
    int streak;
    unsigned presses;
};

static void handle_signal(int signo)
{
    (void)signo;
    interrupted = 1;
}

static int sysfs_write(const char *path, const char *data)
{
    int fd = open(path, O_WRONLY | O_CLOEXEC);
    if (fd < 0)
        return -1;
    size_t len = strlen(data);
    ssize_t count = write(fd, data, len);
    int saved = errno;
    (void)close(fd);
    errno = saved;
    return count == (ssize_t)len ? 0 : -1;
}

static int gpio_control(const char *path, int number)
{
    char value[32];
    (void)snprintf(value, sizeof(value), "%d", number);
    return sysfs_write(path, value);
}

static int read_gpio(int fd)
{
    char buffer[8] = {0};
    if (lseek(fd, 0, SEEK_SET) < 0)
        return -1;
    ssize_t count = read(fd, buffer, sizeof(buffer) - 1);
    if (count <= 0)
        return -1;
    if (buffer[0] == '0') return 0;
    if (buffer[0] == '1') return 1;
    errno = EINVAL;
    return -1;
}

static void release_button(struct button *button)
{
    if (button->fd >= 0) {
        (void)close(button->fd);
        button->fd = -1;
    }
    if (button->exported_here) {
        if (gpio_control("/sys/class/gpio/unexport", button->number) != 0)
            fprintf(stderr, "WARN: cannot unexport GPIO%d: %s\n",
                    button->number, strerror(errno));
        button->exported_here = false;
    }
}

static int prepare_button(struct button *button)
{
    char path[128];
    char direction[16] = {0};

    if (gpio_control("/sys/class/gpio/export", button->number) == 0) {
        button->exported_here = true;
    } else if (errno != EBUSY) {
        fprintf(stderr, "ERROR: export GPIO%d failed: %s\n",
                button->number, strerror(errno));
        return -1;
    }

    (void)snprintf(path, sizeof(path), "/sys/class/gpio/gpio%d/direction",
                   button->number);
    int direction_fd = open(path, O_RDONLY | O_CLOEXEC);
    if (direction_fd < 0) {
        fprintf(stderr, "ERROR: cannot inspect GPIO%d direction\n", button->number);
        return -1;
    }
    ssize_t n = read(direction_fd, direction, sizeof(direction) - 1);
    (void)close(direction_fd);
    if (n < 2 || strncmp(direction, "in", 2) != 0) {
        fprintf(stderr, "SAFETY STOP: GPIO%d direction is not 'in'\n",
                button->number);
        return -1;
    }

    (void)snprintf(path, sizeof(path), "/sys/class/gpio/gpio%d/value",
                   button->number);
    button->fd = open(path, O_RDONLY | O_CLOEXEC);
    if (button->fd < 0) {
        fprintf(stderr, "ERROR: open GPIO%d value: %s\n",
                button->number, strerror(errno));
        return -1;
    }
    int first = read_gpio(button->fd);
    if (first < 0) {
        fprintf(stderr, "ERROR: initial read of GPIO%d failed\n", button->number);
        return -1;
    }
    button->stable = first;
    button->candidate = first;
    button->streak = 0;
    printf("%s GPIO%d initial=%d (active-low press expected, verify)\n",
           button->name, button->number, first);
    return 0;
}

static int poll_button(struct button *button, int *speed)
{
    int value = read_gpio(button->fd);
    if (value < 0) {
        fprintf(stderr, "ERROR: GPIO%d read: %s\n", button->number,
                strerror(errno));
        return -1;
    }
    if (value != button->candidate) {
        button->candidate = value;
        button->streak = 1;
    } else if (button->streak < DEBOUNCE_SAMPLES) {
        button->streak++;
    }
    if (button->streak >= DEBOUNCE_SAMPLES && value != button->stable) {
        button->stable = value;
        // The external project's DTS specifies ACTIVE_LOW for both buttons.
        // Raw 0 is treated as pressed, which must be verified on this board.
        if (value == 0) {
            ++button->presses;
            if (strcmp(button->name, "S2") == 0 && *speed > 0) --*speed;
            if (strcmp(button->name, "S3") == 0 && *speed < 9) ++*speed;
            printf("%s PRESSED (GPIO%d raw=0), demo-speed=%d\n",
                   button->name, button->number, *speed);
        } else {
            printf("%s RELEASED (GPIO%d raw=1)\n",
                   button->name, button->number);
        }
        fflush(stdout);
    }
    return 0;
}

static void usage(const char *program)
{
    printf("Usage: %s [--seconds 1..300] [--base N]\n", program);
    puts("Reads PS MIO20/MIO32 through Linux 4.6 GPIO sysfs.");
    puts("Exports INPUT lines only; does not toggle LEDs, NAND or FPGA.");
    puts("Default: --seconds 20 --base 906. Press S2/S3 during the run.");
}

static int parse_int(const char *text, int lower, int upper, int *target)
{
    char *end = NULL;
    errno = 0;
    long val = strtol(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || val < lower || val > upper)
        return -1;
    *target = (int)val;
    return 0;
}

int main(int argc, char **argv)
{
    int seconds = 20;
    int base = GPIO_BASE_DEFAULT;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--help") == 0) {
            usage(argv[0]);
            return 0;
        }
        if (strcmp(argv[i], "--seconds") == 0 && i + 1 < argc) {
            if (parse_int(argv[++i], 1, 300, &seconds) != 0)
                return fprintf(stderr, "Bad --seconds\n"), 2;
        } else if (strcmp(argv[i], "--base") == 0 && i + 1 < argc) {
            if (parse_int(argv[++i], 0, 100000, &base) != 0)
                return fprintf(stderr, "Bad --base\n"), 2;
        } else {
            usage(argv[0]);
            return 2;
        }
    }

    struct button buttons[2] = {
        {.name="S2", .number=base+GPIO_S2_OFFSET, .fd=-1},
        {.name="S3", .number=base+GPIO_S3_OFFSET, .fd=-1}
    };
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = handle_signal;
    (void)sigaction(SIGINT, &sa, NULL);
    (void)sigaction(SIGTERM, &sa, NULL);

    int status = 0;
    if (prepare_button(&buttons[0]) != 0 ||
        prepare_button(&buttons[1]) != 0) {
        status = 1;
        goto done;
    }

    puts("EBAZ23_GPIO_BUTTONS_READY: press S2 and S3, no outputs changed.");
    fflush(stdout);
    int speed = 5;
    const struct timespec period = {.tv_sec=0, .tv_nsec=SAMPLE_NS};
    for (int tick = 0; tick < seconds * 40 && !interrupted; ++tick) {
        for (int i = 0; i < 2; i++) {
            if (poll_button(&buttons[i], &speed) != 0) {
                status = 1;
                goto done;
            }
        }
        (void)nanosleep(&period, NULL);
    }

done:
    printf("RESULT: S2 presses=%u; S3 presses=%u; status=%s\n",
           buttons[0].presses, buttons[1].presses,
           status == 0 ? "PASS_SOFTWARE_ONLY" : "FAIL");
    release_button(&buttons[1]);
    release_button(&buttons[0]);
    return status;
}
