# Phase zero: look before you touch

The first thing a personal agent does on your machine must be incapable of doing harm.
Not "careful". Incapable: a pass that only reads, and whose output you check before
anything is allowed to write.

```bash
python3 scripts/survey.py projects ~/
python3 scripts/survey.py secrets  ~/
python3 scripts/survey.py stale    ~/ --days 30
```

## What the survey establishes

**Where the work is.** Every git repository, its branch, uncommitted files, unpushed
commits, and how long since the last one. This is the map the agent reasons over later,
and it is also, on most machines, the first honest look anyone has had at it in a year.

**Where the secrets are.** Which files hold credentials and what the keys are called.
Never a value. The tool reads the name on the left of the assignment and discards the rest
before returning anything, and the test suite plants a canary value and asserts it never
appears in the output.

**What has been abandoned.** Projects untouched for a month with uncommitted work. That
combination is the most common way something is lost on a laptop, and it is worth fixing
before it is worth automating anything.

## The rules the first pass obeys

1. **Reads only.** No writes anywhere, including no cache files in the directories it
   surveys.
2. **Never opens a secret's value.** Key names are enough to build a map; values are
   only ever needed by the process actually making the call.
3. **Never descends into a repository.** A repo is a leaf. Walking inside it turns a
   ten-second survey into a ten-minute one and adds nothing.
4. **Prunes the noise**: `node_modules`, virtualenvs, caches, build output, `Library`.
   Not for speed alone: a survey that reports 40,000 directories reports nothing.
5. **Bounded depth.** Six levels finds everything a person actually organises and stops
   before it finds the inside of a dependency tree.

## The first thing to fix

A `.env` inside a repository that is not gitignored. `survey.py secrets` marks it
`TRACKED BY GIT` and exits non-zero.

If it has already been committed, adding it to `.gitignore` does not remove it from
history. Rotate the credential; treat rewriting history as a separate decision made with
a clear head, not at the moment of discovery.

## Then, and only then

Once the survey is clean and you have read it:

1. Write the profile: who you are, what you work on, how you want to be told things.
2. Wire **one** event end to end, with an approval gate, and watch it run a few times.
3. Add a second only once the first has been boring for a week.

The failure mode of building this is not a bug. It is a system that does eleven things
adequately and nothing reliably, built in an evening, abandoned in a month because you
never trusted any of the eleven.

One boring, reliable loop beats a demo of ten.
