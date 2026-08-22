# Multi-Layer Interaction Architecture Implementation Plan

> **Goal:** Implement a comprehensive multi-layer interaction subsystem in Daemon across two key operational domains:
> 1. **Windows UI Navigation:** Semantic UI Automation (UIA) tree inspection and programmatic control + Computer Vision agentic fallback.
> 2. **Code & Developer Integration:** Background file watching with vector/AST cache pre-warming + Language Server Protocol (LSP) client bridge + Native IDE WebSocket extension bridge.

---

## High-Level Architecture

```
                                  ┌───────────────────────────┐
                                  │      PetWindow / MCP      │
                                  └─────────────┬─────────────┘
                                                │
                 ┌──────────────────────────────┴──────────────────────────────┐
                 │                                                             │
        ┌────────▼────────┐                                           ┌────────▼────────┐
        │   Windows UI    │                                           │ Code Interaction│
        │   Subsystem     │                                           │    Subsystem    │
        └────────┬────────┘                                           └────────┬────────┘
                 │                                                             │
        ┌────────┴────────┐                                           ┌────────┴────────────────────┐
        │                 │                                           │              │              │
┌───────▼───────┐ ┌───────▼───────┐                           ┌───────▼───────┐┌─────▼──────┐┌──────▼───────┐
│ UIA Navigator │ │ Vision Engine │                           │  FS Watcher   ││ LSP Client ││ IDE Bridge WS│
│ (Semantic DOM)│ │ (CV & Coords) │                           │(Context Cache)││(Diagnostics││ (VS Code Ext)│
└───────────────┘ └───────────────┘                           └───────────────┘└────────────┘└──────────────┘
```

---

## Detailed Task Breakdown

### Phase 1: Semantic Windows UI Automation (UIA) Engine
- [ ] **Task 1.1:** Create `src/system/uia_navigator.py` implementing `UIANavigator` with COM apartment-safe tree traversal.
- [ ] **Task 1.2:** Add `dump_tree(window_handle, max_depth=3)` returning clean, filtered JSON with control types, names, automation IDs, and bounding rects.
- [ ] **Task 1.3:** Add `invoke_control(automation_id_or_name, action)` supporting `InvokePattern`, `ValuePattern` (typing), and `ExpandCollapsePattern`.
- [ ] **Task 1.4:** Register MCP tools: `uia_get_window_tree`, `uia_interact_element`.
- [ ] **Task 1.5:** Write unit tests in `tests/test_uia_navigator.py`.

### Phase 2: Computer Vision & Agentic Fallback Subsystem
- [ ] **Task 2.1:** Create `src/system/vision_controller.py` with multi-monitor / DPI-aware screen capture via Pillow `ImageGrab`.
- [ ] **Task 2.2:** Implement coordinate grid overlay generation and Set-of-Marks (SoM) label bounding.
- [ ] **Task 2.3:** Add PyAutoGUI / ctypes `SendInput` smooth cursor navigation and click simulation with safety bounds.
- [ ] **Task 2.4:** Register MCP tools: `vision_capture_screen`, `vision_click_coordinate`.
- [ ] **Task 2.5:** Write unit tests in `tests/test_vision_controller.py`.

### Phase 3: Project Workspace File System Watcher
- [ ] **Task 3.1:** Create `src/system/fs_watcher.py` using `watchdog` to monitor project directories.
- [ ] **Task 3.2:** Implement debounce logic (500ms) for atomic file modifications to prevent churn.
- [ ] **Task 3.3:** Connect file modification signals to update the local codebase AST and vector context cache.
- [ ] **Task 3.4:** Write unit tests in `tests/test_fs_watcher.py`.

### Phase 4: Language Server Protocol (LSP) Client Integration
- [ ] **Task 4.1:** Create `src/system/lsp_client.py` with JSON-RPC stdio transport for LSP servers (`pyright`, `tsserver`, `rust-analyzer`).
- [ ] **Task 4.2:** Implement LSP initialization handshake and document synchronization protocol (`textDocument/didOpen`, `textDocument/didChange`).
- [ ] **Task 4.3:** Implement query methods: `get_diagnostics()`, `goto_definition(file, line, col)`, `find_references(file, line, col)`.
- [ ] **Task 4.4:** Register MCP tools: `lsp_get_diagnostics`, `lsp_get_symbol_info`.
- [ ] **Task 4.5:** Write unit tests in `tests/test_lsp_client.py`.

### Phase 5: Native IDE WebSocket Extension Bridge
- [ ] **Task 5.1:** Create `src/system/ide_bridge.py` running an authenticated local WebSocket server on `127.0.0.1:4098`.
- [ ] **Task 5.2:** Define bidirectional JSON protocol: `INSERT_CODE`, `REPLACE_SELECTION`, `GET_ACTIVE_CONTEXT`, `FORMAT_DOCUMENT`.
- [ ] **Task 5.3:** Build minimal VS Code extension in `extensions/vscode-daemon/` connecting to `ws://127.0.0.1:4098`.
- [ ] **Task 5.4:** Wire IDE Bridge context directly into `ContextManager` and `BehaviorController`.
- [ ] **Task 5.5:** Write unit tests in `tests/test_ide_bridge.py`.
