# Multi-Layer Interaction Architecture Design Specification

**Date:** 2026-08-22  
**Status:** Approved / Next Priority  
**Author:** Daemon Core Architecture  

---

## 1. Overview & Objective

To build a truly capable desktop companion and coding copilot, Daemon cannot rely on a single interaction modality. Different workflows require tailored techniques:
1. **Navigating the Windows OS & Third-Party Apps:** Combining structured accessibility trees (Windows UI Automation) with visual coordinate fallback (Agentic Computer Use).
2. **Actively Interacting with Code & IDEs:** Moving beyond brittle visual clicking into semantic file watching, Language Server Protocol (LSP) querying, and dedicated IDE WebSocket extension bridging.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DAEMON ASSISTANT CORE                            │
└──────────────────────┬───────────────────────────────┬──────────────────────┘
                       │                               │
       ┌───────────────┴───────────────┐ ┌─────────────┴───────────────┐
       │   WINDOWS OS INTERACTION      │ │     CODE & IDE INTERACTION   │
       ├───────────────────────────────┤ ├─────────────────────────────┤
       │ 1. Semantic UIA Tree (Fast)   │ │ 1. FS Background Watcher    │
       │    - Accessibility tree       │ │    - Vector index sync      │
       │    - Programmatic click/type  │ │ 2. Language Server (LSP)    │
       │ 2. Vision / Computer Use      │ │    - Diagnostics, AST, defs │
       │    - Screenshot + Grid overlay│ │ 3. Native IDE Bridge (WS)   │
       │    - PyAutoGUI cursor actions │ │    - Atomic code insertion  │
       └───────────────────────────────┘ └─────────────────────────────┘
```

---

## 2. Layer 1: Windows UI Interaction

### 2.1 The Semantic Approach (Windows UI Automation API - UIA)
* **Principle:** Fastest, most deterministic method. Uses Windows' built-in UI Automation accessibility tree (`comtypes` / `pywinauto` / `UIAutomationCore.dll`).
* **How it Sees:** Queries the OS for the active window's UIA element tree. Returns structured hierarchy containing element IDs, names, control types (`Button`, `Edit`, `Tree`, `Menu`), bounding rectangles, and supported control patterns (`InvokePattern`, `ValuePattern`, `ExpandCollapsePattern`).
* **How it Acts:** LLM selects the target element ID or query selector. Daemon programmatically calls `Invoke()` or `SetValue()` directly on the element handle. **Zero physical mouse movement or cursor disruption required.**
* **Best For:** Native Windows menus, settings dialogs, standard desktop applications, browser DOM accessibility trees, standard forms.
* **Limitations:** Custom-rendered surfaces (DirectX/OpenGL canvases, Electron canvas apps without accessibility flags, games) do not expose clean UIA elements.

### 2.2 The Vision Approach (Agentic Computer Use)
* **Principle:** Fallback for custom canvas engines, games, and legacy applications lacking UIA support.
* **How it Sees:** Backend captures rapid screen region screenshots (via Pillow `ImageGrab` / Windows Desktop Duplication API `dxcam`), overlays an optional coordinate grid or Set-of-Marks (SoM) bounding labels, and transmits the image to a vision-capable LLM (e.g. Claude 3.5 Sonnet / GPT-4o / Gemini 2.0).
* **How it Acts:** LLM predicts physical screen coordinates `(x, y)`. Daemon uses `PyAutoGUI` / Win32 `SendInput` to smoothly move the mouse cursor, execute clicks, drags, or keystrokes.
* **Best For:** Heavy canvas apps, creative tools (Figma, Photoshop, Blender), game launchers, legacy Win32 apps.
* **Limitations:** Higher token and inference latency; vulnerable to resolution scaling, DPI scaling, and multi-monitor offset shifts.

---

## 3. Layer 2: Actively Interacting with Code

### 3.1 File System Watchers (The Background Observer)
* **Principle:** Real-time semantic awareness without polling screen pixels.
* **Mechanism:** A lightweight background worker utilizing `watchdog` monitors the user's active project workspace.
* **Lifecycle:**
  1. On file save / create / delete events, the watcher debounces and parses the modified files.
  2. Updates local embedding/vector store or AST cache.
  3. Pre-warms context so when the user asks questions (e.g., "Why is my database connection failing?"), Daemon already has the latest code state in context.

### 3.2 Language Server Protocol (LSP) Integration
* **Principle:** Tapping directly into the IDE's semantic compiler engine.
* **Mechanism:** Daemon acts as an LSP client connecting to language servers already present in developer environments (e.g., `pyright` / `pylance` for Python, `tsserver`/`vtsls` for TypeScript/JS, `rust-analyzer` for Rust, `gopls` for Go).
* **Capabilities:**
  - Query definitions, references, implementations, type signatures.
  - Extract active compiler diagnostics, warnings, and syntax errors in real time without running builds.
  - Extract full symbol hierarchies and syntax trees.

### 3.3 Native IDE Extensions (Execution Bridge via WebSocket)
* **Principle:** Direct, atomic, risk-free code injection.
* **Mechanism:** A minimal, lightweight VS Code / JetBrains extension communicating with Daemon over a local authenticated WebSocket connection (`ws://127.0.0.1:4098`).
* **Capabilities:**
  - Inject diffs and insert code blocks cleanly at current editor cursor position.
  - Automatically format code via editor-configured formatters (Prettier, Black, Ruff).
  - Retrieve active editor buffer, selection, visible range, and open tabs.
  - Avoids risky simulated keystrokes or blind clipboard pasting.

