"""The deploy step of a release: the `release` branch moves to the tagged commit (forced, so an
older tag released by hand moves it back, while a tag push moves it only to the newest release
tag), and Coolify is asked to deploy only when all three of its secrets are set, failing on any
answer but 2xx and on a redirect; the image's moving tags follow the newest release alike. The
branch is pushed to a bare repository in a temporary folder, release.yml's and server-image.yml's
own steps run against it in bash, and Coolify is a local HTTP stub.

    python3 -m unittest discover -s tools/release -t tools/release
"""

import contextlib
import http.server
import io
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest
from unittest import mock
import urllib.error
import urllib.parse
import urllib.request

import deploy

ROOT = Path(__file__).resolve().parents[2]
try:
    import yaml
except ImportError:  # (the release's own runner has it; the tests below say so when skipped)
    yaml = None

GIT = ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false",
       "-c", "init.defaultBranch=main"]


def git(*args, cwd):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run([*GIT, *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout.strip()


def quietly(call):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = call()
    return code, out.getvalue()


@unittest.skipUnless(shutil.which("git"), "needs git")
class Repository(unittest.TestCase):
    """A bare remote with two commits on main, and a checkout of it."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        self.remote, self.work = root / "remote.git", root / "work"
        git("init", "--bare", str(self.remote), cwd=root)
        git("init", str(self.work), cwd=root)
        git("remote", "add", "origin", str(self.remote), cwd=self.work)
        self.commits = []
        for n in range(2):
            (self.work / "file.txt").write_text(f"version {n}\n", encoding="utf-8")
            git("add", "file.txt", cwd=self.work)
            git("commit", "-m", f"version {n}", cwd=self.work)
            self.commits.append(git("rev-parse", "HEAD", cwd=self.work))
        git("push", "origin", "main", cwd=self.work)

    def release_branch(self):
        return git("rev-parse", "--verify", "-q", "refs/heads/release", cwd=self.remote)

    def tag(self, name, commit, annotated=False):
        git("tag", *(["-a", "-m", name] if annotated else []), name, commit, cwd=self.work)
        git("push", "origin", f"refs/tags/{name}", cwd=self.work)

    def push(self, commit, *flags, environ=None):
        return quietly(lambda: deploy.main(["push", commit, "--repo", str(self.work), *flags],
                                           environ={} if environ is None else environ))

    def outputs(self):
        path = self.work.parent / "github-output"
        return path, lambda: dict(line.split("=", 1) for line in path.read_text().splitlines()) if path.exists() else {}



class PushTest(Repository):
    def test_the_release_branch_moves_to_the_tagged_commit(self):
        self.assertEqual(self.push(self.commits[1])[0], 0)
        self.assertEqual(self.release_branch(), self.commits[1])

    def test_an_older_tag_released_by_hand_moves_it_back(self):
        # (a rollback: the Release workflow run by hand with the older tag, dry run off)
        self.tag("v1.0.1", self.commits[0])
        self.tag("v1.0.2", self.commits[1])
        self.push(self.commits[1], "--tag", "v1.0.2")
        self.assertEqual(self.push(self.commits[0], "--tag", "v1.0.1")[0], 0)
        self.assertEqual(self.release_branch(), self.commits[0])

    def test_a_tag_push_never_moves_it_back_to_an_older_release(self):
        # (v1.0.1 and a hotfix v1.0.2 pushed close together release in parallel; v1.0.1's deploy
        # comes last, after v1.0.2's, and must leave the official server on v1.0.2)
        self.tag("v1.0.1", self.commits[0])
        self.tag("v1.0.2", self.commits[1], annotated=True)
        path, read = self.outputs()
        code, out = self.push(self.commits[1], "--tag", "v1.0.2", "--newest-only", environ={"GITHUB_OUTPUT": str(path)})
        self.assertEqual(code, 0, out)
        self.assertEqual((self.release_branch(), read()), (self.commits[1], {"moved": "true"}))
        path.unlink()
        code, out = self.push(self.commits[0], "--tag", "v1.0.1", "--newest-only", environ={"GITHUB_OUTPUT": str(path)})
        self.assertEqual(code, 0, out)
        self.assertIn("::notice", out)
        self.assertIn("v1.0.2 is", out)
        self.assertEqual((self.release_branch(), read()), (self.commits[1], {"moved": "false"}))

    def test_the_newest_is_by_version_not_by_text(self):
        self.tag("v1.0.9", self.commits[1])
        self.tag("v1.0.10", self.commits[0])
        self.tag("v2.0.0-rc.1", self.commits[1])      # (not a release tag: the gate refuses it)
        self.tag("vnext", self.commits[1])
        self.assertEqual(self.push(self.commits[0], "--tag", "v1.0.10", "--newest-only")[0], 0)
        self.assertEqual(self.release_branch(), self.commits[0])
        self.push(self.commits[1], "--tag", "v1.0.9", "--newest-only")
        self.assertEqual(self.release_branch(), self.commits[0])

    def test_a_tag_push_needs_its_tag_and_the_remotes_tags(self):
        code, out = self.push(self.commits[1], "--newest-only")
        self.assertEqual(code, 1)
        self.assertIn("not a release tag", out)
        code, out = quietly(lambda: deploy.main(["push", self.commits[1], "--tag", "v1.0.0", "--newest-only",
                                                 "--remote", "nowhere", "--repo", str(self.work)], environ={}))
        self.assertEqual(code, 1)
        self.assertIn("cannot list", out)
        with self.assertRaises(subprocess.CalledProcessError):
            self.release_branch()

    def test_a_shallow_checkout_moves_it_too(self):
        # (release.yml's job checks the tag out as actions/checkout does: one commit deep)
        self.tag("v1.0.0", self.commits[1])
        shallow = self.work.parent / "shallow"
        git("clone", "--depth", "1", "--branch", "main", self.remote.as_uri(), str(shallow), cwd=self.work.parent)
        code, out = quietly(lambda: deploy.main(["push", self.commits[1], "--tag", "v1.0.0", "--newest-only",
                                                 "--repo", str(shallow)], environ={}))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.release_branch(), self.commits[1])

    def test_only_a_full_commit_id(self):
        code, out = self.push("v1.0.0")
        self.assertEqual(code, 1)
        self.assertIn("not a full commit id", out)
        with self.assertRaises(subprocess.CalledProcessError):
            self.release_branch()

    def newest(self, tag):
        path, read = self.outputs()
        path.unlink(missing_ok=True)
        code, out = quietly(lambda: deploy.main(["newest", tag, "--repo", str(self.work)],
                                                environ={"GITHUB_OUTPUT": str(path)}))
        self.assertEqual(code, 0, out)
        return read()

    def test_the_images_latest_and_minor_tags_follow_the_newest_release(self):
        self.tag("v1.0.4", self.commits[0])
        self.tag("v1.0.5", self.commits[0])
        self.tag("v1.1.0", self.commits[1])
        self.assertEqual(self.newest("v1.1.0"), {"latest": "true", "minor": "true"})
        self.assertEqual(self.newest("v1.0.4"), {"latest": "false", "minor": "false"})
        self.assertEqual(self.newest("v1.0.5"), {"latest": "false", "minor": "true"}, "a hotfix of 1.0 moves 1.0")
        self.assertEqual(self.newest("v1.2.0"), {"latest": "true", "minor": "true"})
        self.assertEqual(self.newest("v1.2.0-rc.1"), {"latest": "false", "minor": "false"})


@unittest.skipIf(yaml is None, "needs PyYAML")
class WorkflowStepsTest(Repository):
    """release.yml's deploy steps and server-image.yml's newest step, run in bash as the runner does
    (bash -e -o pipefail) in a checkout whose origin is the bare repository."""

    def step(self, workflow, job, step_id):
        flow = yaml.safe_load((ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8"))
        return next(step for step in flow["jobs"][job]["steps"] if step.get("id") == step_id)

    def run_step(self, step, **env):
        tools = self.work / "tools" / "release"
        tools.mkdir(parents=True, exist_ok=True)
        (tools / "deploy.py").write_text((ROOT / "tools/release/deploy.py").read_text(encoding="utf-8"), encoding="utf-8")
        path, read = self.outputs()
        path.unlink(missing_ok=True)
        summary = self.work.parent / "summary"
        environment = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "GITHUB_"))}
        environment.update(GITHUB_OUTPUT=str(path), GITHUB_STEP_SUMMARY=str(summary), **env)
        done = subprocess.run(["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", step["run"]],
                              cwd=self.work, env=environment, capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return read(), done.stdout

    def test_a_tag_push_deploys_only_the_newest_and_a_run_by_hand_rolls_back(self):
        push = self.step("release.yml", "deploy", "push")
        self.tag("v1.0.1", self.commits[0])
        self.tag("v1.0.2", self.commits[1])
        moved, _ = self.run_step(push, EVENT="push", SHA=self.commits[1], TAG="v1.0.2")
        self.assertEqual((moved, self.release_branch()), ({"moved": "true"}, self.commits[1]))
        moved, out = self.run_step(push, EVENT="push", SHA=self.commits[0], TAG="v1.0.1")
        self.assertEqual((moved, self.release_branch()), ({"moved": "false"}, self.commits[1]), out)
        moved, _ = self.run_step(push, EVENT="workflow_dispatch", SHA=self.commits[0], TAG="v1.0.1")
        self.assertEqual((moved, self.release_branch()), ({"moved": "true"}, self.commits[0]))
        flow = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8"))
        coolify = next(s for s in flow["jobs"]["deploy"]["steps"] if "deploy.py coolify" in str(s.get("run", "")))
        self.assertEqual(coolify["if"], "steps.push.outputs.moved == 'true'", "Coolify only after a move")

    def test_the_image_step_says_whether_it_is_the_newest(self):
        step = self.step("server-image.yml", "image", "newest")
        self.tag("v1.0.4", self.commits[0])
        self.tag("v1.0.5", self.commits[0])
        self.tag("v1.1.0", self.commits[1])
        self.assertEqual(self.run_step(step, VERSION="1.0.4")[0], {"latest": "false", "minor": "false"})
        self.assertEqual(self.run_step(step, VERSION="1.0.5")[0], {"latest": "false", "minor": "true"})
        self.assertEqual(self.run_step(step, VERSION="1.1.0")[0], {"latest": "true", "minor": "true"})


class Coolify(http.server.BaseHTTPRequestHandler):
    answers = []
    seen = []

    def do_GET(self):  # noqa: N802 (http.server's name)
        status, body = self.answers.pop(0)
        url = urllib.parse.urlsplit(self.path)
        self.seen.append({"path": url.path, "query": urllib.parse.parse_qs(url.query),
                          "auth": self.headers.get("Authorization")})
        data = json.dumps(body).encode()
        self.send_response(status)
        if 300 <= status < 400:
            self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/api/v1/deploy?moved=1")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class CoolifyTest(unittest.TestCase):
    def setUp(self):
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Coolify)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        Coolify.answers, Coolify.seen = [], []
        self.env = {"COOLIFY_API_URL": f"http://127.0.0.1:{self.server.server_port}/",
                    "COOLIFY_TOKEN": "s3cret-token", "COOLIFY_APP_UUID": "app-uuid-1"}

    def coolify(self, env):
        return quietly(lambda: deploy.main(["coolify", "--timeout", "5"], environ=env))

    def test_without_secrets_a_notice_and_success(self):
        code, out = self.coolify({})
        self.assertEqual(code, 0)
        self.assertIn("::notice", out)
        self.assertEqual(Coolify.seen, [])

    def test_some_secrets_but_not_all_fail(self):
        code, out = self.coolify({"COOLIFY_API_URL": self.env["COOLIFY_API_URL"], "COOLIFY_TOKEN": "x"})
        self.assertEqual(code, 1)
        self.assertIn("COOLIFY_APP_UUID missing", out)
        self.assertEqual(Coolify.seen, [])

    def test_it_asks_coolify_to_deploy_the_app(self):
        Coolify.answers.append((200, {"deployments": [{"message": "Application deployment queued.",
                                                       "resource_uuid": "app-uuid-1", "deployment_uuid": "d-77"}]}))
        code, out = self.coolify(self.env)
        self.assertEqual(code, 0, out)
        self.assertEqual(Coolify.seen, [{"path": "/api/v1/deploy", "query": {"uuid": ["app-uuid-1"], "force": ["false"]},
                                         "auth": "Bearer s3cret-token"}])
        self.assertIn("d-77", out)
        self.assertNotIn("s3cret-token", out)

    def test_the_instances_address_may_end_in_a_slash_or_the_api(self):
        for suffix in ("", "/", "/api/v1", "/api/v1/"):
            Coolify.answers.append((200, {"deployments": [{"deployment_uuid": "d-1"}]}))
            base = f"http://127.0.0.1:{self.server.server_port}{suffix}"
            code, out = self.coolify(dict(self.env, COOLIFY_API_URL=base))
            self.assertEqual((code, Coolify.seen[-1]["path"]), (0, "/api/v1/deploy"), suffix + out)

    def test_an_answer_that_queued_nothing_fails_the_job(self):
        # (Coolify answers 200 for an app it skipped too: only a deployment_uuid says one was queued)
        for body in ({"deployments": [{"message": "Deployment skipped.", "resource_uuid": "app-uuid-1"}]},
                     {"deployments": []}, {"message": "Nothing"}, "not an object"):
            Coolify.answers.append((200, body))
            code, out = self.coolify(self.env)
            self.assertEqual(code, 1, body)
            self.assertIn("queued no deployment", out)
            self.assertNotIn("s3cret-token", out)

    def test_an_error_answer_fails_the_job(self):
        Coolify.answers.append((404, {"message": "No resources found.", "token": "s3cret-token"}))
        code, out = self.coolify(self.env)
        self.assertEqual(code, 1)
        self.assertIn("answered 404", out)
        self.assertIn("No resources found", out)
        self.assertNotIn("s3cret-token", out)

    def test_an_unauthorised_token_fails_the_job(self):
        Coolify.answers.append((401, {"message": "Unauthenticated."}))
        self.assertEqual(self.coolify(self.env)[0], 1)

    def test_no_answer_fails_the_job(self):
        env = dict(self.env, COOLIFY_API_URL="http://127.0.0.1:9")
        code, out = self.coolify(env)
        self.assertEqual(code, 1)
        self.assertIn("no answer", out)

    def test_not_an_http_url_fails(self):
        self.assertEqual(self.coolify(dict(self.env, COOLIFY_API_URL="file:///etc/passwd"))[0], 1)
        self.assertEqual(Coolify.seen, [])

    def test_plain_http_only_on_this_computer(self):
        # (the token goes in a header: over plain http anywhere else it would travel unencrypted)
        for base in ("http://coolify.example.invalid", "http://192.0.2.10:8000", "ftp://127.0.0.1"):
            code, out = self.coolify(dict(self.env, COOLIFY_API_URL=base))
            self.assertEqual(code, 1, base)
            self.assertIn("https://", out)
        self.assertEqual(Coolify.seen, [])
        Coolify.answers.append((200, {"deployments": [{"deployment_uuid": "d-2"}]}))
        local = f"http://localhost:{self.server.server_port}"
        self.assertEqual(self.coolify(dict(self.env, COOLIFY_API_URL=local))[0], 0)

    def test_a_redirect_is_not_followed_with_the_token(self):
        Coolify.answers.append((302, {"to": "elsewhere"}))
        Coolify.answers.append((200, {"deployments": [{"deployment_uuid": "d-3"}]}))
        code, out = self.coolify(self.env)
        self.assertEqual(code, 1, out)
        self.assertIn("answered 302", out)
        self.assertEqual(len(Coolify.seen), 1, "the token went to the redirect's target")

    def test_the_instances_address_is_never_printed(self):
        env = dict(self.env, COOLIFY_API_URL="http://127.0.0.1:9/api/v1")
        code, out = self.coolify(env)
        self.assertEqual(code, 1)
        self.assertNotIn("127.0.0.1:9", out)

    def test_nor_in_a_failures_reason(self):
        # (GitHub masks the secret whole, the URL; a TLS hostname mismatch names the host alone:
        # review M5 round 2)
        env = dict(self.env, COOLIFY_API_URL="https://coolify.hidden.example:8000")
        mismatch = ssl.SSLCertVerificationError(
            1, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: Hostname mismatch, certificate is "
               "not valid for 'coolify.hidden.example'. (_ssl.c:1032)")
        for error, said in ((urllib.error.URLError(mismatch), "TLS"),
                            (urllib.error.URLError(OSError("cannot reach coolify.hidden.example:8000")), "***"),
                            (ssl.SSLError(1, "wrong version for coolify.hidden.example"), "TLS")):
            with mock.patch.object(urllib.request.OpenerDirector, "open", side_effect=error):
                code, out = self.coolify(env)
            self.assertEqual(code, 1, out)
            self.assertIn("no answer", out)
            self.assertIn(said, out)
            self.assertNotIn("coolify.hidden.example", out)


if __name__ == "__main__":
    unittest.main()
