# Context Menu Enhancement & Reorganization

## Overview
The goal of this design is to optimize the `Daemon` context menu by adding new features, re-structuring it with sub-menus to prevent visual clutter, injecting the "Kenny" persona into the action titles, and providing a robust visualization solution for checking Memory, History, and Thought logs.

## 1. Menu Architecture & Layout
We will adopt a hybrid menu structure. Frequent and high-level actions will remain at the top level, while debugging and memory-related actions will be grouped under a "Brain Ops" submenu.

**Top-Level Actions:**
- 📌 `Pin to Screen` (Checkable)
- 💤 `Force Sleep` (Checkable)
- 🔇 `Mute Voice` (Checkable)
- ⚙️ `Settings...`
- `---` (Separator)
- 🧠 `Brain Ops ▸` (Submenu)
- `---` (Separator)
- 💀 `Kill Daemon` (Replaces "Quit Daemon")

**Brain Ops Submenu:**
- `What do I remember?`
- `Show recent history`
- `View Brain Scan`
- `---` (Separator)
- ⚡ `Defibrillate (Restart)` (Replaces "Restart Brain")
- ⚠️ `Lobotomy (Wipe All Data)` (New)

## 2. Shared Data Viewer Dialog
Currently, Memory and History try to push their contents into an ephemeral 8-second speech bubble, which limits viewing to ~260 characters and ruins readability. The "View Brain Scan" option uses a dedicated `ThoughtLogDialog`. 

**Solution:**
We will refactor the existing `ThoughtLogDialog` into a more generic `DataViewerDialog` (or create a flexible subclass). This generic UI window will be re-used across all three actions:
1. **Memory Viewer:** Will load and display the full formatted key-value pairs from the `Memory` store.
2. **History Viewer:** Will load and display the full chat history.
3. **Thought Viewer:** Will continue to read from the thoughts log file and support auto-refresh if necessary.

## 3. New Functionalities Implementation
- **Force Sleep:** A new `_forced_sleep` boolean will be added to the `PetWindow` state. When toggled ON, autonomous actions (`_active_chat_timer`, `_joke_timer`, etc.) will be suppressed, and the FSM will be forced into `PetState.SLEEP`. Unchecking it wakes the pet.
- **Mute Voice:** Will toggle the text-to-speech engine. This mirrors the functionality in the `SettingsDialog` but exposes it directly on the context menu for 1-click access.
- **Lobotomy (Wipe All Data):** A destructive action. When clicked, it must show a native `QMessageBox` warning prompt. If the user confirms, it will clear the local stores (`Memory`, `History`, `DiaryStore`), clear them from Firebase if synced, and reset context hashes to effectively wipe the pet's slate clean.

## 4. Components Affected
- `src/context_menu.py`: Update the menu hierarchy, add new actions, and introduce new signals (`sleep_toggle`, `mute_toggle`, `wipe_memory`).
- `src/pet_window.py`: Wire the new signals to their respective handler methods (`_on_sleep_toggle`, `_on_mute_toggle`, `_on_lobotomy_requested`). Update `_on_recall_memory` and `_on_recall_history` to open the dialog.
- `src/thought_log_dialog.py`: Refactor to support generic content injection (History, Memory) while maintaining its Matrix-style green-on-black aesthetic.