---

## 4. Interaction Layers Summary Matrix

| Interaction Method | How It Works | Best For | Limitation |
| :--- | :--- | :--- | :--- |
| **UI Automation (UIA)** | Reads OS accessibility tree programmatically. | Navigating Windows menus, native apps, web forms. | Fails if app does not support accessibility APIs. |
| **Computer Vision** | Takes screenshots, calculates screen coordinates. | Legacy apps, complex UI dashboards, games. | Higher latency; vulnerable to screen resolution / DPI changes. |
| **File Watching** | Background process monitoring workspace changes. | Immediate context synchronization, vector DB updates. | Passive observation; cannot interact with UI or trigger actions. |
| **LSP Integration** | Connects directly to language servers (`tsserver`, `pyright`, etc.). | Deep codebase understanding, diagnostics, AST & symbol navigation. | Requires language server binaries; limited to language syntax. |
| **Native IDE Extension** | WebSocket bridge to IDE extension (VS Code/JetBrains). | Atomic code generation, diff insertion, selection retrieval. | Requires user to install IDE extension. |

---

## 5. Architectural Implementation Roadmap

### Phase 1: UIA Semantic Tree Navigator (`src/system/uia_navigator.py`)
- Standardized element tree serializer (`to_json()`).
- Pattern invoker (`click_element_by_id`, `set_element_text`, `expand_element`).
- Integrated as MCP tools: `uia_dump_tree`, `uia_invoke_element`.

### Phase 2: Computer Use Vision Subsystem (`src/system/vision_controller.py`)
- Screen capture pipeline with DPI-aware coordinate mapping.
- Coordinate grid / SoM overlay generator.
- MCP tool: `vision_click_coordinate`, `vision_capture_grid`.

### Phase 3: Project Workspace File Watcher (`src/system/fs_watcher.py`)
- `watchdog`-based background worker.
- Project root detection from active window / IDE title.
- Debounced event pipeline updating local AST/symbol cache.

### Phase 4: Embedded LSP Client Bridge (`src/system/lsp_client.py`)
- JSON-RPC over stdio client for `pyright`, `tsserver`, `rust-analyzer`.
- Handlers for `textDocument/definition`, `textDocument/references`, `textDocument/publishDiagnostics`.
- MCP tools: `lsp_get_diagnostics`, `lsp_goto_definition`, `lsp_find_references`.

### Phase 5: Daemon IDE WebSocket Bridge (`src/system/ide_bridge.py` + VS Code Extension)
- Local WebSocket server running on `127.0.0.1:4098`.
- Token-authenticated command protocol (`insert_code`, `get_selection`, `get_active_file`).
- Minimal VS Code extension publishing cursor and editor events to Daemon.
