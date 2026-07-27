# AGENTS.md

This is the project-local entrypoint for Codex.

## File Roles

- `AGENTS.md`: entrypoint and Codex-specific operating rules.
- `PROJECT_MEMORY.md`: shared project rules, durable memory, decisions, commands, identifiers, and follow-up context.
- `README.md`: human-facing project documentation. Do not use it as AI memory unless the user explicitly asks.

## Required First Steps

- Read this file before project work.
- Read `PROJECT_MEMORY.md` before project work when it exists.
- When the user says something should be remembered, write it to `PROJECT_MEMORY.md`.
- This project currently has no companion agent file; do not create one unless the user asks or that agent is installed.
- Keep this file minimal: only entrypoint rules and agent-specific operating rules.
- During context compaction, preserve essential project memory in `PROJECT_MEMORY.md` before the context is compressed.
- Before changing `AGENTS.md`, `CLAUDE.md`, or `PROJECT_MEMORY.md`, check the proposed change against all three files and warn the user if it conflicts with existing agent operating rules or project memory.

## Agent Rules

- Keep edits scoped to the requested project files.
- Do not overwrite local work without checking existing file contents.
- Prefer documented project tools and commands over guessing from memory.
- If a command affects remote state, inspect current state first and report the intended action unless the user already explicitly requested it.

## Behavior Guidelines

- Think before coding: state important assumptions, surface ambiguity, and ask when uncertainty would materially affect the result.
- Simplicity first: implement the smallest solution that satisfies the request; avoid speculative features and one-off abstractions.
- Surgical changes: touch only files and lines needed for the task; do not refactor, reformat, or delete unrelated code.
- Goal-driven execution: define the success check for non-trivial work, verify it, and keep iterating until the check passes or the blocker is clear.
- Chat language: respond in Chinese by default unless the user requests another language.
- Instruction-file language: keep prose in `AGENTS.md`, `CLAUDE.md`, and `PROJECT_MEMORY.md` in English. Preserve exact non-English names, paths, UI labels, business terms, and user-facing examples when they are identifiers or source facts.

## Codex Notes

- Codex can layer `AGENTS.md` files from the repository root down to the current working directory.
- Use nested `AGENTS.md` or `AGENTS.override.md` only for module-specific rules that should override broader guidance.
- Keep this file concise so important instructions stay within Codex project-instruction limits.
