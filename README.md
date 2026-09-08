# Always-On Agent

**An Agent Skill for building a personal AI agent that runs continuously on your own
machine: the four layers to keep separate, how to wake a laptop that sleeps, which phone
channel will not get your number banned, and a read-only first pass that maps your
projects and credentials without ever reading a secret's value.**

[![License: MIT](https://img.shields.io/badge/License-MIT-2ea44f.svg)](LICENSE)
![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white)
![Zero dependencies](https://img.shields.io/badge/dependencies-0-6E56CF)
![Read only](https://img.shields.io/badge/first%20pass-read%20only-0f766e)

```bash
npx skills add Hiberius/always-on-agent
```

---

## Phase zero: look before you touch

The first thing an agent does on your machine must be *incapable* of doing harm. Not
careful. Incapable.

```bash
python3 scripts/survey.py secrets ~/
```
```
Key NAMES only. No value in this output was ever read into memory.

/Users/you/work/api/.env  (7 keys, 4 sensitive)   <- TRACKED BY GIT
    STRIPE_SECRET_KEY, DB_PASSWORD, JWT_SECRET, WEBHOOK_SIGNING_KEY
/Users/you/side/bot/.env  (3 keys, 2 sensitive)
    TELEGRAM_TOKEN, OPENAI_API_KEY

2 secret file(s) found.
1 of them are NOT gitignored inside a repository. Fix that before anything else.
```

It reads the name on the left of the assignment and discards everything else before
returning anything. The test suite plants a canary value in every fixture and asserts it
never appears in any output. That is the contract, not a promise.

```bash
python3 scripts/survey.py projects ~/
```
```
PROJECT                      BRANCH            DIRTY  AHEAD   DAYS  LAST COMMIT
old-client-site              main                 34      0    412  wip before holiday
scraper                      feat/retry            6      3     41  handle 429
api                          main                  0      0      2  bump deps

27 repo(s): 4 need attention, 9 have uncommitted or unpushed work
```

## The four layers

```
FACE     what you look at            reads state, never talks to the model
BRAIN    the agent loop              event-driven, does the work
PROFILE  who you are, what you do    private, gitignored, replaceable
VAULT    secrets                     the model never sees a value
```

**The engine is publishable, the profile is not.** Two directories, one gitignored, no
client name ever inside the engine. That split is what lets you open-source the useful
half, and retrofitting it means auditing every file you have written.

## The wake problem

Your laptop sleeps, so the agent misses everything. A laptop that never sleeps has no
battery.

```
event ──► always-on gateway ──► queue ──► signed POST to the Mac ──► the Mac drains it
```

The gateway holds no secrets and does no work. Sign the wake request and verify it, or
you have published an endpoint anyone can use to make your machine run an agent.

## The phone channel, one rule

**Official channels only.** An unofficial client for a messaging platform gets the number
banned, and on a working phone that is the number your clients use. Not an inconvenience,
your business line.

## Four states, and the fourth is the point

**working** · **waiting for you** · **idle** · **drifting**

An agent forty minutes into something nobody asked for is the failure that actually
happens, and it is invisible unless you have named it.

## Documentation

- [`SKILL.md`](SKILL.md) — the skill itself, what the agent reads
- [`references/architecture.md`](references/architecture.md) — the four layers, wake architecture, launchd vs cron, tmux, channel options with their risks, approval tiers, cost control
- [`references/first-run.md`](references/first-run.md) — the read-only first pass, its five rules, what to fix first, what to build after

## License

MIT. No network calls, no writes, no dependencies.
