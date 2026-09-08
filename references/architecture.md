# The four layers

Separate them at the start. Every one of them fails differently, and a design that merges
any two of them fails in a way you cannot debug.

```
FACE     what you look at            reads state, never talks to the model
BRAIN    the agent loop              event-driven, does the work
PROFILE  who you are, what you do    private, gitignored, replaceable
VAULT    secrets                     the model never sees a value
```

## Face

A status surface: a menu-bar item, a small always-on-top window, a page you keep open. It
reads a state file and a log. It **never** calls the model and never holds a token.

Two reasons this separation is not optional:

- The interface is the part you will rewrite five times. Coupling it to the agent means
  every visual change risks the loop.
- A face that cannot call the model cannot cost money by being open.

Give it four states and no more: **working**, **waiting for you**, **idle**, **drifting**.
The fourth one is the important one. An agent that has been running for forty minutes on
something nobody asked for is the failure mode that actually happens, and it is invisible
unless you name it.

## Brain

An agent loop as a daemon, woken by events, not a script on a timer that re-reads
everything.

Events worth waking for: a message arrives, a webhook fires, a scheduled briefing time,
a file changes in a watched folder. Everything else is polling, and polling on a laptop
is how you find the battery gone at lunchtime.

On macOS use **launchd**, not cron: cron does not survive sleep the way you expect, and
launchd will run a missed job on wake. Keep the process inside **tmux** or a supervisor so
you can attach to a live session and see what it is doing without stopping it.

## Profile

Your identity, your rules, your clients, your writing samples, your projects. The thing
that makes the agent yours rather than generic.

**The engine is publishable. The profile is not.** Two directories, one gitignored, and
never a client name inside the engine. That split is what lets you open-source the useful
half without leaking a customer list, and it is much harder to introduce later than to
start with.

## Vault

Secrets stay in the OS keychain or a password manager, fetched at the moment of use,
scoped per project, read-only wherever the API allows it.

**The model never sees a value.** It sees that a key exists, what it is called, and which
project it belongs to. `survey.py secrets` is built to that rule, and its test suite
plants a canary value and asserts it never appears in any output.

This is not paranoia about the model. It is that everything the model sees may end up in
a log, a transcript, an error report or a prompt sent somewhere else.

## The wake problem

Your laptop sleeps. An agent that only exists while the lid is open misses everything
that happens while it is closed, and a laptop that never sleeps is a laptop with no
battery.

The shape that works:

```
event ──► always-on gateway (a tiny worker, a VPS, anything cheap)
      ──► queue
      ──► signed POST to the Mac when it is awake
      ──► the Mac drains the queue
```

The gateway holds no secrets and does no work: it accepts, queues, and signs. Sign the
wake request and verify the signature, or you have published an endpoint that anyone can
use to make your laptop run an agent.

Schedule the daily briefing for a time the machine is reliably awake. Not 06:00.

## The phone channel

You will want to approve things from your phone. The rule that matters:

**Use an official channel.** An unofficial client for a messaging platform gets the number
banned, and on a working phone that number is the one your clients use. The cost of being
wrong here is not an inconvenience, it is your business line.

Options that do not carry that risk: a self-chat on a platform whose local database you
can read on your own machine, a platform's official business API on a second number, a
Telegram bot, or a small authenticated web page you open from your phone.

Whichever you pick, put an allowlist on it. An inbound channel that acts on any message
it receives is an inbound channel someone else can use.

## Approval gates

Three tiers, decided once and written down:

| Tier | Examples | Rule |
|---|---|---|
| Free | read, search, summarise, draft | just do it |
| Ask | send an email, commit, change a campaign, spend money | propose, wait for a yes |
| Never | delete, force push, rotate a credential, anything irreversible without a copy | not without you at the keyboard |

The tier is a property of the **action**, not of how confident the agent is. Confidence is
not evidence, and an agent that escalates its own permissions when it feels sure is an
agent that will one day feel sure about the wrong thing.

## Cost

A loop that wakes on every event and thinks with a large model will surprise you at the
end of the month.

- Route by task: a cheap model for triage and classification, the expensive one only for
  the work that needs it.
- Cap the context. Conversations and project histories grow without limit unless
  something truncates them.
- Log tokens per event and read that log weekly. The expensive event is never the one you
  expected.
