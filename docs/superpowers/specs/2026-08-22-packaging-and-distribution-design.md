# Packaging, Distribution & Multi-Device Shipping Specification

**Date:** 2026-08-22  
**Status:** Approved / Ultimate End Goal  
**Author:** Daemon Core Architecture  

---

## 1. Overview & Vision

The ultimate end goal for Daemon is to be effortlessly packaged, distributed, and installed on any Windows machine as a single self-contained application without requiring manual Python installation, git cloning, or command-line dependency management.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       DAEMON SHIPPING & RELEASE PIPELINE                    │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                │                                             │
   ┌────────────▼────────────┐                   ┌────────────▼────────────┐
   │    PYINSTALLER BUNDLE   │                   │    INNO SETUP INSTALLER │
   ├─────────────────────────┤                   ├─────────────────────────┤
   │ - Full Python 3.14 Venv │                   │ - Single setup .exe     │
   │ - All PyQt6 / CTYpes Lib│                   │ - Desktop / Start Menu  │
   │ - FastMCP / Uvicorn     │                   │ - "Run on Startup" flag │
   │ - Assets & Default Conf │                   │ - Uninstaller           │
   │ - Bundled FFmpeg        │                   │                         │
   └────────────┬────────────┘                   └────────────▲────────────┘
                │                                             │
                └──────────────────────┬──────────────────────┘
                                       │
                        ┌──────────────▼──────────────┐
                        │   FIRST-RUN SETUP WIZARD    │
                        ├─────────────────────────────┤
                        │ - Firebase Auth / Guest Mode│
                        │ - LLM Setup (Opencode/Local)│
                        │ - System Permissions Consent│
                        │ - Auto-Updater Check        │
                        └─────────────────────────────┘
```

---

## 2. Packaging Architecture

### 2.1 PyInstaller Specification (`daemon.spec` modernization)
- **Mode:** One-Directory (`onedir`) distribution inside installer, or single-file executable (`onefile`) portable release.
- **Embedded Bundles:**
  - `assets/` (config template, sounds, icons, emotion sprite assets).
  - `.opencode/skills/kenny/SKILL.md` (prompts and default persona definitions).
  - Bundled standalone `ffmpeg.exe` and `ffprobe.exe` (enabling pitch-shifted TTS out of the box without requiring WinGet/winget installation on target PC).
- **Hidden Imports Enforced:**
  - `src.system.*`, `src.llm.*`, `src.autonomy.*`, `src.ui.*`
  - `fastmcp`, `uvicorn`, `starlette`, `anyio`
  - `pywinauto`, `comtypes`, `pynput`, `pydub`, `edge_tts`, `pyttsx3`
  - `structlog`, `prometheus_client`, `firebase_admin`

### 2.2 Native Windows Installer (Inno Setup / NSIS)
- **Installer Executable:** `DaemonSetup-vX.Y.Z.exe`
- **Installation Directory:** `%LOCALAPPDATA%\Daemon` (allows non-administrator standard user installs).
- **Capabilities:**
  - Create Desktop Shortcut & Start Menu entry.
  - "Start with Windows" Registry entry (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`).
  - Add firewall exception rule for local port bindings (`:4097` FastMCP, `:4098` IDE WebSocket Bridge).
  - Clean uninstallation removing temporary caches while giving option to retain user memory/data.

---

## 3. First-Run Onboarding & Configuration Wizard

When launched on a fresh machine without existing `data/daemon_config.json`:
1. **Config Auto-Creation:** Automatically generate `data/daemon_config.json` from `assets/daemon_config_template.json`.
2. **Setup Wizard Dialog (`src/ui/onboarding_wizard.py`):**
   - **Step 1: Account / Cloud Sync:** Sign in with Firebase (or select "Guest / Local-Only Mode").
   - **Step 2: Brain / Provider Selection:**
     - Select **Opencode Zen / Cloud LLM** (enter API key) OR
     - Select **Local Ollama** (auto-detects local `127.0.0.1:11434` instance and installed models).
   - **Step 3: Boundaries & Consent Matrix:** Interactive toggles for Tier 1–3 permissions (animations, toasts, clipboard, window management).
3. **Hardware & PATH Validation:** Self-check for screen resolution, microphone/audio output, and hotkey availability (`Ctrl+Alt+D`).

---

## 4. Automatic Updates & Distribution

- **GitHub Releases Integration:**
  - CI/CD GitHub Action builds `DaemonSetup.exe` on tagged git commits.
  - In-app check on boot (`GET https://api.github.com/repos/.../releases/latest`).
  - Silent download and one-click update prompt in Pet context menu.
