"""The official server's policy (docs/design/core-loop.md §6.12, M5 track D): README.md's
"The official server" and the site's web/policy.html say the same, and what they say is what the
official server is set to do: deploy/coolify/server.ini's retention (no players' log, backups and
daily totals kept so long), the kick's longest, the name rule, the address the game connects to
(data/net.json), who runs and moderates it and how to be forgotten. The official line of welcome
names the policy page, and every page's footer links it."""

import configparser
import html
import json
import re
import unittest

from support import ROOT   # (server/ on the path, and the test process's memory cap)
from groundhold_server.admin import KICK_MAX_MINUTES, KICK_MINUTES   # noqa: E402
from groundhold_server.protocol import SPEC   # noqa: E402

POLICY_URL = "https://saschb2b.github.io/Groundhold/policy.html"


def official_settings():
    config = configparser.ConfigParser(interpolation=None)
    config.read(ROOT / "deploy/coolify/server.ini", encoding="utf-8")
    return config["server"]


def readme_section():
    """server/README.md's "## The official server", up to the next "## "."""
    text = (ROOT / "server/README.md").read_text(encoding="utf-8")
    found = re.search(r"^## The official server\n(.*?)(?=^## )", text, re.M | re.S)
    assert found, "server/README.md has no section '## The official server'"
    return found.group(1)


def plain(markdown_or_html):
    """The words alone: no tags, no Markdown links' targets, no backticks or bold, one space between."""
    text = re.sub(r"<!--.*?-->", " ", markdown_or_html, flags=re.S)
    text = re.sub(r"</?(?:p|li|ul|td|th|tr|table|div|h\d|header|footer|main|nav|br)\b[^>]*>", " ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = html.unescape(text).replace("`", "").replace("**", "")
    return re.sub(r"\s+", " ", text).strip()


def readme_rows():
    """The first cell of each row of the section's table of what is kept."""
    rows = [line for line in readme_section().splitlines() if line.startswith("| ") and not line.startswith("| ---")]
    return [plain(row.split("|")[1]) for row in rows[1:]]


def policy_rows():
    page = (ROOT / "web/policy.html").read_text(encoding="utf-8")
    table = re.search(r'<table class="kept">(.*?)</table>', page, re.S).group(1)
    return [plain(cell) for cell in re.findall(r"<tr><td>(.*?)</td>", table, re.S)]


class PolicyTest(unittest.TestCase):
    def pages(self):
        return {"server/README.md": plain(readme_section()),
                "web/policy.html": plain((ROOT / "web/policy.html").read_text(encoding="utf-8"))}

    def test_both_say_what_the_official_server_keeps_and_for_how_long(self):
        settings = official_settings()
        log_days, backup_days, stats_days = (settings.getint(key) for key in ("log_days", "backup_days", "stats_days"))
        self.assertEqual(log_days, 0, "the policy promises no players' log")
        for page, text in self.pages().items():
            self.assertIn("not kept on the official server (log_days = 0)", text, page)
            self.assertIn(f"{backup_days} days (backup_days = {backup_days})", text, page)
            self.assertIn(f"{stats_days} days (stats_days = {stats_days})", text, page)
            self.assertIn(f"age out within {backup_days} days", text, page)
            self.assertIn("writes it nowhere", text, page)
            for record in ("identity.key", "players.json", "logs/", "moderation.json", "stats.jsonl", "/stats"):
                self.assertIn(record, text, page)

    def test_both_keep_the_same_table(self):
        self.assertEqual(readme_rows(), policy_rows())
        self.assertEqual(len(readme_rows()), 7)

    def test_the_rules_are_the_servers(self):
        longest = KICK_MAX_MINUTES // (24 * 60)
        self.assertEqual(KICK_MINUTES, 10)
        most = int(re.fullmatch(r"\[A-Za-z0-9\]\[A-Za-z0-9 _-\]\{0,(\d+)\}", SPEC["name_pattern"]).group(1)) + 1
        for page, text in self.pages().items():
            self.assertIn(f"a kick (out for ten minutes, or up to {longest} days)", text, page)
            self.assertIn(f"1 to {most} letters, digits, spaces, - and _", text, page)
            self.assertIn("refuses to start with it on", text, page)

    def test_who_runs_it_where_and_how_to_be_forgotten(self):
        official = json.loads((ROOT / "data/net.json").read_text(encoding="utf-8"))["official"]
        for page, text in self.pages().items():
            self.assertIn(official, text, page)
            self.assertIn("Saschb2b, who makes Groundhold, runs it", text, page)
            self.assertNotIn("Sascha Becker", text, page)   # (the operator chose the handle only)
            self.assertIn("Saschb2b is its moderator", text, page)
            self.assertIn("delete net.cfg", text, page)
            self.assertIn('titled "Groundhold server: remove my data"', text, page)
            self.assertIn("runs forget", text, page)
            self.assertIn("it is not legal advice", text, page)
        self.assertIn("https://github.com/saschb2b/Groundhold/issues/new", (ROOT / "web/policy.html").read_text())
        self.assertIn(POLICY_URL, readme_section())

    def test_the_official_welcome_and_the_sites_footers_name_the_policy(self):
        motd = official_settings()["motd"]
        self.assertIn(POLICY_URL.removeprefix("https://"), motd)
        self.assertLessEqual(len(motd.encode()), SPEC["motd_bytes"])
        for page, link in (("web/index.html", "policy.html"), ("web/play/index.html", "../policy.html"),
                           ("web/policy.html", "policy.html")):
            footer = re.search(r"<footer>(.*?)</footer>", (ROOT / page).read_text(encoding="utf-8"), re.S).group(1)
            self.assertIn(f'<a href="{link}">', footer, page)

    def test_the_first_release_checks_what_the_policy_claims_before_it_goes_live(self):
        # (the page says the proxy keeps no access log, and Pages publishes it with main: the check
        # comes first, before the merge that brings the page to main, not only before the first
        # tag (review M5 round 2); and the policy's text is the user's decision, design 6.13)
        text = (ROOT / "server/README.md").read_text(encoding="utf-8")
        before = plain(text[text.index("Before the merge into `main`"):text.index("Before the first release")])
        self.assertLess(text.index("Before the first release"), text.index("Each release:"))
        self.assertRegex(before, r"access log checked off \(Coolify deployment, step 6\) before the policy page goes live")
        self.assertIn("web/policy.html says the proxy keeps no access log", before)
        self.assertIn("The policy's text decided (design §6.13)", before)
        for words in ("who runs and moderates the server", "reaches the moderator", "whether an imprint is needed"):
            self.assertIn(words, before)
        self.assertIn("the proxy in front of it is set to keep no access log",
                      plain((ROOT / "web/policy.html").read_text(encoding="utf-8")),
                      "the claim the checklist guards (change both together)")


if __name__ == "__main__":
    unittest.main()
