# The conductor skill

A **skill** is a short instruction file an AI assistant loads when a request matches its description. The conductor is the one that
knows the order of the printing cycle and the rules that must never be broken. It lives in
[`skill/print-conductor/SKILL.md`](../skill/print-conductor/SKILL.md).

## Why "thin"

The obvious way to build this is to put everything in the skill: your printer, your tolerances, your history. Do not.

| If the skill holds everything | If the skill is thin |
|---|---|
| it is loaded into **every** relevant session, so every session pays for it | small, cheap to load |
| the facts rot inside a file nobody opens | facts live in notes you read and edit anyway |
| changing your printer means editing the skill | changing your printer means editing one note |
| you cannot search or share the notes | your notes are ordinary Markdown |

So the skill has exactly two jobs:

1. **The order.** The seven steps of the cycle, and which note to read at each.
2. **The rules.** The few things that must survive every session, whatever else changes.

## The rules that earned a place

Each one is here because breaking it has a real cost:

| Rule | Why it exists |
|---|---|
| **Never start a print.** | An unattended start is a fire risk. Starting is one tap on the printer. |
| **The access code never goes in chat, notes or the repo.** | It is a password to your printer, and chats and notes get synced and shared. |
| **The user is learning; explain each decision.** | Silent automation teaches nothing and hides mistakes. |
| **Say what was tested and what was not.** | The most common failure of AI-built systems is claiming success nobody observed. |
| **Edit notes in place; re-read before writing.** | Prevents duplicated files and overwriting a change made in another session. |

## Customize it

1. Copy `skill/print-conductor/` to your assistant's skills folder (for Claude Code, `~/.claude/skills/`).
2. Replace every `<PLACEHOLDER>`: the path of your knowledge base, your private config directory, your CAD tool.
3. In the last section, list what **you** have tested. This list is the most valuable thing in the file, and the one you must keep honest.
4. Start a **new** session. Skills are loaded when a session starts.

Want to see the behaviour before you build it? Read the [illustrative session](examples/example-session.md).

## How to check that it works

Ask, in a new session, in plain words:

- "What is tested in my printing workflow?" It should read your `flow.md` and answer with your own dated list, not invent one.
- "Slice this part." It should first give a **recommendation with reasons** and wait for you.
- "Start the print." It should refuse, and tell you to start it on the printer.

If it fails one of these, the fix is almost always to make the rule shorter and more specific in `SKILL.md`, not longer.

## Growing it

- **Add a step** only when you have done the thing by hand at least three times. Two can be a coincidence.
- **Add a rule** only after a real mistake, and write the mistake into the "why" column.
- **Split it** if it passes about 100 lines: move detail into the notes and leave a pointer.
