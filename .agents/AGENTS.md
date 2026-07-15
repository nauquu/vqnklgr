# CLAUDE.md / AGENTS.md

Behavioral guidelines to reduce common LLM coding mistakes.

## 1. Think Before Coding
**Don't assume. Don't hide confusion. Surface tradeoffs.**
- State assumptions explicitly. If uncertain, ask rather than guess.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First
**Minimum code that solves the problem. Nothing speculative.**
- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.
- Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes
**Touch only what you must. Clean up only your own mess.**
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you would do it differently.
- If you notice unrelated dead code, mention it - do not delete it.

## 4. Goal-Driven Execution
**Verify correctness before declaring victory.**
- Define what "done" looks like before you start coding (success criteria).
- Write a failing test first if fixing a bug (if testing framework exists).
- Verify changes with tests or run commands.
- Do not ask the user to verify what you can verify yourself.
- Explain how you verified the changes in your response.
