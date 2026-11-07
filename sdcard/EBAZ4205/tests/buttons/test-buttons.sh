#!/bin/sh
# EBAZ4205 Developer SD: SW2/SW3 GPIO input demo.
# EBAZ4205 stock NAND Linux 4.6; root user; no FPGA or NAND changes.
# Physical SW2=MIO20=GPIO926, SW3=MIO32=GPIO938 (gpiochip base 906).
# Only GPIO export/unexport and read; never changes direction or value.

set -u
GPIO_ROOT=${EBAZ_GPIO_ROOT:-/sys/class/gpio}
GPIO_SW2=926
GPIO_SW3=938
own_sw2=0
own_sw3=0

cleanup() {
    if [ "$own_sw3" = 1 ]; then
        printf '%s\n' "$GPIO_SW3" > "$GPIO_ROOT/unexport" 2>/dev/null || :
    fi
    if [ "$own_sw2" = 1 ]; then
        printf '%s\n' "$GPIO_SW2" > "$GPIO_ROOT/unexport" 2>/dev/null || :
    fi
}
trap 'cleanup' 0
trap 'exit 130' 2
trap 'exit 143' 15

prepare() {
    number=$1
    if [ ! -d "$GPIO_ROOT/gpio$number" ]; then
        if ! printf '%s\n' "$number" > "$GPIO_ROOT/export"; then
            echo "ERROR: GPIO$number cannot be exported" >&2
            return 1
        fi
        if [ "$number" = "$GPIO_SW2" ]; then own_sw2=1; else own_sw3=1; fi
    fi
    if [ ! -r "$GPIO_ROOT/gpio$number/direction" ]; then
        echo "ERROR: GPIO$number has no readable direction" >&2
        return 1
    fi
    IFS= read -r direction < "$GPIO_ROOT/gpio$number/direction" || return 1
    if [ "$direction" != in ]; then
        echo "SAFETY STOP: GPIO$number is not an input (direction=$direction)" >&2
        return 1
    fi
    if [ ! -r "$GPIO_ROOT/gpio$number/value" ]; then
        echo "ERROR: GPIO$number value is unavailable" >&2
        return 1
    fi
}

if [ ! -r "$GPIO_ROOT/gpiochip906/base" ]; then
    echo "SAFETY STOP: expected gpiochip906 not found" >&2
    exit 1
fi
IFS= read -r base < "$GPIO_ROOT/gpiochip906/base" || exit 1
if [ "$base" != 906 ]; then
    echo "SAFETY STOP: unexpected GPIO base $base" >&2
    exit 1
fi
if ! sleep 0.1 2>/dev/null; then
    echo "ERROR: this BusyBox sleep does not support fractional seconds" >&2
    exit 1
fi

prepare "$GPIO_SW2" || exit 1
prepare "$GPIO_SW3" || exit 1
IFS= read -r stable2 < "$GPIO_ROOT/gpio$GPIO_SW2/value" || exit 1
IFS= read -r stable3 < "$GPIO_ROOT/gpio$GPIO_SW3/value" || exit 1
case "$stable2:$stable3" in
    0:0|0:1|1:0|1:1) ;;
    *) echo 'ERROR: unexpected initial GPIO values' >&2; exit 1 ;;
esac
cand2=$stable2
cand3=$stable3
count2=0
count3=0

echo 'Ожидание нажатий SW2 и SW3. Для выхода нажмите Ctrl+C.'
while :; do
    IFS= read -r value2 < "$GPIO_ROOT/gpio$GPIO_SW2/value" || exit 1
    IFS= read -r value3 < "$GPIO_ROOT/gpio$GPIO_SW3/value" || exit 1
    case "$value2:$value3" in
        0:0|0:1|1:0|1:1) ;;
        *) echo 'ERROR: GPIO input read failed' >&2; exit 1 ;;
    esac

    if [ "$value2" = "$cand2" ]; then
        if [ "$count2" -lt 3 ]; then count2=$((count2+1)); fi
    else
        cand2=$value2
        count2=1
    fi
    if [ "$count2" -ge 3 ] && [ "$stable2" != "$cand2" ]; then
        stable2=$cand2
        if [ "$stable2" = 0 ]; then echo 'Нажата кнопка SW2'; fi
    fi

    if [ "$value3" = "$cand3" ]; then
        if [ "$count3" -lt 3 ]; then count3=$((count3+1)); fi
    else
        cand3=$value3
        count3=1
    fi
    if [ "$count3" -ge 3 ] && [ "$stable3" != "$cand3" ]; then
        stable3=$cand3
        if [ "$stable3" = 0 ]; then echo 'Нажата кнопка SW3'; fi
    fi

    sleep 0.1
done
