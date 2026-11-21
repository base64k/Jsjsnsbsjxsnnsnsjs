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


def rpc_lines(report):
    """The RPC requests to the IOP's servers and their replies, from the start of the run."""
    if report is None:
        return None
    out = [l for l in report.splitlines() if "RPC 0x" in l or "RPC reply" in l]
    return "\n".join(out) if out else None


def write_lines(report):
    """The stores to the watched addresses, from the start of the run (each at most twice)."""
    if report is None:
        return None
    seen, out = {}, []
    for line in report.splitlines():
        if line.startswith("[write]") and seen.get(line, 0) < 2:
            seen[line] = seen.get(line, 0) + 1
            out.append(line)
    return "\n".join(out) if out else None


def watch_lines(report):
    """The trace's lines (--watch), each at most three times, from the start of the run."""
    if report is None:
        return None
    seen, out = {}, []
    for line in report.splitlines():
        if line.startswith("[watch"):
            if seen.get(line, 0) < 3:
                seen[line] = seen.get(line, 0) + 1
                out.append(line)
    return "\n".join(out) if out else None


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
                    read("build/ee_disasm.txt"), 12000)
    text += section("The watched functions (--watch): their arguments and the memory behind them",
                    watch_lines(report), 14000, keep="tail")
    text += section("The sound driver's RPC requests and replies (the words sent and answered)",
                    rpc_lines(report), 7000)
    text += section("The stores to the watched addresses (--watch-write): who fills them",
                    write_lines(report), 9000)
    text += section("The IOP, from its start (each line at most twice)",
                    iop_first_lines(report), 5000)
    text += section("Report (end)", report[-6000:] if report else None, 6000, keep="tail")
    text += section("Where the module writes the flag it waits for (-0x5108)",
                    read("build/irx/finds.txt"), 3000)
    text += section("The disassembly's own diagnostics", read("build/irx/diag.txt"), 1000)
    text += section("The sound driver's code around the bind (ELF addresses)",
                    "\n".join(l for l in (read("build/irx/disasm.txt") or "").splitlines()
                              if _in_window(l)), 3000)
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
