#!/usr/bin/env python3
"""save_report.py AGENT_OUTPUT REPORT_MD: the persona's final report, from a background
agent's output file (JSON lines), saved verbatim. It takes the agent's hand-back message if
there is one, else its last long reply."""
import json
import sys

if len(sys.argv) != 3:
    sys.exit(__doc__.strip().splitlines()[0])
src, dst = sys.argv[1], sys.argv[2]
handback = text = None
with open(src, encoding="utf-8") as f:
    for line in f:
        try:
            d = json.loads(line)
        except ValueError:
            continue
        m = d.get("message") or {}
        if m.get("role") != "assistant" or not isinstance(m.get("content"), list):
            continue
        for c in m["content"]:
            if c.get("type") == "tool_use" and "Handback" in c.get("name", ""):
                handback = c["input"].get("message", handback)
            elif c.get("type") == "text" and len(c.get("text", "")) > 1500:
                text = c["text"]
report = handback or text
if not report:
    sys.exit("no report found in " + src)
with open(dst, "w", encoding="utf-8") as f:
    f.write(report.rstrip() + "\n")
print(f"{dst}: {len(report)} characters")
