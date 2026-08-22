# Packaging & Multi-Device Shipping Implementation Plan

> **Goal:** Create a turnkey packaging, installer, and distribution pipeline for Daemon to easily ship and install on other Windows machines.

---

## Detailed Task Breakdown

### Phase 1: PyInstaller Build Modernization
- [ ] **Task 1.1:** Update `daemon.spec` to include all modular packages (`src.system`, `src.llm`, `src.autonomy`, `src.ui`) and new dependencies (`fastmcp`, `uvicorn`, `structlog`, `prometheus_client`, `fastembed`).
- [ ] **Task 1.2:** Bundle static assets (`assets/`, `.opencode/skills/kenny/SKILL.md`, sound clips, icons) in `Analysis.datas`.
- [ ] **Task 1.3:** Add standalone FFmpeg runtime bundling in `bin/` and update `_ensure_ffmpeg_on_path()` in `daemon.py` to prioritize the bundled binary.
- [ ] **Task 1.4:** Test clean standalone executable build on a clean environment.

### Phase 2: First-Run Onboarding Wizard
- [ ] **Task 2.1:** Implement `src/ui/onboarding_wizard.py` (3-step initial setup for Firebase Auth / Local Mode, LLM Provider selection, and Consent Matrix configuration).
- [ ] **Task 2.2:** Wire `onboarding_wizard` to trigger automatically on first boot when `daemon_config.json` is missing or unconfigured.
- [ ] **Task 2.3:** Add unit and UI tests for wizard state flow in `tests/test_onboarding_wizard.py`.

### Phase 3: Windows Installer (Inno Setup)
- [ ] **Task 3.1:** Create `installer/daemon_setup.iss` Inno Setup script.
- [ ] **Task 3.2:** Configure installation into `%LOCALAPPDATA%\Daemon` with Desktop and Start Menu shortcut generation.
- [ ] **Task 3.3:** Add checkbox for "Launch Daemon on Windows Startup" (`HKCU\...\Run`).
- [ ] **Task 3.4:** Add uninstaller logic that offers to preserve user memory and diary files in `data/`.

### Phase 4: Auto-Update & CI/CD Pipeline
- [ ] **Task 4.1:** Implement `src/system/auto_updater.py` (queries GitHub Releases API for new version tags and downloads patch installers).
- [ ] **Task 4.2:** Add "Check for Updates" action in Pet context menu.
- [ ] **Task 4.3:** Create `.github/workflows/build_release.yml` for automated PyInstaller + Inno Setup builds on release tags.
