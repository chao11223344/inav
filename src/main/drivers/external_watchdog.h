/* SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

// Init after IOInitGlobal(), before configuration storage and sensor startup.
void externalWatchdogInit(void);
// Bounded startup servicing only; called from the 1 ms SysTick interrupt.
void externalWatchdogStartupTick(void);
// Transfers servicing to the foreground. Call on every main/MSC loop iteration.
void externalWatchdogPoll(void);
