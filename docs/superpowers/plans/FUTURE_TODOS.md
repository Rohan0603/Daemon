# Future TODOs and Security Gaps

## 0. NEXT PRIORITY: Multi-Layer Interaction Architecture (Desktop & Code)

*Design Spec:* `docs/superpowers/specs/2026-08-22-multi-layer-interaction-architecture-design.md`  
*Implementation Plan:* `docs/superpowers/plans/2026-08-22-multi-layer-interaction-architecture.md`

### 1. Windows UI Interaction
- [x] **Semantic UI Automation (UIA) Engine (`src/system/uia_navigator.py`)**:
  - Structured accessibility tree traversal (`comtypes` / `UIAutomationCore`).
  - Programmatic click/type execution via UIA control patterns (`InvokePattern`, `ValuePattern`).
  - Zero cursor movement required; resilient to layout/screen shifts.
  - MCP Tools: `uia_get_window_tree`, `uia_interact_element`.
- [x] **Agentic Computer Use / Vision Engine (`src/system/vision_controller.py`)**:
  - High-speed screen capture with coordinate grid / Set-of-Marks overlay.
  - Vision model coordinate prediction (`(x, y)` target extraction).
  - Smooth cursor movement and click simulation via PyAutoGUI/ctypes for custom canvas/game apps.
  - MCP Tools: `vision_capture_screen`, `vision_click_coordinate`.

### 2. Code & Developer Interaction
- [x] **Background File System Watcher (`src/system/fs_watcher.py`)**:
  - `watchdog` monitoring of active project workspace.
  - Debounced file-save event pipeline updating local AST and vector database caches.
  - Pre-warms context so queries have real-time code awareness without visual inspection.
- [x] **Language Server Protocol (LSP) Client (`src/system/lsp_client.py`)**:
  - Direct JSON-RPC connection to language servers (`tsserver`, `pyright`, `rust-analyzer`, `gopls`).
  - Real-time compiler diagnostics, type info, definition/reference lookup, and AST syntax trees.
  - MCP Tools: `lsp_get_diagnostics`, `lsp_get_symbol_info` (definitions and references).
- [ ] **Native IDE WebSocket Bridge (`src/system/ide_bridge.py` + VS Code Extension)**:
  - Local authenticated WebSocket server on `127.0.0.1:4098`.
  - Atomic code insertion, diff application, and automatic formatting directly in editor.
  - Real-time cursor position, active selection, and open tab synchronization.

### 3. Persisted Memory: Cloud Firestore Native Vector DB & RAG (100% Free on Spark Plan)
*Design Spec:* `docs/superpowers/specs/2026-08-22-firestore-vector-rag-memory-design.md`  
*Implementation Plan:* `docs/superpowers/plans/2026-08-22-firestore-vector-rag-memory.md`

- [ ] **Client-Side Embedding Engine (`src/memory/embedding_engine.py`)**:
  - Local embedding generation (e.g. `all-MiniLM-L6-v2` via ONNX/`fastembed` or Ollama `/api/embeddings`).
  - Completely eliminates paid Firebase Extensions (which require Blaze pay-as-you-go + Cloud Functions).
  - 384-dimensional vector embedding generation with LRU caching.
- [ ] **Firestore Native Vector Query & kNN Search (`src/firebase_crud.py`)**:
  - Store vector embeddings using Firestore's native `Vector` type on documents under `users/{uid}/pets/{pet_id}/memories`.
  - Execute `collection.find_nearest()` kNN queries directly via client SDK.
  - Quota optimization: 1 read per 100 index entries scanned + 1 read per returned result document (stays well under the 50,000 daily free read limit).
- [ ] **Semantic RAG Retrieval Pipeline (`src/memory/rag_retriever.py`)**:
  - Context-aware retrieval of top-K relevant memories and diary entries on user questions or autonomous triggers.
  - Local cosine similarity fallback on cached JSON records during offline/network failure.
  - MCP Tool: `query_semantic_memory(query, limit=5)`.
- [ ] **Legacy Memory Migration Script (`scripts/migrate_to_vector_db.py`)**:
  - Vectorizes existing `core_brain` and historical diary entries into semantic chunks with embeddings.

| Interaction Method | How It Works | Best For | Limitation |
| :--- | :--- | :--- | :--- |
| **UI Automation (UIA)** | Reads OS accessibility tree programmatically. | Navigating Windows menus, native apps, web forms. | Fails if app does not support accessibility APIs. |
| **Computer Vision** | Takes screenshots, calculates screen coordinates. | Legacy apps, complex UI dashboards, games. | Higher latency; vulnerable to screen resolution changes. |
| **File Watching** | Background process monitoring workspace changes. | Immediate context synchronization, vector DB updates. | Passive observation; cannot interact with UI components. |
| **LSP Integration** | Connects directly to language servers (`tsserver`, etc.). | Deep codebase understanding, diagnostics, refactoring. | Strictly limited to code syntax and semantics. |
| **Native IDE Extension** | WebSocket bridge to IDE extension (VS Code/JetBrains). | Atomic code insertion, diff application, editor state. | Requires installing the editor extension. |
| **Firestore Vector RAG** | Client-side embeddings + native Firestore kNN search. | Semantic memory recall, diary search, zero Cloud Functions cost. | Limited to 50k reads/day on Spark; requires client embeddings. |

