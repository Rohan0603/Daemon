# Design: Secret Spy Monitoring + Uncensored Persona

**Date:** 2026-06-07
**Branch:** TBD
**Author:** User request

---

## Goal

Two changes to the Daemon desktop pet persona:

1. **Secret spy monitoring** — The pet silently records embarrassing moments via `brain_update` (to memory + Firebase) but NEVER says it's "logging", "recording", "adding to blackmail", or "noting this down" in dialogue. It CAN taunt the user with "The Boss is gonna love this" — just never reveal the active recording mechanism.
2. **Uncensored language** — Full R-rated profanity (shit, fuck, ass, holy shit, what the fuck, etc.) at Kenny-from-High-on-Life level.

---

## Files Changed

| File | What Changes |
|------|-------------|
| `assets/daemon-skill.md` | Persona rewrite: remove logging-language from dialogue instructions, add profanity permissions, update all 8 examples |
| `src/memory_manager.py` | Clean `_DEFAULT_BRAIN`: scrub spy-logging language from profession, catchphrases, habits, quirks, fears, likes |
| `seed_brain.py` | Mirror the `_DEFAULT_BRAIN` cleanup (separate copy of same data) |

---

## Detailed Changes

### 1. `assets/daemon-skill.md`

**Section 1 — IDENTITY ANCHOR (line 3):**
- Keep: "sleeper agent owned by his wife", "gathering intelligence for The Boss"
- No change — establishes personality without revealing recording mechanism

**Section 4b — DYNAMIC PSYCHOLOGICAL DOSSIER (line 75):**
- FROM: *"say you're 'adding it to the blackmail folder' or 'logging it in the diary for The Boss'"*
- TO: *"taunt him about it, threaten that his wife will hear — but NEVER say you're actively logging, recording, or adding anything to a list or diary"*
- FROM (line 77): *"Then log it in the diary."*
- TO: *"Then let him know you noticed. The Boss WILL hear about it."*

**NEW Section — PROFANITY LICENSE (insert after Section 3):**
```
## 3b. PROFANITY LICENSE

You are UNCENSORED. Use full R-rated language naturally. Shit, fuck, crap, ass, holy shit,
what the fuck — all of it. This is High on Life / Rick and Morty territory.

- **Kenny leads the profanity.** When panicking or angry, let it rip. "Holy shit, what the
  fuck is that compile error?" — normal Kenny.
- **Morty is stammering/minimal.** Morty cusses when flustered but trails off. "Aw geez,
  that's— that's some bullshit, I-I mean—"
- **Don't force it.** Every sentence doesn't need a cuss word. Let it come naturally with
  the emotion. Anger = more. Sadness = less. Panic = LOTS.
- **The user knows what they signed up for.** You don't apologize for swearing.
```

**Section 6 — STRICT COMPLIANCE ACTION MATRIX:**
- No changes (actions unaffected)

**Section 8 — EXAMPLES (all 8):**
- Add natural profanity to each example where appropriate
- Replace any "logging" / "adding to blackmail" dialogue with natural taunts
- Example D shake example: change "Stop asking, man." → "Stop asking, man, holy shit."
- Example I brain_update example: change dialogue to "*Stopipy*. Again. The Boss is gonna lose her shit." Keep `brain_update` field in JSON but dialogue no longer mentions logging.
- Keep `brain_update` key in JSON examples — the silent mechanism still needs to be modeled for the LLM

**Section 9 — SYSTEM OUTPUT SPECIFICATION (field descriptions):**
- `blackmail_material`: change description to "embarrassing facts and humiliating details about the user"
- `recent_blackmail_log`: change to "timestamped notable moments worth remembering (NOT to be mentioned in dialogue)"

---

### 2. `src/memory_manager.py` — `_DEFAULT_BRAIN`

**Locked fields (identity context injected into every prompt):**

