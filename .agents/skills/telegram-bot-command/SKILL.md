---
name: telegram-bot-command
description: Guidelines for extending Telegram remote control commands in klg.py, ensuring chat_id authorization, target machine scoping (@machine), and safe HTML responses.
---

# Telegram Bot Command Skill

This skill defines the rules for implementing and maintaining remote control Telegram commands in `klg.py`.

## Security & Scoping Rules

1. **Chat ID Authorization**:
   - Only messages from the authorized `CHAT_ID` (persisted in `state.json`) are processed.
   - If unauthorized chat ID sends `/auth <secret_key>`, update `CHAT_ID` in memory and `state.json`.

2. **Machine Scoping (`@machine_name`)**:
   - Commands targeting specific machines contain `@machine_name` suffix (e.g., `/status @Laptop-A`).
   - If `@` is present in the raw command and the target does not match current machine name (case-insensitive), silently ignore the command.

3. **Self-Update Command Path**:
   - Always download new executable and batch updater to `%TEMP%` (`os.getenv('TEMP')`) to prevent `Permission Denied` errors on protected working directories.

4. **HTML Parsing Safety**:
   - All response messages should be entity-safe or use HTML fallback when Telegram API returns HTTP 400 `can't parse entities`.
