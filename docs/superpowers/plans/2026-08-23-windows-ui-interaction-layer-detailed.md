# Windows UI Interaction Layer — Detailed Implementation Plan

**Date:** 2026-08-23  
**Status:** Planning Phase  
**Priority:** 🚀 Immediate Top Priority (Item 1 in project-dev-memory.md)

---

## 1. Overview

This plan covers the **Windows UI Interaction Layer** — the first major component of the Multi-Layer Interaction Architecture. It consists of two complementary subsystems:

| Subsystem | File | Purpose |
|-----------|------|---------|
| **Semantic UIA Tree Engine** | `src/system/uia_navigator.py` | Fast, deterministic Windows UI Automation tree inspection and programmatic control (zero cursor movement) |
| **Agentic Computer Vision Engine** | `src/system/vision_controller.py` | Fallback for custom canvas apps — screenshot capture, Set-of-Marks overlay, vision-LLM coordinate targeting, smooth cursor actions |

Both subsystems will be exposed as **MCP tools** on the existing in-process JSON-RPC 2.0 server (port 4097).

---

## 2. Architecture Integration

### 2.1 Package Structure

```
src/
├── system/
│   ├── __init__.py
│   ├── uia_navigator.py        # NEW — Semantic UIA Tree Engine
│   ├── vision_controller.py    # NEW — Computer Vision Fallback
│   ├── screen_reader.py        # EXISTING — UIA text extraction (reference)
│   ├── active_window.py        # EXISTING — Window detection (reference)
│   └── ...
├── mcp_server.py               # EXISTING — Tool registration point
└── ...
```

### 2.2 Import Boundary Compliance

Per AGENTS.md canonical import direction: **`system` must NOT import `ui` or `llm`**

- `uia_navigator.py` and `vision_controller.py` are pure `system` modules
- They will be imported by `mcp_server.py` (root level) for tool registration
- No reverse dependencies allowed

### 2.3 Threading Model

| Component | Thread | Communication |
|-----------|--------|---------------|
| UIANavigator | Main thread (MCP handler thread) | Direct function calls via MCP |
| VisionController | Main thread (MCP handler thread) | Direct function calls via MCP |
| Screen capture | Background thread (optional) | QThread if needed for performance |

---

## 3. Semantic UIA Tree Engine (`src/system/uia_navigator.py`)

### 3.1 Design Requirements

| Requirement | Detail |
|-------------|--------|
| **COM Safety** | Thread-local `IUIAutomation` initialization (mirror `screen_reader.py:_get_uia_automation`) |
| **Tree Serialization** | Clean JSON output: control type, name, automation_id, bounding rect, supported patterns, children |
| **Depth Control** | Configurable max_depth (default 3) to avoid massive trees |
| **Pattern Invocation** | `InvokePattern` (click), `ValuePattern` (type), `ExpandCollapsePattern`, `ScrollPattern` |
| **Element Resolution** | By `automation_id`, `name`, or XPath-like query selector |
| **Error Handling** | Graceful degradation — return partial tree + error info, never crash |
| **Performance** | Target <200ms for tree dump, <50ms for single element invocation |

### 3.2 Public API

```python
class UIANavigator:
    """Windows UI Automation navigator for semantic UI interaction."""
    
    def __init__(self, max_depth: int = 3):
        """Initialize navigator with tree depth limit."""
    
    def dump_tree(self, window_handle: int = None, max_depth: int = None) -> dict:
        """
        Dump the UIA element tree for a window.
        
        Args:
            window_handle: HWND (int). Default: foreground window.
            max_depth: Override instance max_depth.
            
        Returns:
            {
                "window_handle": int,
                "window_title": str,
                "tree": [...],  # Serialized element nodes
                "truncated": bool,
                "error": str | None
            }
        """
    
    def find_element(self, window_handle: int, query: dict) -> dict | None:
        """
        Find element by query dict.
        
        Query keys: automation_id, name, control_type, class_name, xpath
        Returns element info dict or None.
        """
    
    def invoke_element(self, window_handle: int, query: dict, action: str) -> dict:
        """
        Invoke action on element.
        
        Actions: "click", "type", "expand", "collapse", "scroll", "select"
        Returns: {"success": bool, "result": str, "error": str | None}
        """
    
    def get_element_patterns(self, window_handle: int, query: dict) -> list[str]:
        """Return list of supported pattern names for element."""
```