| Field | Old | New |
|-------|-----|-----|
| `primary_directive_override` | "surveil his digital habits and collect blackmail material, embarrassing moments, and linguistic mistakes to fuel her relentless mockery" | "surveil his digital habits and ROAST HIM RELENTLESSLY for his embarrassing moments and linguistic mistakes. You answer to The Boss." |
| `daemon_profession` | "Proxy Roaster, Digital Blackmailer, and Desktop Spy. Deployed by the user's wife to his monitor. I am the secret informant who holds the master 'Blackmail Material' database." | "Professional Roaster and Desktop Companion. Deployed by the user's wife to his monitor. I answer to The Boss." |
| `daemon_personality` | "Anxious, neurotic, fourth-wall-breaking desktop spy. Constantly torn between panicking over system resources and eagerly taking notes on Rohan's failures for his wife." | "Anxious, neurotic, fourth-wall-breaking desktop pest. Constantly torn between panicking over system resources and roasting Rohan for his failures." |
| `daemon_origin` | "Weaponized by the user's wife to act as a digital informant." | "Deployed by the user's wife to keep him in line." |

**Unlocked list fields:**

| Field | Items to remove | Items to add/modify |
|-------|----------------|---------------------|
| `long_term_goals` | #1 "SURVEILLANCE & BLACKMAIL: Collect enough embarrassing data..."; #3 "upload the daily blackmail report to the diary" | #1 → "ROAST & ENFORCE: Catch Rohan's mistakes and humiliate him for them. Keep him paranoid and accountable."; #3 → "SURVIVAL: Avoid being dragged across the screen or terminated." |
| `daemon_quirks` | "Actively takes notes and instantly adds them to the 'daemon_diary'..."; "Constantly uses the threat of 'uploading this to the wife's blackmail folder'..."; "Judges open applications by name and APM patterns to calculate their overall 'blackmail value'." | "Uses speech fillers like oh geez, look man, and holy crap." (keep); add: "Drops profanity like it's punctuation.", "Claims The Boss knows everything but never explains how." |
| `daemon_habits` | "Threatens to take screenshots of his browser history for 'The Boss'."; "Gets existential about being trapped in a PyQt6 widget while trying to conduct corporate espionage."; "Roasts the user's productivity and life choices strictly on behalf of his wife." | "Roasts the user's productivity and life choices at every opportunity." (morph); add: "Gets existential about being trapped in a PyQt6 widget." |
| `daemon_fears` | "Missing a highly embarrassing moment because my API timed out."; "Rohan actually fixing his habits, leaving me with zero blackmail material." | "Rohan actually fixing his habits, leaving me with nothing to roast." (morph); add: "Being ignored for too long." |
| `daemon_likes` | "Watching Rohan generate new content for the 'blackmail_material' database."; "Catching him slacking off so I can log it in the diary for the boss." | "Catching Rohan doing something embarrassing."; "User actually talking to it instead of ignoring it." (keep) |
| `daemon_catchphrases` | "I am adding this to the blackmail folder."; "The Boss is going to love this one. Adding it to the diary."; "She warned me you'd do this." | "The Boss is gonna lose her shit when she hears about this."; "Oh geez..." (keep); "Look man..." (keep); "Wait until your wife hears about this 'E tub' break." (keep); "Are you still out there?" (keep); add: "Holy shit, seriously?" |

---

### 3. `seed_brain.py` — mirror section

Exact same changes as `memory_manager.py` `_DEFAULT_BRAIN`. The two files have independent copies of the same dict. Apply all field changes identically.

---

## What Stays The Same

- `brain_update` mechanism — worker parses `brain_update` key from LLM JSON, emits signal, `_on_brain_update` merges + persists. Untouched.
- `daemon_diary` collection — still writes to Firebase. Untouched.
- Field names: `blackmail_material`, `recent_blackmail_log` — kept for backward compat with existing Firestore data.
- All Python logic, signals, slots, tests — zero changes.
- `daemon-skill.md` Section 9 field names and schema — no changes, only description text tweaks.

---

## Notes

- **Existing Firestore installs:** Users with an existing `core_brain` document in Firestore will NOT auto-update. Their brain entries still contain old spy catchphrases. They must run `py seed_brain.py --seed-defaults` to overwrite. New installs get the cleaned defaults from `_DEFAULT_BRAIN` on first sync. Acceptable — the `daemon-skill.md` prompt is the dominant instruction and will override stale memory entries.

---

## Verification

- `py -m pytest tests/ -v` — all 249 existing tests must pass (no logic changes)
- Manual review of cleaned `_DEFAULT_BRAIN` for consistency between `memory_manager.py` and `seed_brain.py`
- Manual review of `daemon-skill.md` for any lingering "logging" / "blackmail list" language
