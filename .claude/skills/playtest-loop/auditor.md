# The report's auditor (run after every report, before triage)

A separate agent (another model family where one is available) reads the persona's file, its session card, the
report, its notes and the pictures the report names, and answers in a table, one row per finding:

- **No evidence**: a problem or highlight with no frame, command or picture; or a frame whose picture does not show
  what the report says.
- **Knowledge it should not have**: a fact the screen never showed (a number only the source, docs or a test knows; a
  rival's corked pack before its uncorking; a future wave's contents not on the strip), or a design term the game
  never uses on screen.
- **Suggestion dressed as observation**: a fix or a design idea in the OBSERVATION line.
- **Score against severities**: 7 or more with a severity 3 or 4 open; a score far from what the quit points and
  the "would come back" answer say; every changelog item "as it played" with no frames.
- **Drift**: the persona check's answers against the persona file (history, pet peeves, what a 5 means); voice or
  habits that left the persona (a veteran who reads every tooltip slowly, a newcomer using genre jargon).
- **Positivity**: praise with no moment behind it; problems softened in the summary that the blocks call major.

Its verdict: the report as is, the report with these rows struck or downgraded, or the session to run again. Triage
reads the report through the auditor's rows. Keep the auditor's table beside the report (`audit-sN.md`).
