#!/usr/bin/env python3
"""Post the PC reference run's report as a check run on the commit.

The artifacts and logs of a run are not always downloadable from outside; the
API is. Each part of the report has its own share of the check run's text
(GitHub caps it at 65,000 characters), so no part is cut by the others:
the summary, the EE code where the game stopped, the IOP's own lines from the
start, the end of the game's report, and the sound driver's code.

    python3 scripts/check_report.py
"""

import json
import os
import pathlib
import subprocess

LIMIT = 65000


def read(path):
    p = pathlib.Path(path)
    return p.read_text(errors="replace") if p.exists() else None


def section(title, body, budget, keep="head"):
    """A markdown section; the body cut to `budget` characters (head or tail)."""
    if body is None:
        return ""
    if len(body) > budget:
        body = body[:budget] + "\n(cut)" if keep == "head" else "(cut)\n" + body[-budget:]
    return "\n## %s\n```\n%s\n```" % (title, body)


def iop_first_lines(report):
    """The IOP's lines from the start of the run, each at most twice."""
    if report is None:
        return None
    seen, first = {}, []
    for line in report.splitlines():
        if line.startswith("[iop]") or "[host] IOP" in line or "[host] SIF" in line:
            if seen.get(line, 0) < 2:
                seen[line] = seen.get(line, 0) + 1
                first.append(line)
    return "\n".join(first)


def main():
    report = read("games/up/build/port/report.txt")
    text = "## Summary\n```\n%s\n```" % (read("games/up/build/smoke/summary.txt") or "(no summary)")
    text += section("The EE's code where it stopped (the functions' disassembly)",
                    read("build/ee_disasm.txt"), 14000)
    text += section("The IOP, from its start (each line at most twice)",
                    iop_first_lines(report), 12000)
    text += section("Report (end)", report[-14000:] if report else None, 14000, keep="tail")
    text += section("Where the module writes the flag it waits for (-0x5108)",
                    read("build/irx/finds.txt"), 4000)
    text += section("The disassembly's own diagnostics", read("build/irx/diag.txt"), 1500)
    text += section("The sound driver's code around the bind (ELF addresses)",
                    "\n".join(l for l in (read("build/irx/disasm.txt") or "").splitlines()
                              if _in_window(l)), 6000)
    text = text[-LIMIT:] if len(text) > LIMIT else text

    body = {
        "name": "PC reference run (headless)",
        "head_sha": os.environ.get("GITHUB_SHA"),
        "status": "completed",
        "conclusion": "neutral",
        "output": {"title": "How far the game got", "summary": "See the text.", "text": text},
    }
    repo = os.environ["GITHUB_REPOSITORY"]
    subprocess.run(["gh", "api", "-X", "POST", "repos/%s/check-runs" % repo, "--input", "-"],
                   input=json.dumps(body).encode(), check=False)


def _in_window(line):
    """The code in the poll's window: IOP 0x10700-0x107F0, ELF 0x700-0x7F0."""
    head = line.split(":")[0].strip()
    try:
        address = int(head, 16)
    except ValueError:
        return False
    return 0x700 <= address <= 0x7F0 or 0x10700 <= address <= 0x107F0


if __name__ == "__main__":
    main()
