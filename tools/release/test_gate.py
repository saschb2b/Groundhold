"""The release gate refuses a tag the tree does not say it is, or one without dated notes; it plans
what a run of release.yml releases (a tag published, a run by hand a dry run, of a tag or of the
branch). The release's text is tools/release/release_notes.py's (test_release_notes.py).

    python3 -m unittest discover -s tools/release -t tools/release
"""

import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import gate

ROOT = Path(__file__).resolve().parents[2]
try:
    import yaml
except ImportError:  # (the release's own runner has it; the tests below say so when skipped)
    yaml = None
GIT = ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false",
       "-c", "init.defaultBranch=main", "-c", "advice.detachedHead=false"]


def git(*args, cwd):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run([*GIT, *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout.strip()

PROJECT = """config_version=5

[application]

config/name="Groundhold"
config/version="%s"
run/main_scene="res://scenes/hub.tscn"

[display]

config/version="9.9.9"
"""

CHANGELOG = """# Changelog

## Unreleased

Things on main.

## 1.2.0 · 2026-11-02

The release's notes.

- A line of them.

## 1.1.0 · 2026-10-30

Older notes.

## 1.0.0

"""


class GateTest(unittest.TestCase):
    def tree(self, version="1.2.0", changelog=CHANGELOG):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        (root / "project.godot").write_text(PROJECT % version if version is not None else "[application]\n",
                                            encoding="utf-8")
        if changelog is not None:
            (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
        return root

    def run_gate(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = gate.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_a_tag_the_tree_agrees_with_passes(self):
        root = self.tree()
        self.assertEqual(gate.problems(root, "v1.2.0"), [])
        code, out, _ = self.run_gate("--root", str(root), "check", "v1.2.0")
        self.assertEqual(code, 0)
        self.assertIn("agree", out)

    def test_another_version_in_project_godot_refuses(self):
        root = self.tree(version="1.1.0")
        code, _, err = self.run_gate("--root", str(root), "check", "v1.2.0")
        self.assertEqual(code, 1)
        self.assertIn("config/version is 1.1.0", err)

    def test_only_the_application_section_counts(self):
        self.assertEqual(gate.project_version(self.tree(version="1.2.0")), "1.2.0")
        self.assertEqual(gate.problems(self.tree(version=None), "v1.2.0")[0],
                         "project.godot has no application/config/version")

    def test_no_changelog_section_refuses(self):
        found = gate.problems(self.tree(version="1.3.0"), "v1.3.0")
        self.assertEqual(found, ["CHANGELOG.md has no section '## 1.3.0'"])

    def test_an_empty_section_refuses(self):
        self.assertEqual(gate.problems(self.tree(version="1.0.0"), "v1.0.0"),
                         ["CHANGELOG.md's section '## 1.0.0' is empty"])

    def test_no_changelog_at_all_refuses(self):
        self.assertEqual(gate.problems(self.tree(changelog=None), "v1.2.0"), ["CHANGELOG.md has no section '## 1.2.0'"])

    def test_a_longer_version_is_not_its_prefix(self):
        root = self.tree(version="1.2.0", changelog="## 1.2.0-rc.1\n\nA candidate.\n\n## 1.2.01\n\nNo.\n")
        self.assertIsNone(gate.changelog_section(root, "1.2.0"))

    def test_tags_must_be_vxyz(self):
        root = self.tree()
        for tag in ("1.2.0", "v1.2", "v1.2.0-rc.1", "v1.2.0\n", "release"):
            self.assertEqual(len(gate.problems(root, tag)), 1, tag)
            self.assertIn("is not vX.Y.Z", gate.problems(root, tag)[0])

    def test_a_heading_without_its_date_refuses_a_tag_and_warns_a_dry_run(self):
        root = self.tree(changelog=CHANGELOG.replace("## 1.2.0 · 2026-11-02", "## 1.2.0 · TBD"))
        found = gate.problems(root, "v1.2.0")
        self.assertEqual(len(found), 1)
        self.assertIn("'## 1.2.0 · TBD' has no date", found[0])
        self.assertEqual(gate.problems(root, "v1.2.0", need_date=False), [])
        code, _, err = self.run_gate("--root", str(root), "check", "v1.2.0")
        self.assertEqual(code, 1)
        self.assertIn("::error", err)
        code, out, err = self.run_gate("--root", str(root), "check", "v1.2.0", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("::warning", err)
        self.assertIn("has no date", err)
        bare = self.tree(changelog="## 1.2.0\n\nNotes.\n")
        self.assertIn("'## 1.2.0' has no date", gate.problems(bare, "v1.2.0")[0])

    def test_a_dry_run_still_refuses_another_version_or_no_notes(self):
        code, _, err = self.run_gate("--root", str(self.tree(version="1.1.0")), "check", "v1.2.0", "--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("config/version is 1.1.0", err)
        self.assertEqual(self.run_gate("--root", str(self.tree(version="1.3.0")), "check", "v1.3.0", "--dry-run")[0], 1)

    def test_this_tree_is_releasable_as_its_own_version(self):
        # (its date may still be TBD while the release is prepared: a tag then needs it)
        version = gate.project_version(gate.ROOT)
        self.assertRegex(version, r"^\d+\.\d+\.\d+$", "project.godot's config/version")
        self.assertEqual(gate.problems(gate.ROOT, "v" + version, need_date=False), [])


class PlanTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        (self.root / "project.godot").write_text(PROJECT % "1.2.0", encoding="utf-8")

    def plan(self, **environ):
        return gate.plan(environ, self.root)

    def test_a_pushed_tag_is_published(self):
        self.assertEqual(self.plan(EVENT="push", REF_TYPE="tag", REF_NAME="v1.2.0"),
                         {"tag": "v1.2.0", "version": "1.2.0", "publish": "true"})

    def test_a_pushed_tag_that_is_no_version_or_a_branch_is_refused(self):
        for tag in ("v1.2", "1.2.0", "v1.2.0.1", "v1.2.0-rc.1", "vnext"):
            with self.assertRaisesRegex(gate.GateError, "is not vX.Y.Z", msg=tag):
                self.plan(EVENT="push", REF_TYPE="tag", REF_NAME=tag)
        with self.assertRaisesRegex(gate.GateError, "pushed tag"):
            self.plan(EVENT="push", REF_TYPE="branch", REF_NAME="main")
        with self.assertRaises(gate.GateError):
            self.plan(EVENT="schedule")

    def test_a_run_by_hand_is_a_dry_run_unless_told_otherwise(self):
        self.assertEqual(self.plan(EVENT="workflow_dispatch", INPUT_TAG="", INPUT_DRY_RUN="true"),
                         {"tag": "", "version": "1.2.0", "publish": "false"}, "the branch at project.godot's version")
        self.assertEqual(self.plan(EVENT="workflow_dispatch", INPUT_TAG=" v1.1.0 ", INPUT_DRY_RUN="true"),
                         {"tag": "v1.1.0", "version": "1.1.0", "publish": "false"})
        self.assertEqual(self.plan(EVENT="workflow_dispatch", INPUT_TAG="v1.1.0", INPUT_DRY_RUN="false")["publish"],
                         "true", "a tag released again")
        with self.assertRaisesRegex(gate.GateError, "needs a tag"):
            self.plan(EVENT="workflow_dispatch", INPUT_TAG="", INPUT_DRY_RUN="false")

    def test_the_plan_goes_to_the_jobs_outputs(self):
        output = self.root / "output"
        environ = {"EVENT": "push", "REF_TYPE": "tag", "REF_NAME": "v1.2.0", "GITHUB_OUTPUT": str(output)}
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gate.main(["--root", str(self.root), "plan"], environ), 0)
        self.assertEqual(output.read_text(encoding="utf-8"), "tag=v1.2.0\nversion=1.2.0\npublish=true\n")
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(gate.main(["--root", str(self.root), "plan"], dict(environ, REF_NAME="v1")), 1)
        self.assertTrue(err.getvalue().startswith("::error"))
        self.assertEqual(output.read_text(encoding="utf-8").count("tag="), 1, "nothing written for a refused run")


@unittest.skipIf(yaml is None or not shutil.which("git"), "needs PyYAML and git")
class OnMainTest(unittest.TestCase):
    """A release is a tag on main: release.yml's own step, run in bash as the runner does, in a
    one-commit-deep checkout of the tag as actions/checkout makes it."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.remote, work = self.root / "remote.git", self.root / "work"
        git("init", "--bare", str(self.remote), cwd=self.root)
        git("init", str(work), cwd=self.root)
        git("remote", "add", "origin", str(self.remote), cwd=work)
        for n in range(3):
            (work / "file.txt").write_text(f"main {n}\n", encoding="utf-8")
            git("add", "file.txt", cwd=work)
            git("commit", "-m", f"main {n}", cwd=work)
            if n == 1:
                git("tag", "v1.0.0", cwd=work)
        git("switch", "-c", "feature", "HEAD~1", cwd=work)
        (work / "file.txt").write_text("feature\n", encoding="utf-8")
        git("commit", "-am", "feature", cwd=work)
        git("tag", "v1.0.1", cwd=work)
        git("push", "origin", "main", "feature", "--tags", cwd=work)
        flow = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8"))
        self.step = next(step for step in flow["jobs"]["gate"]["steps"] if step.get("id") == "main")

    def run_step(self, tag, publish):
        checkout = self.root / f"checkout-{tag}-{publish}"
        git("clone", "--quiet", "--depth", "1", "--branch", tag, self.remote.as_uri(), str(checkout), cwd=self.root)
        tools = checkout / "tools" / "release"
        tools.mkdir(parents=True)
        for name in ("gate.py",):
            (tools / name).write_text((ROOT / "tools/release" / name).read_text(encoding="utf-8"), encoding="utf-8")
        environment = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "GITHUB_"))}
        environment["PUBLISH"] = publish
        return subprocess.run(["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", self.step["run"]],
                              cwd=checkout, env=environment, capture_output=True, text=True, timeout=60)

    def test_a_tag_on_main_passes(self):
        done = self.run_step("v1.0.0", "true")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("is on origin/main", done.stdout)

    def test_a_tag_on_another_branch_is_refused(self):
        done = self.run_step("v1.0.1", "true")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("::error title=Release gate::", done.stderr)
        self.assertIn("a release is a tag on main", done.stderr)

    def test_a_dry_run_of_such_a_tag_only_warns(self):
        done = self.run_step("v1.0.1", "false")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("::warning", done.stderr)

    def test_it_runs_only_for_a_tag(self):
        self.assertEqual(self.step["if"], "steps.plan.outputs.tag != ''")
        steps = [step.get("id") or step.get("name") for step in
                 yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8"))["jobs"]["gate"]["steps"]]
        self.assertLess(steps.index("plan"), steps.index("main"))


if __name__ == "__main__":
    unittest.main()
