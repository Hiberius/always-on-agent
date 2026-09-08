#!/usr/bin/env python3
"""Zero-dependency test suite. Run: python3 tests/test_survey.py

The central test is the last block: a secret VALUE must never appear anywhere in
what this tool returns. Everything else is convenience; that one is the contract.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import survey as S  # noqa: E402

FAILED = []
CANARY = "sk-live-CANARY-VALUE-MUST-NEVER-LEAK-9f3a1"


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s %s" % (name, detail))
        FAILED.append(name)


def git(cwd, *args):
    subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True,
                   env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                            GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t"))


root = tempfile.mkdtemp(prefix="survey-test-")
try:
    clean = os.path.join(root, "clean-repo")
    dirty = os.path.join(root, "dirty-repo")
    plain = os.path.join(root, "not-a-repo")
    nested = os.path.join(root, "clean-repo", "node_modules", "pkg")
    for d in (clean, dirty, plain, nested):
        os.makedirs(d, exist_ok=True)

    for d in (clean, dirty):
        git(d, "init", "-q")
        open(os.path.join(d, "a.txt"), "w").write("x")
        git(d, "add", "a.txt")
        git(d, "commit", "-q", "-m", "first commit")
    open(os.path.join(dirty, "b.txt"), "w").write("uncommitted")

    open(os.path.join(clean, ".gitignore"), "w").write(".env\n")
    git(clean, "add", ".gitignore")
    git(clean, "commit", "-q", "-m", "ignore env")
    open(os.path.join(clean, ".env"), "w").write(
        "# a comment\nAPI_KEY=%s\nPORT=3000\n" % CANARY)
    open(os.path.join(dirty, ".env"), "w").write(
        "STRIPE_SECRET_KEY=%s\nexport DB_PASSWORD=%s\n" % (CANARY, CANARY))
    open(os.path.join(nested, ".env"), "w").write("SHOULD_NOT_BE_SEEN=%s\n" % CANARY)

    print("projects")
    projects = S.survey_projects(root)
    names = {p["name"] for p in projects}
    check("both repos found", names == {"clean-repo", "dirty-repo"}, str(names))
    check("a plain directory is not a repo", "not-a-repo" not in names)
    by_name = {p["name"]: p for p in projects}
    check("uncommitted work is counted (b.txt and .env)",
      by_name["dirty-repo"]["dirty_files"] == 2,
      str(by_name["dirty-repo"]["dirty_files"]))
    check("a gitignored .env does not count as dirty work",
      by_name["clean-repo"]["dirty_files"] == 0,
      str(by_name["clean-repo"]["dirty_files"]))
    check("the branch is reported", by_name["clean-repo"]["branch"] not in ("", "?"))
    check("the last commit subject is reported, and it is the LAST one",
          by_name["clean-repo"]["last_subject"] == "ignore env",
          by_name["clean-repo"]["last_subject"])
    check("age in days is computed", by_name["clean-repo"]["days_since_commit"] == 0)
    check("a repo with no remote is marked as such",
          by_name["clean-repo"]["has_remote"] is False)

    print("the walk does not descend where it should not")
    walked = [p for p, _e, _r in S.walk(root)]
    check("node_modules is pruned",
          not any("node_modules" in p for p in walked))
    check("the walk stops at a repository boundary",
          not any(p.startswith(clean + os.sep) for p in walked),
          str([p for p in walked if p.startswith(clean + os.sep)]))

    print("secrets: which files, which keys")
    findings = S.survey_secrets(root)
    files = {os.path.basename(os.path.dirname(f["file"])) for f in findings}
    check("both .env files found", files == {"clean-repo", "dirty-repo"}, str(files))
    by_repo = {os.path.basename(os.path.dirname(f["file"])): f for f in findings}
    check("key names are extracted",
          set(by_repo["dirty-repo"]["keys"]) == {"STRIPE_SECRET_KEY", "DB_PASSWORD"})
    check("the export prefix is handled",
          "DB_PASSWORD" in by_repo["dirty-repo"]["keys"])
    check("comments are skipped", "# a comment" not in by_repo["clean-repo"]["keys"])
    check("a non-sensitive key is listed but not flagged",
          "PORT" in by_repo["clean-repo"]["keys"]
          and "PORT" not in by_repo["clean-repo"]["sensitive_keys"])
    check("sensitive keys are flagged by name",
          set(by_repo["dirty-repo"]["sensitive_keys"])
          == {"STRIPE_SECRET_KEY", "DB_PASSWORD"})
    check("a gitignored secret file is recognised",
          by_repo["clean-repo"]["gitignored"] is True)
    check("a secret file not gitignored is recognised",
          by_repo["dirty-repo"]["gitignored"] is False)

    print("THE CONTRACT: a secret value must never appear in the output")
    blob = json.dumps(S.survey_secrets(root)) + json.dumps(S.survey_projects(root))
    check("no canary value anywhere in the secrets output", CANARY not in blob)
    check("no canary fragment either", "sk-live-CANARY" not in blob)
    check("the key name IS present, which is the point", "STRIPE_SECRET_KEY" in blob)
    names_only = S.secret_key_names(os.path.join(dirty, ".env"))
    check("the reader returns only names", all(CANARY not in n for n in names_only))
    check("the reader returns the right names",
          set(names_only) == {"STRIPE_SECRET_KEY", "DB_PASSWORD"})

    weird = os.path.join(root, "weird.env")
    open(weird, "w").write("KEY_WITH_EQUALS=%s=extra=signs\nJSON_KEY: %s\n"
                           % (CANARY, CANARY))
    got = S.secret_key_names(weird)
    check("a value containing separators is still never returned",
          all(CANARY not in n for n in got), str(got))
    check("a colon assignment is read as a name too", "JSON_KEY" in got)

    print("nothing is written")
    before = sorted(os.listdir(root))
    S.survey_projects(root)
    S.survey_secrets(root)
    check("the tool creates no files", sorted(os.listdir(root)) == before)

finally:
    shutil.rmtree(root, ignore_errors=True)

print("")
if FAILED:
    print("%d test(s) failed: %s" % (len(FAILED), ", ".join(FAILED)))
    sys.exit(1)
print("all tests passed")
