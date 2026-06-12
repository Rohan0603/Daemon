# Navarasa Strict Expression Design

## Goal
Implement the `EmotionProfile` dataclass with a strict constraint: strip out `transform_func` and `sclera_scale_y` parameters. The body and the eyeball must remain their default shapes. All 9 Navarasa states will be expressed purely through pupil scaling/shifting, eyebrow angles, color overrides, and particle systems.

## 1. Dataclass Simplification (`src/animator.py`)
Replace the current `EmotionProfile` with a geometry-locked version:
```python
from dataclasses import dataclass
from typing import Callable, Optional
from PyQt6.QtGui import QColor

@dataclass
class EmotionProfile:
    name: str
    
    # Color & Opacity (No body shape transforms)
    color_override: Optional[str] = None
    color_hue_shift: int = 0
    opacity_func: Callable[[float], float] = lambda t: 1.0
    
    # Eyes (Sclera remains perfectly round)
    pupil_scale: float = 1.0
    pupil_shape: str = "circle"  # "circle" | "heart"
    pupil_color_override: Optional[str] = None
    pupil_offset_x: float = 0.0  # For eye rolling/shifting
    brow_angle: float = 0.0      # degrees: positive = angry furrow, negative = sad
    
    # Overlay (Border, Aura, Flash)
    overlay_kind: Optional[str] = None      
    overlay_color: Optional[str] = None
    overlay_alpha_func: Callable[[float], int] = lambda t: 255
    overlay_width: int = 2
    
    # Particles
    particle_count: int = 0
    particle_color: Optional[str] = None
    particle_spread: float = 1.0
    particle_gravity: float = 0.0
    particle_drift_x: float = 0.0 
    particle_lifetime_ticks: int = 30
    
    # Misc
    single_fire_decay_ms: int = 0
```

## 2. Navarasa Registry Matrix
Express the 9 emotions using only permitted variables:

| Emotion | Color / Opacity | Pupils | Eyebrows | Particles / Overlays |
| --- | --- | --- | --- | --- |
| **MIRTH** | Base Blue | `scale=1.0` | `angle=0` | None |
| **ANGER** | Override `#E74C3C` | `scale=0.5` | `angle=20` | Red fire particles (`count=1`). Red border. |
| **FEAR** | Override `#6B5B95` | `scale=0.3` | `angle=-10` | Purple sweat drops (`gravity=0.1`). |
| **DISGUST** | Hue-shift -30 | `offset_x=2.0` | `angle=10` | None |
| **PATHOS** | Grayscale, pulse opacity `0.6` to `0.9` | `scale=1.0` | `angle=-15` | None |
| **DEVOTION** | Override `#FF69B4` | `shape="heart"` | `angle=0` | Pink heart particles. |
| **HEROISM** | Override `#FFD700` | `color=#FFD700`, `scale=1.2` | `angle=15` | Gold aura overlay. |
| **WONDER** | Override `#FFFFFF`, glitch opacity | `scale=1.5` | `angle=0` | White screen flash. |
| **TRANQ.** | Base Blue, opacity `0.8` | `scale=0.3` | `angle=0` | 1 light-blue Zzz particle every 2000ms. |

## 3. Renderer Upgrades (`src/pet_renderer.py`)
Update `_draw_eyes` to remove `sclera_h` and enforce a perfectly round 4x4 sclera. Implement the primary expression driver: eyebrows (`brow_angle`) rotated inversely for left vs. right eye to create symmetry. Ensure the pet's body transform function no longer applies squashing/stretching for these emotions.