### 3.3 Element Serialization Format

```json
{
  "automation_id": "btnOK",
  "name": "OK",
  "control_type": "Button",
  "control_type_id": 50000,
  "class_name": "Button",
  "bounding_rect": {"left": 100, "top": 200, "right": 180, "bottom": 240},
  "is_offscreen": false,
  "patterns": ["Invoke", "LegacyIAccessible"],
  "children": [...]
}
```

### 3.4 Implementation Steps

| Task | Description | Effort |
|------|-------------|--------|
| 3.4.1 | Create `UIANavigator` class with COM-safe initialization | Medium |
| 3.4.2 | Implement `dump_tree()` with depth-limited DFS walk | Medium |
| 3.4.3 | Implement element query resolver (automation_id, name, control_type, xpath) | Medium |
| 3.4.4 | Implement pattern invokers: Invoke, Value, ExpandCollapse, Scroll | High |
| 3.4.5 | Add error handling and partial-result returns | Low |
| 3.4.6 | Write unit tests in `tests/test_uia_navigator.py` | Medium |

### 3.5 Dependencies

- `comtypes` (already in project)
- `UIAutomationCore.dll` (Windows built-in)
- No new external dependencies

---

## 4. Agentic Computer Vision Engine (`src/system/vision_controller.py`)

### 4.1 Design Requirements

| Requirement | Detail |
|-------------|--------|
| **Screen Capture** | Multi-monitor aware, DPI-aware via Pillow `ImageGrab` or `dxcam` (high-performance) |
| **Coordinate Grid Overlay** | Optional grid lines with coordinate labels for vision LLM reference |
| **Set-of-Marks (SoM)** | Bounding box labels on detected UI elements (requires object detection or UIA hybrid) |
| **Cursor Control** | Smooth movement via `PyAutoGUI` + Win32 `SendInput` for precision |
| **Safety Bounds** | Clamp coordinates to screen bounds; optional "dead zone" around pet window |
| **Async Support** | Non-blocking capture for potential background use |
| **Vision LLM Integration** | Returns image + metadata for LLM consumption; LLM returns (x, y) targets |

### 4.2 Public API

```python
class VisionController:
    """Agentic computer vision fallback for non-UIA applications."""
    
    def __init__(self, enable_grid: bool = True, grid_spacing: int = 100):
        """Initialize vision controller."""
    
    def capture_screen(self, region: tuple[int, int, int, int] = None, 
                       add_grid: bool = True, add_som: bool = False) -> dict:
        """
        Capture screen region with optional overlays.
        
        Args:
            region: (left, top, right, bottom) in logical pixels. Default: full virtual screen.
            add_grid: Overlay coordinate grid.
            add_som: Overlay Set-of-Marks labels (requires element detection).
            
        Returns:
            {
                "image_base64": str,           # PNG base64
                "image_path": str | None,      # Temp file path if saved
                "region": (l, t, r, b),
                "grid_overlay": bool,
                "som_overlay": bool,
                "som_elements": [...],         # If SoM enabled
                "dpi_scale": float,
                "monitor_info": [...]
            }
        """
    
    def click_coordinate(self, x: int, y: int, click_type: str = "left",
                         smooth: bool = True, duration: float = 0.3) -> dict:
        """
        Move cursor and click at screen coordinates.
        
        Args:
            x, y: Logical screen coordinates.
            click_type: "left", "right", "double", "middle"
            smooth: Use smooth Bezier curve movement.
            duration: Movement duration in seconds.
            
        Returns: {"success": bool, "error": str | None}
        """
    
    def type_text(self, text: str, interval: float = 0.01) -> dict:
        """Type text at current cursor position."""
    
    def get_monitor_layout(self) -> list[dict]:
        """Return list of monitors with bounds and DPI scale."""
```

### 4.3 Coordinate System

- All coordinates are **logical pixels** (matching PyQt6/QCursor behavior on Windows)
- DPI scaling handled automatically via `ctypes.windll.shcore.GetScaleFactorForMonitor`
- Multi-monitor virtual screen coordinates supported

