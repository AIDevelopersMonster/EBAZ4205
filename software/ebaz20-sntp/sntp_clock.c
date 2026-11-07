#define _POSIX_C_SOURCE 200809L
#include <arpa/inet.h>
#include <errno.h>
#include <inttypes.h>
#include <netinet/in.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

/* SNTPv4 laboratory client: IPv4 numeric server, one exchange, no daemon. */
#define NTP_PORT 123
#define NTP_PACKET_LEN 48
#define NTP_UNIX_EPOCH UINT64_C(2208988800)
/* The target is 32-bit ARM; stay clear of its 2038 time_t limit. */
#define MIN_UNIX_TIME INT64_C(1704067200) /* 2024-01-01 UTC */
#define MAX_UNIX_TIME INT64_C(2145916800) /* 2038-01-01 UTC */
#define MAX_RTT_SECONDS 3.0

static uint32_t read_u32(const unsigned char *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}

static void write_u32(unsigned char *p, uint32_t value) {
    p[0] = (unsigned char)(value >> 24);
    p[1] = (unsigned char)(value >> 16);
    p[2] = (unsigned char)(value >> 8);
    p[3] = (unsigned char)value;
}

static double monotonic_seconds(const struct timespec *ts) {
    return (double)ts->tv_sec + (double)ts->tv_nsec / 1e9;
}

static double ntp_to_unix(const unsigned char *p) {
    uint64_t secs = read_u32(p);
    /* NTP era 1 begins in 2036; only modern dates are supported. */
    if (secs < NTP_UNIX_EPOCH) {
        secs += UINT64_C(4294967296);
    }
    return (double)((int64_t)secs - (int64_t)NTP_UNIX_EPOCH) +
           (double)read_u32(p + 4) / 4294967296.0;
}

static void unix_to_ntp(unsigned char *p, const struct timespec *ts) {
    uint64_t sec = (uint64_t)((int64_t)ts->tv_sec + (int64_t)NTP_UNIX_EPOCH);
    uint64_t frac = ((uint64_t)ts->tv_nsec << 32) / UINT64_C(1000000000);
    write_u32(p, (uint32_t)sec);
    write_u32(p + 4, (uint32_t)frac);
}

static void usage(const char *prog) {
    printf("Usage: %s [--server IPv4] [--port PORT] [--apply]\n"
           "Default server: 162.159.200.1 (Cloudflare NTP), UDP/123.\n"
           "Default action: query and print UTC time; DO NOT change system clock.\n"
           "--apply: set Linux CLOCK_REALTIME after checking SNTP response.\n"
           "This is an unauthenticated lab SNTP client, not NTS/chrony.\n", prog);
}

