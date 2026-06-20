# Future TODOs and Security Gaps

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
- **Auto-Update**: Mechanism for auto-updating if distributing as an executable.
