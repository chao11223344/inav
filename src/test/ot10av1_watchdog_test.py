#!/usr/bin/env python3
"""Run the real OT10AV1 watchdog code against a host clock/GPIO stub.

Usage: python3 src/test/ot10av1_watchdog_test.py
Requires a host C compiler (CC, default cc); no downloaded test dependencies.
"""

import os
from pathlib import Path
import shlex
import subprocess
import tempfile


MAIN = Path(__file__).resolve().parents[1] / "main"

IO_STUB = r"""
#pragma once
#include <stdbool.h>
typedef void *IO_t;
#define IO_TAG(pin) 8
#define OWNER_SYSTEM 1
#define RESOURCE_OUTPUT 2
#define IOCFG_OUT_PP 3
IO_t IOGetByTag(int tag);
void IOInit(IO_t io, int owner, int resource, int index);
void IOLo(IO_t io);
void IOConfigGPIO(IO_t io, int mode);
void IOToggle(IO_t io);
"""

TEST = r"""
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "drivers/io.h"
#include "drivers/time.h"
#include "drivers/external_watchdog.h"

static timeMs_t now;
static int pin, toggles, level, initialized, configured;
timeMs_t millis(void) { return now; }
IO_t IOGetByTag(int tag) { assert(tag == 8); return &pin; }
void IOInit(IO_t io, int owner, int resource, int index) {
    assert(io == &pin && owner == OWNER_SYSTEM && resource == RESOURCE_OUTPUT && index == 0);
    initialized = 1;
}
void IOLo(IO_t io) { assert(io == &pin && initialized); level = 0; }
void IOConfigGPIO(IO_t io, int mode) {
    assert(io == &pin && mode == IOCFG_OUT_PP && level == 0);
    configured = 1;
}
void IOToggle(IO_t io) {
    assert(io == &pin && configured);
    level = !level;
    toggles++;
}
static void reset(timeMs_t start) {
    now = start;
    toggles = initialized = configured = 0;
    level = 1;
    externalWatchdogInit();
    assert(configured && level == 0);
}
int main(void) {
    // SysTick can run before IO initialization.
    externalWatchdogStartupTick();
    externalWatchdogPoll();
    assert(toggles == 0);

    reset(0);
    for (now = 0; now < 100; now++) externalWatchdogStartupTick();
    assert(toggles == 0);
    externalWatchdogStartupTick();
    assert(toggles == 1 && level == 1);
    now = 200;
    externalWatchdogStartupTick();
    assert(toggles == 2 && level == 0);

    // Foreground handoff: interrupts alone cannot feed a hung main/MSC loop.
    now = 201;
    externalWatchdogPoll();
    for (now = 202; now < 5202; now++) externalWatchdogStartupTick();
    assert(toggles == 2);
    externalWatchdogPoll();
    assert(toggles == 3);
    externalWatchdogPoll();
    assert(toggles == 3);

    // A stuck initializer receives no more edges after the bounded grace period.
    reset(0);
    for (now = 0; now <= 31000; now++) externalWatchdogStartupTick();
    assert(toggles == 299);
    now = 100; // Even after clock wrap, expired startup servicing stays disabled.
    externalWatchdogStartupTick();
    assert(toggles == 299);

    // Unsigned millisecond wrap must not stall either startup or foreground feeding.
    reset(UINT32_MAX - 49);
    now = 49;
    externalWatchdogStartupTick();
    assert(toggles == 0);
    now = 50;
    externalWatchdogStartupTick();
    assert(toggles == 1);
    reset(UINT32_MAX - 49);
    externalWatchdogPoll();
    now = 50;
    externalWatchdogPoll();
    assert(toggles == 1);

    puts("OT10AV1 watchdog: startup, timeout, foreground stall, cadence and rollover passed");
    return 0;
}
"""


with tempfile.TemporaryDirectory(prefix="ot10-watchdog-") as directory:
    tmp = Path(directory)
    (tmp / "drivers").mkdir()
    (tmp / "platform.h").write_text(
        f'#include "{MAIN / "target/OT10AV1/target.h"}"\n'
    )
    (tmp / "drivers/io.h").write_text(IO_STUB)
    (tmp / "drivers/time.h").write_text(
        "#pragma once\n#include <stdint.h>\ntypedef uint32_t timeMs_t;\ntimeMs_t millis(void);\n"
    )
    (tmp / "test.c").write_text(TEST)
    executable = tmp / "watchdog-test"
    subprocess.run(
        shlex.split(os.environ.get("CC", "cc"))
        + ["-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(tmp), "-I", str(MAIN),
           str(MAIN / "target/OT10AV1/watchdog.c"), str(tmp / "test.c"), "-o", str(executable)],
        check=True,
    )
    subprocess.run([str(executable)], check=True)
