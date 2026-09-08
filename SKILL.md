---
name: always-on-agent
description: Use when building a personal AI agent that runs continuously on your own machine - deciding the architecture, waking a laptop that sleeps, choosing a phone channel that will not get a number banned, keeping secrets away from the model, setting approval gates for irreversible actions, or running the read-only first pass that maps projects and credentials before the agent is allowed to touch anything.
---

# Always-On Agent

## Overview

A personal agent on your own machine is four systems, not one, and they fail differently:

```
FACE     what you look at            reads state, never talks to the model
BRAIN    the agent loop              event-driven, does the work
PROFILE  who you are, what you do    private, gitignored, replaceable
VAULT    secrets                     the model never sees a value
```

**Core principle: the first pass must be incapable of doing harm, and the engine must be
publishable without the profile.** Both are much harder to introduce later than to start
with.

## When to use

- Designing or building an agent that runs continuously on a personal machine
- The laptop sleeps and the agent misses everything that happens meanwhile
- Choosing how to approve actions from a phone
- Deciding what the agent may do alone and what it must ask about
- Keeping credentials out of prompts, logs and transcripts
- The first run on a machine nobody has surveyed

**Not for:** a hosted always-on service on a server you control, where none of the sleep,
wake or personal-data problems apply.

## Phase zero, before anything can write

```bash
python3 scripts/survey.py projects ~/     # every repo, dirty files, unpushed, age
python3 scripts/survey.py secrets  ~/     # which files hold keys, and which keys
python3 scripts/survey.py stale    ~/     # abandoned work that is not committed
```

Reads only. Never descends into a repository. Never opens a secret's **value**: it reads
the name on the left of the assignment and discards the rest before returning anything.
The test suite plants a canary value and asserts it never appears in any output.

`secrets` exits non-zero when it finds a credentials file inside a repo that is not
gitignored. Fix that first, and rotate the credential rather than assuming a `.gitignore`
entry retroactively hides what was already committed.

## The wake problem

A laptop that sleeps misses events. A laptop that never sleeps has no battery.

```
event ──► always-on gateway ──► queue ──► signed POST to the Mac ──► the Mac drains it
```

The gateway holds no secrets and does no work: it accepts, queues, and signs. **Sign the
wake request and verify the signature**, or you have published an endpoint anyone can use
to make your machine run an agent.

On macOS use `launchd`, not cron: launchd runs a job missed during sleep. Keep the loop in
`tmux` or under a supervisor so you can attach to a live session without stopping it.

## The phone channel: one rule

**Use an official channel.** An unofficial client for a messaging platform gets the number
banned, and on your working phone that number is the one your clients use. The cost of
being wrong is not an inconvenience, it is your business line.

Safe shapes: a self-chat whose local database you read on your own machine, a platform's
official business API on a second number, a bot on a platform that has bots, or a small
authenticated page you open from your phone. Whichever you choose, put an allowlist on it.

## Approval gates

| Tier | Examples | Rule |
|---|---|---|
| Free | read, search, summarise, draft | just do it |
| Ask | send, commit, change a campaign, spend money | propose and wait |
| Never | delete, force push, rotate a credential, anything irreversible | not without you at the keyboard |

The tier is a property of the **action**, not of the agent's confidence. An agent that
escalates its own permissions when it feels sure will one day feel sure about the wrong
thing.

## Engine and profile are two directories

The engine is generic and publishable. The profile holds your identity, your clients,
your writing samples, your rules, and is gitignored. No client name ever appears inside
the engine.

This split is what lets you open-source the useful half. Retrofitting it means auditing
every file you have written.

## Four states, and the fourth is the point

**working** · **waiting for you** · **idle** · **drifting**

An agent forty minutes into something nobody asked for is the failure mode that actually
happens, and it is invisible unless the face has a name for it.

## Reference

| Topic | File |
|---|---|
| The four layers, wake architecture, launchd and tmux, channel options, cost control | `references/architecture.md` |
| The read-only first pass, its five rules, what to fix first, what to build after | `references/first-run.md` |

## Common mistakes

- **Letting the first pass write.** Anything that can write before you have read the
  survey will eventually write the wrong thing to the wrong project.
- **Putting a secret's value anywhere the model can see it.** It ends up in a log, a
  transcript, an error report, or a prompt sent somewhere else.
- **An unofficial messaging client.** Banned number, and it is the number your clients use.
- **Polling instead of waking.** The battery is gone by lunchtime and nothing is fresher.
- **Coupling the face to the loop.** The interface is the part you rewrite five times.
- **Building eleven capabilities in one evening.** One boring, reliable loop beats a demo
  of ten, and the demo is abandoned in a month because you never trusted any of it.
- **Scheduling the briefing at 06:00.** The machine is asleep. Pick an hour it is awake.