int main(int argc, char **argv) {
    const char *server = "162.159.200.1";
    int port = NTP_PORT;
    int apply = 0;
    int fd = -1;
    int result = 1;
    unsigned char request[NTP_PACKET_LEN] = {0};
    unsigned char response[512] = {0};
    struct sockaddr_in dst;
    struct timeval timeout = {4, 0};
    struct timespec tx_wall, start_mono, end_mono;
    double server_rx, server_tx, rtt, process, estimate;

    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--help") == 0) {
            usage(argv[0]);
            return 0;
        } else if (strcmp(argv[i], "--apply") == 0) {
            apply = 1;
        } else if (strcmp(argv[i], "--server") == 0 && i + 1 < argc) {
            server = argv[++i];
        } else if (strcmp(argv[i], "--port") == 0 && i + 1 < argc) {
            char *end = NULL;
            long n;
            errno = 0;
            n = strtol(argv[++i], &end, 10);
            if (errno != 0 || end == argv[i] || *end != '\0' ||
                n < 1 || n > 65535) {
                fprintf(stderr, "Invalid UDP port.\n");
                return 2;
            }
            port = (int)n;
        } else {
            usage(argv[0]);
            return 2;
        }
    }

    memset(&dst, 0, sizeof(dst));
    dst.sin_family = AF_INET;
    dst.sin_port = htons((uint16_t)port);
    if (inet_pton(AF_INET, server, &dst.sin_addr) != 1) {
        fprintf(stderr, "Invalid IPv4 address: %s (no DNS dependency).\n", server);
        return 2;
    }

    fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (fd < 0) {
        perror("socket");
        return 1;
    }
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) < 0 ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)) < 0) {
        perror("setsockopt");
        goto done;
    }
    if (connect(fd, (struct sockaddr *)&dst, sizeof(dst)) < 0) {
        perror("connect UDP");
        goto done;
    }

    request[0] = 0x23; /* leap=0, version=4, mode=3 (client) */
    if (clock_gettime(CLOCK_REALTIME, &tx_wall) != 0 ||
        clock_gettime(CLOCK_MONOTONIC, &start_mono) != 0) {
        perror("clock_gettime");
        goto done;
    }
    /* Transmit time also acts as a request/response correlation token. */
    unix_to_ntp(request + 40, &tx_wall);
    if (send(fd, request, sizeof(request), 0) != (ssize_t)sizeof(request)) {
        perror("send");
        goto done;
    }
    ssize_t count = recv(fd, response, sizeof(response), 0);
    if (count < 0) {
        perror("recv (verify network/firewall UDP/123)");
        goto done;
    }
    if (clock_gettime(CLOCK_MONOTONIC, &end_mono) != 0) {
        perror("clock_gettime end");
        goto done;
    }

    rtt = monotonic_seconds(&end_mono) - monotonic_seconds(&start_mono);
    if (count < NTP_PACKET_LEN || rtt < 0.0 || rtt > MAX_RTT_SECONDS) {
        fprintf(stderr, "SNTP invalid response length or delay.\n");
        goto done;
    }
    unsigned mode = response[0] & 7U;
    unsigned version = (response[0] >> 3) & 7U;
    unsigned li = response[0] >> 6;
    unsigned stratum = response[1];
    if (mode != 4 || version < 3 || version > 4 || li == 3 ||
        stratum == 0 || stratum > 15 ||
        memcmp(response + 24, request + 40, 8) != 0 ||
        (read_u32(response + 40) == 0 && read_u32(response + 44) == 0)) {
        fprintf(stderr, "SNTP server response failed validation.\n");
        goto done;
    }

    server_rx = ntp_to_unix(response + 32);
    server_tx = ntp_to_unix(response + 40);
    process = server_tx - server_rx;
    if (process < -0.02 || process > rtt + 0.25) {
        fprintf(stderr, "SNTP inconsistent server timing.\n");
        goto done;
    }
    if (process < 0.0) process = 0.0; /* minor clock rounding at server */
    estimate = server_tx + (rtt - process) / 2.0;
    if (estimate < (double)MIN_UNIX_TIME ||
        estimate >= (double)MAX_UNIX_TIME) {
        fprintf(stderr, "SNTP time outside supported 2024-2037 range.\n");
        goto done;
    }

    struct timespec corrected;
    corrected.tv_sec = (time_t)estimate;
    corrected.tv_nsec = (long)((estimate - (double)corrected.tv_sec) * 1e9);
    if (corrected.tv_nsec < 0) corrected.tv_nsec = 0;
    if (corrected.tv_nsec >= 1000000000L) corrected.tv_nsec = 999999999L;
    struct tm utc;
    char formatted[64];
    if (!gmtime_r(&corrected.tv_sec, &utc) ||
        !strftime(formatted, sizeof(formatted), "%Y-%m-%d %H:%M:%S UTC", &utc)) {
        fprintf(stderr, "Cannot render timestamp.\n");
        goto done;
    }
    printf("EBAZ20_SNTP_QUERY_PASS server=%s stratum=%u rtt_ms=%.1f\n",
           server, stratum, rtt * 1000.0);
    printf("NTP estimated UTC: %s\n", formatted);

    if (apply) {
        if (clock_settime(CLOCK_REALTIME, &corrected) < 0) {
            perror("clock_settime (requires root/CAP_SYS_TIME)");
            goto done;
        }
        puts("EBAZ20_SNTP_CLOCK_SET_PASS");
    } else {
        puts("EBAZ20_SNTP_DRY_RUN_PASS (clock unchanged)");
    }
    result = 0;

done:
    if (fd >= 0) (void)close(fd);
    return result;
}
