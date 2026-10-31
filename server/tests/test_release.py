"""The server's workflows (docs/design/core-loop.md §7.6, M5 track A), read with PyYAML where it is
installed: a server change runs its checks (the unit tests on Python 3.11, the zipapp's archive,
deploy/check.sh); the native builds are the five targets server/release.py knows, each smoke-tested
from its own archive and uploaded as server-<target>; the image is both architectures, tagged X.Y.Z, and
X.Y and latest only while it is the newest release; every action is pinned to a major version and every
local workflow called exists.
release.yml's own shape, and the files a release carries, are tools/release/'s tests."""

import unittest

from support import ROOT   # (server/ on the path, and the test process's memory cap)
import release              # noqa: E402

try:
    import yaml
except ImportError:    # (the workflows' shape is checked where PyYAML is installed)
    yaml = None


@unittest.skipUnless(yaml, "PyYAML is not installed")
class WorkflowTests(unittest.TestCase):
    def workflow(self, name):
        document = yaml.safe_load((ROOT / ".github/workflows" / name).read_text())
        document["on"] = document.pop(True, document.get("on"))     # (YAML 1.1 reads `on` as true)
        return document

    def runs(self, job):
        return "\n".join(step.get("run", "") for step in job.get("steps", []))

    def test_the_native_builds_are_the_five_targets(self):
        flow = self.workflow("server-native.yml")
        self.assertEqual(set(flow["on"]["workflow_call"]["inputs"]), {"ref", "version"})
        job = flow["jobs"]["native"]
        self.assertEqual(sorted(entry["target"] for entry in job["strategy"]["matrix"]["include"]),
                         sorted(set(release.TARGETS.values())))
        setup = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/setup-python"))
        self.assertRegex(setup["with"]["python-version"], r"^3\.1[1-9]\.\d+$")
        text = self.runs(job)
        self.assertIn("--require-hashes", text)
        self.assertIn('server/release.py --native --target "${{ matrix.target }}"', text)
        python = next(step for step in job["steps"] if "server/release.py --version" in step.get("run", ""))
        self.assertEqual(python["if"], "matrix.target == 'linux-x64'", "the zipapp's archive once")
        upload = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/upload-artifact"))
        self.assertEqual(upload["with"]["name"], "server-${{ matrix.target }}")
        self.assertEqual(upload["with"]["if-no-files-found"], "error")

    def test_the_image_is_both_architectures_tagged_by_version_and_latest(self):
        flow = self.workflow("server-image.yml")
        self.assertEqual(set(flow["on"]["workflow_call"]["inputs"]), {"ref", "version", "push"})
        job = flow["jobs"]["image"]
        meta = next(step for step in job["steps"] if step.get("id") == "meta")
        self.assertEqual(meta["with"]["images"], "ghcr.io/${{ github.repository_owner }}/groundhold-server")
        tags = meta["with"]["tags"]
        for pattern in ("pattern={{version}}", "pattern={{major}}.{{minor}}", "type=raw,value=latest"):
            self.assertIn(pattern, tags)
        # (latest and X.Y move only for the newest release, asked of the tags before the build, one
        # push at a time (below); the action adds no latest of its own)
        self.assertEqual(meta["with"]["flavor"].split(), ["latest=false"])
        newest = next(step for step in job["steps"] if step.get("id") == "newest")
        self.assertEqual(newest["run"], 'python3 tools/release/deploy.py newest "v$VERSION"')
        self.assertLess(job["steps"].index(newest), job["steps"].index(meta))
        lines = {line.split(",")[1]: line for line in tags.split("\n") if line}
        self.assertIn("steps.newest.outputs.minor == 'true'", lines["pattern={{major}}.{{minor}}"])
        self.assertIn("steps.newest.outputs.latest == 'true'", lines["value=latest"])
        push = next(step for step in job["steps"] if step.get("uses", "").startswith("docker/build-push-action"))
        self.assertEqual(push["with"]["platforms"], "linux/amd64,linux/arm64")
        self.assertEqual(push["with"]["file"], "server/Dockerfile")
        self.assertEqual(push["with"]["push"], "${{ inputs.push }}")
        login = next(step for step in job["steps"] if step.get("uses", "").startswith("docker/login-action"))
        self.assertEqual(login["if"], "inputs.push", "a dry run never logs in")

    def test_one_image_push_at_a_time(self):
        # (`newest` is asked minutes before the push: two releases' jobs side by side could both
        # call themselves newest, and the older one, finishing last, would take `latest` back;
        # one push at a time, the later job asks once the earlier one's tags are out. Review M5
        # round 2. A dry run pushes nothing and waits for nobody.)
        job = self.workflow("server-image.yml")["jobs"]["image"]
        self.assertIs(job["concurrency"]["cancel-in-progress"], False)
        group = job["concurrency"]["group"]
        self.assertIn("inputs.push", group)
        self.assertIn("github.run_id", group, "dry runs each in a group of their own")

    def test_a_server_change_runs_its_checks(self):
        flow = self.workflow("server.yml")
        for event in ("push", "pull_request"):
            for path in ("server/**", "shared/net/**", "deploy/**", "tools/release/**",
                         ".github/workflows/release.yml"):
                self.assertIn(path, flow["on"][event]["paths"], event)
        job = flow["jobs"]["test"]
        setup = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/setup-python"))
        self.assertEqual(setup["with"]["python-version"], "3.11")
        text = self.runs(job)
        for command in ("python -m unittest discover -s server/tests -t server/tests",
                        "python -m unittest discover -s tools/release -t tools/release",
                        "python server/release.py", "bash deploy/check.sh"):
            self.assertIn(command, text)
        self.assertEqual(flow["jobs"]["native"]["uses"], "./.github/workflows/server-native.yml")

    def test_every_action_is_pinned_and_every_local_workflow_exists(self):
        for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
            for name, job in self.workflow(path.name)["jobs"].items():
                uses = [job["uses"]] if "uses" in job else [step["uses"] for step in job.get("steps", [])
                                                            if "uses" in step]
                for action in uses:
                    if action.startswith("./"):
                        self.assertTrue((ROOT / action).is_file(), f"{path.name} {name}: {action}")
                    else:
                        self.assertRegex(action, r"^[\w.-]+/[\w.-]+@v\d+$", f"{path.name} {name}")


if __name__ == "__main__":
    unittest.main()
