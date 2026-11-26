"""Every script a workflow runs by its path (`run: scripts/release_upload.sh ...`, not `bash scripts/x.sh`) is executable
in git: a script stored as 100644 stops the runner with "Permission denied" (exit 126), as the nightly's uploads did on
every push to main while scripts/release_upload.sh was 100644. The other checks run the scripts through bash, so only
this one sees the mode.

Read from .github/workflows/*.yml: the run: steps, one line or a block, and in them a scripts/... path where a command
starts (a line's start, or after &&, ||, ;, |, then, do, else, ! or $( ). The mode is git's (git ls-files -s), the same
on every platform; with no git checkout, the file's own mode where there is one (not on Windows).

python -I -B tests/test_workflow_script_modes.py
"""
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

COMMAND = re.compile(r"(?:^|&&|\|\||[;|!]|\$\(|\b(?:then|do|else)\b)\s*(?:\./)?(scripts/[\w./-]+)")
RUN = re.compile(r"^(\s*)(?:-\s+)?run:\s*(.*)$")


def run_blocks(text):
    """Each run: step's shell text, as (line number, text)"""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = RUN.match(lines[i])
        if not m:
            i += 1
            continue
        indent, rest = len(m.group(1)), m.group(2).strip()
        start = i + 1
        i += 1
        if rest and rest[0] not in "|>":
            yield start, rest
            continue
        body = []
        while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > indent):
            body.append(lines[i])
            i += 1
        yield start + 1, "\n".join(body)


def called_scripts():
    """{script path: [workflow:line, ...]} for each script a workflow runs by its path"""
    found = {}
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        for line_no, shell in run_blocks(wf.read_text(encoding="utf-8")):
            for k, line in enumerate(shell.splitlines()):
                code = line.split(" #", 1)[0]
                if code.lstrip().startswith("#"):
                    continue
                for m in COMMAND.finditer(code):
                    found.setdefault(m.group(1), []).append("%s:%d" % (wf.name, line_no + k))
    return found


def git_modes(paths):
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-s", "--"] + paths, capture_output=True, text=True)
    except OSError:
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return {line.split("\t", 1)[1]: line.split()[0] for line in r.stdout.splitlines()}


def main():
    found = called_scripts()
    assert "scripts/release_upload.sh" in found, "the workflows' run: steps were not read: " + ", ".join(sorted(found))
    missing = [p for p in found if not (ROOT / p).is_file()]
    assert not missing, "workflows run scripts that are not in the repository: " + ", ".join(missing)
    modes = git_modes(sorted(found))
    bad = []
    if modes is not None:
        bad = [p for p in sorted(found) if modes.get(p) != "100755"]
        how = "git ls-files -s"
    elif os.name != "nt":
        bad = [p for p in sorted(found) if not os.access(ROOT / p, os.X_OK)]
        how = "the files' modes"
    else:
        print("SKIP: no git checkout, and Windows files have no executable mode")
        return 0
    if bad:
        for p in bad:
            print("FAIL: %s is not executable (%s), and %s run%s it by its path" % (
                p, modes.get(p, "?") if modes else "no x bit", ", ".join(found[p]), "s" if len(found[p]) == 1 else ""))
        print("fix: git update-index --chmod=+x " + " ".join(bad))
        return 1
    print("PASS: the %d scripts the workflows run by their paths are executable (%s)" % (len(found), how))
    return 0


if __name__ == "__main__":
    sys.exit(main())