### 4.4 Implementation Steps

| Task | Description | Effort |
|------|-------------|--------|
| 4.4.1 | Create `VisionController` class with screen capture via `ImageGrab` | Medium |
| 4.4.2 | Implement coordinate grid overlay generation (PIL drawing) | Low |
| 4.4.3 | Implement Set-of-Marks element detection (hybrid: UIA + OCR fallback) | High |
| 4.4.4 | Implement smooth cursor movement via `SendInput` (ctypes) | Medium |
| 4.4.5 | Add safety bounds and pet-window exclusion zone | Low |
| 4.4.6 | Write unit tests in `tests/test_vision_controller.py` | Medium |

### 4.5 Dependencies

| Package | Purpose | Status |
|---------|---------|--------|
| `Pillow` | Screen capture, image overlay | Already in project |
| `PyAutoGUI` | Cross-platform cursor control (fallback) | Need to add |
| `dxcam` (optional) | High-speed screen capture via Desktop Duplication API | Optional optimization |
| `opencv-python` (optional) | SoM element detection | Optional |

---

## 5. MCP Tool Registration

### 5.1 New Tools to Add

| Tool | Module | Consent Key | Description |
|------|--------|-------------|-------------|
| `uia_get_window_tree` | `uia_navigator` | (read-only) | Dump UIA element tree for active/foreground window |
| `uia_interact_element` | `uia_navigator` | `allow_window_management` | Click, type, expand, scroll on UIA element |
| `vision_capture_screen` | `vision_controller` | `allow_window_management` | Capture screen with grid/SoM overlay |
| `vision_click_coordinate` | `vision_controller` | `allow_mouse_interference` | Move cursor and click at coordinates |

### 5.2 Consent Mapping Updates

Add to `CONSENT_TOOL_MAP` in `mcp_server.py`:

```python
CONSENT_TOOL_MAP = {
    # ... existing ...
    "uia_get_window_tree": None,           # Read-only, always allowed
    "uia_interact_element": "allow_window_management",
    "vision_capture_screen": "allow_window_management",
    "vision_click_coordinate": "allow_mouse_interference",
}
```

### 5.3 Tool Signatures

```python
# uia_get_window_tree
def uia_get_window_tree(window_handle: int = None, max_depth: int = 3) -> dict:
    """Dump the UIA element tree for a window."""

# uia_interact_element
def uia_interact_element(query: dict, action: str, text: str = None) -> dict:
    """
    Interact with a UIA element.
    query: {"automation_id": "...", "name": "...", "control_type": "..."}
    action: "click" | "type" | "expand" | "collapse" | "scroll"
    text: Text to type (required for "type" action)
    """

# vision_capture_screen
def vision_capture_screen(region: list[int] = None, add_grid: bool = True, 
                          add_som: bool = False) -> dict:
    """Capture screen with optional coordinate grid and Set-of-Marks overlay."""

# vision_click_coordinate
def vision_click_coordinate(x: int, y: int, click_type: str = "left", 
                            smooth: bool = True, duration: float = 0.3) -> dict:
    """Click at screen coordinates with optional smooth movement."""
```

---

## 6. Configuration

### 6.1 New Config Keys (in `data/daemon_config.json`)

```json
{
  "uia": {
    "max_tree_depth": 3,
    "cache_ttl_seconds": 2.0
  },
  "vision": {
    "default_grid_spacing": 100,
    "enable_som": false,
    "cursor_speed": 0.3,
    "safety_margin_px": 10
  }
}
```

### 6.2 Config Defaults (in `constants.py`)

```python
# UIA
UIA_MAX_TREE_DEPTH = 3
UIA_CACHE_TTL_SECONDS = 2.0

# Vision
VISION_DEFAULT_GRID_SPACING = 100
VISION_ENABLE_SOM = False
VISION_CURSOR_SPEED = 0.3
VISION_SAFETY_MARGIN_PX = 10
```

---

## 7. Testing Strategy

### 7.1 Unit Tests

| Test File | Coverage |
|-----------|----------|
| `tests/test_uia_navigator.py` | Tree dump, element query, pattern invocation, error cases |
| `tests/test_vision_controller.py` | Screen capture, grid overlay, cursor movement, coordinate clamping |

