/* SPDX-License-Identifier: GPL-3.0-or-later */

#include <stdbool.h>
#include <stdint.h>

#include "platform.h"
#include "drivers/external_watchdog.h"
#include "drivers/io.h"
#include "drivers/time.h"

// STWD100 WDI is refreshed by either edge. PA8 must never be used for LED/PWM.
static IO_t watchdogIo;
static timeMs_t startupStartedAt;
static volatile timeMs_t lastToggleAt;
static volatile bool startupActive;

static void serviceWatchdog(timeMs_t now)
{
    if ((timeMs_t)(now - lastToggleAt) >= EXTERNAL_WATCHDOG_INTERVAL_MS) {
        IOToggle(watchdogIo);
        lastToggleAt = now;
    }
}

void externalWatchdogInit(void)
{
    startupActive = false;
    watchdogIo = IOGetByTag(IO_TAG(EXTERNAL_WATCHDOG_PIN));
    IOInit(watchdogIo, OWNER_SYSTEM, RESOURCE_OUTPUT, 0);
    IOLo(watchdogIo);
    IOConfigGPIO(watchdogIo, IOCFG_OUT_PP);
    startupStartedAt = lastToggleAt = millis();
    startupActive = true;
}

void externalWatchdogStartupTick(void)
{
    if (!startupActive) {
        return;
    }

    const timeMs_t now = millis();
    if ((timeMs_t)(now - startupStartedAt) >= EXTERNAL_WATCHDOG_STARTUP_MS) {
        // Do not hide a hung initializer indefinitely, even if SysTick still runs.
        startupActive = false;
        return;
    }
    serviceWatchdog(now);
}

void externalWatchdogPoll(void)
{
    if (!watchdogIo) {
        return;
    }
    // Once foreground execution starts, interrupts must not keep a hung loop alive.
    startupActive = false;
    serviceWatchdog(millis());
}
