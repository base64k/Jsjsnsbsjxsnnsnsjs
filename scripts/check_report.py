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
import re
import os
import pathlib
import subprocess

LIMIT = 65000
BAD_VALUE_RE = re.compile(r"read at 0x([0-9A-Fa-f]{8}), outside guest memory")


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
    """The stores to the watched addresses: the ones that write the value the run
    stopped on first, then the first ones of the run (what fills an address before
    it is read), then the last ones before the stop."""
    if report is None:
        return None
    lines = [l for l in report.splitlines() if l.startswith("[write]")]
    bad_value = BAD_VALUE_RE.search(read("games/up/build/smoke/summary.txt") or "")
    bad = [l for l in lines if bad_value and (" <- 0x%s " % bad_value.group(1)) in l][:20]
    # The first stores: the ones that fill the address before the stop (a stream
    # is written long before it is read). Then the last ones, where it stopped.
    first = lines[:30]
    out = bad[:8] + [l for l in first if l not in bad[:8]] + [l for l in lines[-10:] if l not in first and l not in bad[:8]]
    return "\n".join(out) if out else None


def watch_lines(report):
    """The trace's lines (--watch), each at most three times, from the start of the run."""
    if report is None:
        return None
    seen, out = {}, []
    for line in report.splitlines():
        if line.startswith("[watch") and not line.startswith(("[watch-out]", "[watch-src]")):
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
    # The unpacker's calls, decoded in Python from their own input (scripts/decode_src.py): first, they are short.
    text += section("The unpacker's calls, decoded in Python from their input (scripts/decode_src.py)",
                    "\n".join(l for l in report.splitlines() if l.startswith("decode src")) if report else None, 14000)
    text += section("The EE's code where it stopped (the functions' disassembly)",
                    read("build/ee_disasm.txt"), 34000)
    text += section("The watched functions (--watch): their arguments and the memory behind them",
                    watch_lines(report), 4000, keep="tail")
    text += section("The sound driver's RPC requests and replies (the words sent and answered)",
                    rpc_lines(report), 3000)
    text += section("The stores to the watched addresses (--watch-write): who fills them",
                    write_lines(report), 9000)
    text += section("The IOP, from its start (each line at most twice)",
                    iop_first_lines(report), 3000)
    text += section("Report (end)", report[-4000:] if report else None, 4000, keep="tail")
    text += section("The game's SetupHeap calls (its heap's start and size)",
                    "\n".join(l for l in report.splitlines() if l.startswith("[heap]")) if report else None, 1500)
    text += section("Where the module writes the flag it waits for (-0x5108)",
                    read("build/irx/finds.txt"), 1000)
    text += section("The disassembly's own diagnostics", read("build/irx/diag.txt"), 1000)
    # Every disc read the IOP made (cdvdman's sceCdRead, from --iop-trace): how many,
    # which buffers they fill, and the ones that do not fill the usual 0x28900.
    import re as _re
    from collections import Counter as _Counter
    read_re = _re.compile(r"cdvdman#6 sceCdRead\(([0-9A-Fa-f]+), ([0-9A-Fa-f]+), ([0-9A-Fa-f]+), ([0-9A-Fa-f]+)\)")
    reads = [m for m in (read_re.search(l) for l in (report or "").splitlines()) if m]
    buffers = _Counter(m.group(3).upper() for m in reads)
    unusual = [m.group(0) for m in reads if m.group(3).upper() != "00028900"]
    summary = "reads: %d; buffers: %s" % (len(reads), ", ".join("%s x%d" % (b, n) for b, n in buffers.most_common(12)))
    text += section("The disc reads the IOP made (sceCdRead): count and buffers, then the ones not into 0x28900",
                    summary + "\n" + "\n".join(unusual[:80]) if reads else None, 6000)
    # The CD server's own reads (N-commands: into EE or IOP memory, from the EE's requests).
    cd_lines = [l for l in (report or "").splitlines() if "CD: read" in l or "CD: N-command" in l]
    text += section("The CD server's reads (the EE's requests): %d in all, the first 60 and the last 20" % len(cd_lines),
                    "\n".join(cd_lines[:60] + (["..."] if len(cd_lines) > 80 else []) + cd_lines[-20:]) if cd_lines else None, 7000)
    # The IOP's stores in the range the run watches (PS2HOST_IOP_WATCH): who writes the buffer.
    iop_stores = [l for l in (report or "").splitlines() if l.startswith("[iop-write]")]
    text += section("The IOP's stores in the watched range (PS2HOST_IOP_WATCH): %d in all, the first 120 and the last 40" % len(iop_stores),
                    "\n".join(iop_stores[:120] + (["..."] if len(iop_stores) > 160 else []) + iop_stores[-40:]) if iop_stores else None, 9000)
    text += section("The sound driver's code (ZNASND, the IOP copy and poll regions)", read("build/irx/disasm.txt"), 9000)
    text = text[-LIMIT:] if len(text) > LIMIT else text

    body = {
        "name": "PC reference run (headless) #%s" % os.environ.get("GITHUB_RUN_ID", ""),
        "head_sha": os.environ.get("GITHUB_SHA"),
        "status": "completed",
        "conclusion": "neutral",
        "output": {"title": "How far the game got", "summary": "See the text.", "text": text},
    }
    repo = os.environ["GITHUB_REPOSITORY"]
    # The sound driver module itself, base64 (one check run of its own), so that
    # its code can be read outside the run.
    b64 = read("build/irx/znasnd.b64")
    if b64:
        body2 = {"name": "ZNASND.IRX (base64) #%s" % os.environ.get("GITHUB_RUN_ID", ""), "head_sha": os.environ.get("GITHUB_SHA"),
                 "status": "completed", "conclusion": "neutral",
                 "output": {"title": "ZNASND.IRX", "summary": "base64 of the module", "text": b64[:65000]}}
        subprocess.run(["gh", "api", "-X", "POST", "repos/%s/check-runs" % repo, "--input", "-"],
                       input=json.dumps(body2).encode(), check=False)
    subprocess.run(["gh", "api", "-X", "POST", "repos/%s/check-runs" % repo, "--input", "-"],
                   input=json.dumps(body).encode(), check=False)


def _in_window(line):
    """The code in the RPC server's window: IOP 0x10528-0x10740."""
    head = line.split(":")[0].strip()
    try:
        address = int(head, 16)
    except ValueError:
        return False
    return 0x10528 <= address <= 0x10740


if __name__ == "__main__":
    main()