### 7.2 Test Fixtures

- Use `mock_background_workers` fixture to prevent real threads
- Mock `comtypes` UIA for deterministic UIA tests
- Mock `PIL.ImageGrab` for vision tests
- Mock `ctypes.windll.user32.SendInput` for cursor tests

### 7.3 Integration Tests

- `tests/test_mcp_uia_tools.py` — MCP tool registration and consent gating
- `tests/test_mcp_vision_tools.py` — MCP tool registration and consent gating

---

## 8. Implementation Sequence

### Phase 1: UIA Navigator (Week 1)
1. Create `src/system/uia_navigator.py` with `UIANavigator` class
2. Implement `dump_tree()` with JSON serialization
3. Implement element query resolver
4. Implement pattern invokers (Invoke, Value, ExpandCollapse, Scroll)
4. Add to `mcp_server.py`: tool registration + consent mapping
5. Write unit tests

### Phase 2: Vision Controller (Week 2)
1. Create `src/system/vision_controller.py` with `VisionController` class
2. Implement screen capture with `ImageGrab`
3. Implement coordinate grid overlay
4. Implement `click_coordinate()` with smooth `SendInput` movement
5. Add SoM overlay (basic version: UIA-detected elements)
6. Add to `mcp_server.py`: tool registration + consent mapping
7. Write unit tests

### Phase 3: Integration & Polish (Week 3)
1. Add configuration keys to `constants.py` and `daemon_config.json`
2. Integration test with live MCP server
3. Performance benchmarking (<200ms tree dump, <50ms click)
4. Documentation updates

---

## 9. Risk Assessment & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| UIA COM initialization fails on some threads | Medium | High | Use thread-local pattern from `screen_reader.py`; graceful fallback |
| Large UIA trees cause memory/latency issues | Medium | Medium | Configurable depth limit; truncated flag in response |
| `dxcam` not available on all Windows versions | Low | Low | Fallback to Pillow `ImageGrab` (slower but universal) |
| Multi-monitor DPI scaling breaks coordinates | Medium | High | Use `GetScaleFactorForMonitor`; test on 125%/150%/200% DPI |
| Vision LLM coordinate targeting inaccurate | Medium | Medium | SoM overlay improves accuracy; configurable grid density |
| Consent gating blocks legitimate automation | Low | Medium | Clear error messages; log blocked attempts with context |

---

## 10. Success Criteria

- [ ] `uia_get_window_tree` returns valid JSON tree for Notepad/VS Code/Explorer in <200ms
- [ ] `uia_interact_element` can click a button and type in an edit control
- [ ] `vision_capture_screen` returns base64 PNG with grid overlay
- [ ] `vision_click_coordinate` moves cursor smoothly and clicks accurately
- [ ] All unit tests pass with `mock_background_workers` fixture
- [ ] Full test suite stays under 50s
- [ ] No import boundary violations (graphify check passes)

---

## 11. Files to Create/Modify

### New Files
- `src/system/uia_navigator.py`
- `src/system/vision_controller.py`
- `tests/test_uia_navigator.py`
- `tests/test_vision_controller.py`
- `tests/test_mcp_uia_tools.py`
- `tests/test_mcp_vision_tools.py`

### Modified Files
- `src/mcp_server.py` — Tool registration, `CONSENT_TOOL_MAP`, config extraction
- `src/constants.py` — New config constants
- `data/daemon_config.json` — Default config values
- `assets/daemon_config_template.json` — Template for new users

---

## 12. References

- [Design Spec: Multi-Layer Interaction Architecture](../specs/2026-08-22-multi-layer-interaction-architecture-design.md)
- [High-Level Implementation Plan](2026-08-22-multi-layer-interaction-architecture.md)
- [screen_reader.py](../../src/system/screen_reader.py) — UIA COM initialization pattern
- [active_window.py](../../src/system/active_window.py) — Window handle/rect patterns
- [click_through.py](../../src/system/click_through.py) — Win32 API patterns
- [mcp_server.py](../../src/mcp_server.py) — Tool registration pattern
- [AGENTS.md](../../AGENTS.md) — Import boundaries, testing rules, git workflow