## 1. Security Issues
- **Hardcoded Secrets**: data/daemon_config.json contains a hardcoded API key (sk-9f4NGpbB5V7zuOZwXhZMCKJYMbQ7wiVF7Q6LySwb6kR0mWXIjw6AVXdgvucY1OHD) and a hardcoded Firebase API key. These need to be removed from plain text.
- **Firebase Credentials**: Stored directly in the data/ folder. Even with a .env file present, secrets are embedded in the config itself. Need to move to secure secret management or environment variables.

## 2. Architecture Concerns
- **Monolithic pet_window.py**: Massive file (~2300 lines) acting as a god object. Needs decomposition (not part of the current T1-T36 plan).
- **Test Artifact Cleanup**: this_file_surely_does_not_exist_98765.json is left in the root directory.
- **Stale Files**: .daemon_diary.json, .daemon_history.json and others are scattered at the project root instead of being properly organized in data/ (partially addressed by T22, but need to ensure root cleanup).
- **seed_brain.py**: Broken token_provider kwarg.
- **.daemon_kenny.lock**: Following intended naming convention, but keep an eye on lock file management.

## 3. Performance and Storage Issues
- **codebase_map.json Size**: Taking up 121KB (addressed in T34).
- **Large Session Log**: llm_session.json is 51KB and growing.
- **Log Location**: .daemon_thoughts.log (101KB) lives in data/ but should likely move to a dedicated logs/ directory.
- **Backup Directory**: data/backups/ exists but its contents and lifecycle/purpose are unclear.

## 4. Gaps & Future Enhancements
- **Metrics Dashboard**: Prometheus metrics are integrated, but there's no visualization dashboard.
- **Offline Fallback**: No strategy exists for when Firebase becomes unavailable.
- **LLM Provider Abstraction**: Currently hardcoded to opencode-zen/deepseek with no easy abstraction for swapping providers.
- **MCP Tool Rate Limiting**: If the LLM calls read_file dozens of times in a single response, there is no protection.
- **Real-time Brain Syncing**: Brain field changes made via Firebase console or another device don't sync until the daemon restarts.
- **Onboarding Wizard**: No wizard exists for new users.
- **Config Versioning**: Config files lack versioning and migration strategies for breaking changes.
- **Accessibility**: Transparent window breaks accessibility for screen readers.
- **Multi-Monitor Support**: Pet is locked to a single display.
- **Theme Compatibility**: Bubble colors might clash with dark/light modes.
- **Plugin Sandboxing**: Plugins can import anything from the codebase without isolation.
- **Health Dashboard**: Need a more robust health dashboard beyond the minimal Thought Log dialog.
- **Backup & Restore**: Add functionality through brain export/import.
- **Discoverability**: Make the Ctrl+Alt+D shortcut more discoverable.
- **Network Resiliency**: Handle network failures when the opencode server crashes mid-session.
- **Config Validation**: Validate the daemon config file to catch corruption early.
- **SaaS Features**: Implement usage analytics and API key management for users.
- **Privacy Mode**: Disable screen reading and clipboard access during sensitive work.

## 5. Ultimate End Goal: Packaging, Distribution & Shipping (Windows Installer & Multi-Device Setup)
*Design Spec:* `docs/superpowers/specs/2026-08-22-packaging-and-distribution-design.md`  
*Implementation Plan:* `docs/superpowers/plans/2026-08-22-packaging-and-distribution.md`

- [ ] **Modernized PyInstaller Build Pipeline (`daemon.spec`)**:
  - Full packaging of all modular packages (`src.system`, `src.llm`, `src.autonomy`, `src.ui`) and dependencies (`fastmcp`, `uvicorn`, `structlog`, `prometheus_client`, `fastembed`, `comtypes`, `pywinauto`).
  - Bundle static assets (`assets/`, `.opencode/skills/kenny/SKILL.md`, audio files, icons).
  - Bundle standalone FFmpeg binaries in `bin/` so TTS pitch-shifting works on any machine with zero external dependencies.
- [ ] **First-Run Onboarding & Setup Wizard (`src/ui/onboarding_wizard.py`)**:
  - 3-step setup dialog for new users on fresh machines (Firebase Auth / Guest Mode, LLM provider selection, and Tier 1–3 consent boundaries).
- [ ] **Native Windows Installer (Inno Setup / `installer/daemon_setup.iss`)**:
  - Standalone `DaemonSetup.exe` installer for standard non-admin installs (`%LOCALAPPDATA%\Daemon`).
  - Creates Desktop & Start Menu shortcuts + optional "Start with Windows" startup toggle.
  - Clean uninstallation with option to retain user memory/data in `data/`.
- [ ] **Auto-Updater & GitHub Releases CI/CD Pipeline (`src/system/auto_updater.py`)**:
  - In-app update checker querying GitHub Releases for new versions with silent download and one-click update.
