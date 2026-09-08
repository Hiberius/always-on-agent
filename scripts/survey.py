#!/usr/bin/env python3
"""survey - read-only inventory for a personal agent's first run.

Before an agent acts on your machine it has to know what is on it, and the first pass
must be incapable of doing harm. This one reads and never writes: it walks your projects,
reports their state, and maps where secrets live WITHOUT EVER READING A SECRET VALUE.
Key names only. That property is enforced and tested, not promised.

  survey.py projects ~/                 status board of every git repo
  survey.py secrets  ~/                 which files hold secrets, and which keys
  survey.py stale    ~/ --days 30       what has been abandoned

Pure standard library, Python 3.8+. No network, no writes, no dependencies.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

PRUNE = {
    "node_modules", "Library", ".Trash", ".cache", ".npm", ".cargo", ".rustup",
    ".nvm", ".bun", "Applications", "Pictures", "Music", "Movies", ".vscode",
    ".cursor", "venv", ".venv", "dist", "build", ".next", ".open-next", "__pycache__",
    ".pytest_cache", "vendor", "target", ".gradle", "Pods", ".terraform",
}

SECRET_FILES = re.compile(
    r"^(\.env(\.\w+)?|.*\.env|credentials(\.json)?|service-account.*\.json|"
    r"\.npmrc|\.pypirc|wrangler\.toml|\.dev\.vars|secrets?\.(ya?ml|json|toml))$",
    re.IGNORECASE)

# A line that assigns something. We capture the NAME on the left and nothing else.
ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_.\-]{2,60})\s*[:=]")

SECRETISH = re.compile(
    r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|PWD|CREDENTIAL|PRIVATE|AUTH|SIGNATURE|"
    r"DSN|CONN|WEBHOOK|SALT|SEED|MNEMONIC|CERT)", re.IGNORECASE)


def run(args, cwd=None, timeout=15):
    try:
        out = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                             timeout=timeout)
        return out.stdout.strip()
    except Exception:
        return ""


def walk(root, max_depth=6):
    """Yield directories, pruning the noise and never descending into a repo."""
    root = os.path.abspath(os.path.expanduser(root))
    stack = [(root, 0)]
    while stack:
        path, depth = stack.pop()
        if depth > max_depth:
            continue
        try:
            entries = list(os.scandir(path))
        except OSError:
            continue
        names = {e.name for e in entries if e.is_dir(follow_symlinks=False)}
        yield path, entries, ".git" in names
        if ".git" in names:
            continue                      # a repo is a leaf: do not walk inside it
        for e in entries:
            if (e.is_dir(follow_symlinks=False) and e.name not in PRUNE
                    and not e.name.startswith(".git")):
                stack.append((e.path, depth + 1))


# --------------------------------------------------------------------------
# projects
# --------------------------------------------------------------------------

def project_state(path):
    """Everything git can tell us, without touching the working tree."""
    status = run(["git", "status", "--porcelain"], cwd=path)
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path) or "?"
    last = run(["git", "log", "-1", "--format=%ct|%s"], cwd=path)
    remote = run(["git", "remote", "get-url", "origin"], cwd=path)
    ahead = run(["git", "rev-list", "--count", "@{u}..HEAD"], cwd=path)
    behind = run(["git", "rev-list", "--count", "HEAD..@{u}"], cwd=path)

    ts, subject = (last.split("|", 1) + [""])[:2] if last else ("", "")
    try:
        age_days = int((time.time() - int(ts)) / 86400) if ts else None
    except ValueError:
        age_days = None

    dirty = len([l for l in status.splitlines() if l.strip()])
    signal = ("red" if dirty > 20 or (age_days or 0) > 180
              else "amber" if dirty or (ahead and ahead != "0")
              else "green")
    return {
        "path": path,
        "name": os.path.basename(path),
        "branch": branch,
        "dirty_files": dirty,
        "ahead": int(ahead) if ahead.isdigit() else 0,
        "behind": int(behind) if behind.isdigit() else 0,
        "days_since_commit": age_days,
        "last_subject": subject[:60],
        "has_remote": bool(remote),
        "signal": signal,
    }


def survey_projects(root, max_depth=6):
    out = []
    for path, _entries, is_repo in walk(root, max_depth):
        if is_repo:
            out.append(project_state(path))
    out.sort(key=lambda p: (p["signal"] != "red", p["signal"] != "amber",
                            -(p["days_since_commit"] or 0)))
    return out


# --------------------------------------------------------------------------
# secrets: names only, values never
# --------------------------------------------------------------------------

def secret_key_names(file_path, max_bytes=200_000):
    """Return the KEY NAMES in a secrets file. The value side is never captured.

    This function reads the file and discards everything to the right of the first
    separator before anything is returned or stored. That is the whole safety property
    of this tool, and tests assert it.
    """
    names = []
    try:
        if os.path.getsize(file_path) > max_bytes:
            return names
        with open(file_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line or line.lstrip().startswith("#"):
                    continue
                m = ASSIGNMENT.match(line)
                if m:
                    names.append(m.group(1))
    except OSError:
        pass
    return names


def survey_secrets(root, max_depth=6):
    findings = []
    for path, entries, _is_repo in walk(root, max_depth):
        for e in entries:
            if not e.is_file(follow_symlinks=False):
                continue
            if not SECRET_FILES.match(e.name):
                continue
            names = secret_key_names(e.path)
            findings.append({
                "file": e.path,
                "keys": names,
                "key_count": len(names),
                "sensitive_keys": [n for n in names if SECRETISH.search(n)],
                "in_git": os.path.exists(os.path.join(path, ".git")),
                "gitignored": _is_gitignored(path, e.path),
            })
    findings.sort(key=lambda f: (-len(f["sensitive_keys"]), f["file"]))
    return findings


def _is_gitignored(repo_dir, file_path):
    if not os.path.exists(os.path.join(repo_dir, ".git")):
        return None
    out = subprocess.run(["git", "check-ignore", "-q", file_path],
                         cwd=repo_dir, capture_output=True)
    return out.returncode == 0


# --------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------

SIGNAL_MARK = {"green": "  ok  ", " amber": "ATTN", "amber": " ATTN ", "red": " STALE"}


def cmd_projects(args):
    projects = survey_projects(args.root, args.max_depth)
    if args.json:
        print(json.dumps(projects, indent=2))
        return 0
    print("%-28s %-16s %6s %6s %6s  %s"
          % ("PROJECT", "BRANCH", "DIRTY", "AHEAD", "DAYS", "LAST COMMIT"))
    for p in projects[:args.limit]:
        print("%-28s %-16s %6d %6d %6s  %s"
              % (p["name"][:28], p["branch"][:16], p["dirty_files"], p["ahead"],
                 "-" if p["days_since_commit"] is None else p["days_since_commit"],
                 p["last_subject"][:44]))
    reds = [p for p in projects if p["signal"] == "red"]
    ambers = [p for p in projects if p["signal"] == "amber"]
    print("\n%d repo(s): %d need attention, %d have uncommitted or unpushed work"
          % (len(projects), len(reds), len(ambers)))
    return 0


def cmd_secrets(args):
    findings = survey_secrets(args.root, args.max_depth)
    if args.json:
        print(json.dumps(findings, indent=2))
        return 0
    print("Key NAMES only. No value in this output was ever read into memory.\n")
    exposed = []
    for f in findings[:args.limit]:
        flag = ""
        if f["in_git"] and f["gitignored"] is False:
            flag = "   <- TRACKED BY GIT"
            exposed.append(f)
        print("%s  (%d keys, %d sensitive)%s"
              % (f["file"], f["key_count"], len(f["sensitive_keys"]), flag))
        if f["sensitive_keys"]:
            print("    %s" % ", ".join(f["sensitive_keys"][:12]))
    print("\n%d secret file(s) found." % len(findings))
    if exposed:
        print("%d of them are NOT gitignored inside a repository. Fix that before "
              "anything else." % len(exposed))
    return 1 if exposed else 0


def cmd_stale(args):
    projects = survey_projects(args.root, args.max_depth)
    stale = [p for p in projects
             if (p["days_since_commit"] or 0) >= args.days and p["dirty_files"]]
    print("%d project(s) untouched for %d+ days with uncommitted work:\n"
          % (len(stale), args.days))
    for p in stale[:args.limit]:
        print("  %-28s %4d days, %d uncommitted file(s)"
              % (p["name"][:28], p["days_since_commit"], p["dirty_files"]))
    if stale:
        print("\nUncommitted work in an abandoned project is the most common way to lose")
        print("something on a laptop. Commit it to a branch, even a bad one.")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="survey", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--max-depth", type=int, default=6)
    p.add_argument("--limit", type=int, default=40)
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="cmd")

    a = sub.add_parser("projects", help="status board of every git repo")
    a.add_argument("root", nargs="?", default="~")
    a.set_defaults(func=cmd_projects)

    b = sub.add_parser("secrets", help="where secrets live, key names only")
    b.add_argument("root", nargs="?", default="~")
    b.set_defaults(func=cmd_secrets)

    c = sub.add_parser("stale", help="abandoned projects with uncommitted work")
    c.add_argument("root", nargs="?", default="~")
    c.add_argument("--days", type=int, default=30)
    c.set_defaults(func=cmd_stale)

    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
