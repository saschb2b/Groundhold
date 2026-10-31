"""The deployment (docs/design/core-loop.md §6.11, M5 track B): the image's Dockerfile and its
build context; the health checks the image and both Compose files run, run here against a real
server and real archives (the backup's turns unhealthy past 26 hours); the Coolify and self-host
Compose files as Compose resolves them (hardening, ports, volumes, the server.ini mount, the
image, Caddy without an access log, a DOMAIN required); the official server's settings, which
the real program starts with; the self-host .env.example; Godot keeping out of deploy/.

The Compose tests need `docker compose` and skip without it, unless GROUNDHOLD_REQUIRE_DOCKER=1
(server.yml sets it). deploy/check.sh builds the image and runs both stacks."""

import configparser
import contextlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

from support import ROOT
from groundhold_server.protocol import SPEC   # noqa: E402

DOCKERFILE = ROOT / "server/Dockerfile"
COOLIFY = ROOT / "deploy/coolify/compose.yaml"
SELFHOST = ROOT / "deploy/selfhost/compose.yaml"
HARDENED = {"read_only": True, "cap_drop": ["ALL"], "security_opt": ["no-new-privileges:true"],
            "tmpfs": ["/tmp:size=8m,mode=1777"]}


def health_checks(path):
    """The health check commands in a Compose file, in order (flow sequences of JSON strings)."""
    return [json.loads(found) for found in re.findall(r"^\s*test: (\[.*\])\s*$", path.read_text(), re.MULTILINE)]


def image_health_check():
    """The Dockerfile's HEALTHCHECK command, as Compose writes one."""
    text = DOCKERFILE.read_text().replace("\\\n", "")
    return ["CMD"] + json.loads(re.search(r"^HEALTHCHECK .*? CMD (\[.*\])$", text, re.MULTILINE)[1])


def run_check(test, **environ):
    """A health check's command run here (python3 as this Python): its exit status."""
    assert test[0] == "CMD" and test[1] == "python3", test
    return subprocess.run([sys.executable] + test[2:], env=dict(os.environ, **environ), capture_output=True,
                          timeout=30).returncode


@contextlib.contextmanager
def real_server(*args):
    """The real program on a free port of 127.0.0.1, its state in a temporary folder: its port."""
    with tempfile.TemporaryDirectory(prefix="groundhold-deploy-") as directory:
        process = subprocess.Popen([sys.executable, str(ROOT / "server/main.py"), "--host", "127.0.0.1", "--port", "0",
                                    "--state-dir", str(Path(directory) / "state"), *args],
                                   cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                   env=dict(os.environ, PYTHONUNBUFFERED="1"))
        try:
            line = process.stdout.readline()
            match = re.match(r"listening port=(\d+)", line)
            assert match, f"the server said {line!r}"
            yield int(match[1])
        finally:
            process.terminate()
            process.wait(timeout=10)
            process.stdout.close()


def health(port):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(f"http://127.0.0.1:{port}/health", timeout=5) as response:
        return json.load(response)


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def compose_available():
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(["docker", "compose", "version"], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


COMPOSE = compose_available()
REQUIRED = os.environ.get("GROUNDHOLD_REQUIRE_DOCKER") == "1"


def compose_config(*args, **environ):
    """`docker compose ... config --format json`, resolved: (exit status, the config or the error)."""
    environment = {key: value for key, value in os.environ.items()
                   if key not in ("DOMAIN", "VERSION", "SERVER_NAME", "SERVER_MOTD", "PLAYER_CAP")}
    environment.update(environ)
    result = subprocess.run(["docker", "compose", *args, "config", "--format", "json"], cwd=ROOT,
                            env=environment, capture_output=True, text=True, timeout=60)
    return result.returncode, json.loads(result.stdout) if result.returncode == 0 else result.stderr


class DockerfileTests(unittest.TestCase):
    def setUp(self):
        self.text = DOCKERFILE.read_text()

    def test_two_stages_on_pythons_slim_image_run_as_10001(self):
        stages = re.findall(r"^FROM (\S+)(?: AS (\w+))?$", self.text, re.MULTILINE)
        self.assertEqual(stages, [("scratch", "sources"), ("python:3.13-slim", "build"), ("python:3.13-slim", "")])
        self.assertIn("COPY --from=sources / /workspace/", self.text)
        self.assertIn("COPY --from=build /dist/ /app/", self.text)
        self.assertRegex(self.text, r"(?m)^USER 10001:10001$")
        self.assertRegex(self.text, r"(?m)^EXPOSE 8766$")
        self.assertEqual(SPEC["port"], 8766)
        self.assertIn('ENTRYPOINT ["python3", "/app/groundhold-server.pyz"]', self.text)
        self.assertIn('CMD ["--host", "0.0.0.0"]', self.text)
        self.assertIn("GROUNDHOLD_SERVER_STATE_DIR=/data", self.text)
        self.assertRegex(self.text, r"HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3")

    def test_the_ignore_file_lets_in_the_builds_inputs_and_they_are_enough(self):
        patterns = [line for line in (ROOT / "server/Dockerfile.dockerignore").read_text().splitlines()
                    if line and not line.startswith("#")]
        self.assertEqual(patterns[0], "**")
        allowed = [pattern[1:] for pattern in patterns[1:]]
        self.assertTrue(all(pattern.startswith("!") for pattern in patterns[1:]), patterns)
        # (the context as the file lets it in, alone, builds the zipapp: nothing the build reads is left out)
        with tempfile.TemporaryDirectory(prefix="groundhold-context-") as directory:
            context = Path(directory)
            for pattern in allowed:
                for source in ROOT.glob(pattern):
                    (context / source.relative_to(ROOT)).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, context / source.relative_to(ROOT))
            result = subprocess.run([sys.executable, "-I", "server/build.py", "--output", "dist/groundhold-server.pyz"],
                                    cwd=context, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(sorted(path.name for path in (context / "dist").iterdir()),
                             ["LICENSE", "README.md", "groundhold-server.pyz", "server.example.ini"])


class HealthCheckTests(unittest.TestCase):
    def test_the_server_checks_are_the_images_own(self):
        image = image_health_check()
        self.assertEqual(health_checks(COOLIFY)[0], image)
        self.assertEqual(health_checks(SELFHOST)[0], image)

    def test_the_server_check_asks_health_on_the_servers_port(self):
        check = image_health_check()
        with real_server() as port:
            self.assertEqual(run_check(check, GROUNDHOLD_SERVER_PORT=str(port)), 0)
            self.assertNotEqual(run_check(check, GROUNDHOLD_SERVER_PORT=str(free_port())), 0)
        # (nobody on 8766 here, or a server that is not this one's: the default port is asked)
        self.assertIn("or '8766'", check[3])

    def test_the_backup_check_turns_unhealthy_26_hours_after_the_newest_archive(self):
        checks = [health_checks(path)[1] for path in (COOLIFY, SELFHOST)]
        self.assertEqual(checks[0], checks[1])
        with tempfile.TemporaryDirectory() as directory:
            test = [part.replace("/backups/", directory + "/") for part in checks[0]]
            self.assertEqual(run_check(test), 1, "no archive yet")
            other = Path(directory) / "notes.tar.gz"
            other.write_bytes(b"")
            self.assertEqual(run_check(test), 1, "another file is no archive")
            archive = Path(directory) / "groundhold-state-20261031-001500.tar.gz"
            archive.write_bytes(b"")
            self.assertEqual(run_check(test), 0)
            for hours, status in ((25, 0), (27, 1)):
                then = time.time() - hours * 3600
                os.utime(archive, (then, then))
                self.assertEqual(run_check(test), status, f"{hours} hours old")
            newer = Path(directory) / "groundhold-state-20261101-001500.tar.gz"
            newer.write_bytes(b"")
            self.assertEqual(run_check(test), 0, "the newest archive counts")


@unittest.skipUnless(COMPOSE or REQUIRED, "docker compose is not installed")
class ComposeTests(unittest.TestCase):
    def assert_hardened(self, service, name):
        for key, value in HARDENED.items():
            self.assertEqual(service.get(key), value, f"{name}: {key}")
        self.assertEqual(service["logging"]["driver"], "json-file", name)
        self.assertTrue({"max-size", "max-file"} <= set(service["logging"]["options"]), name)
        self.assertEqual(service["restart"], "unless-stopped", name)
        self.assertNotIn("ports", service, name)
        self.assertNotIn("privileged", service, name)

    def mounts(self, service):
        return {mount["target"]: (mount["type"], mount["source"], bool(mount.get("read_only")))
                for mount in service["volumes"]}

    def test_coolify_runs_the_server_and_its_backup_hardened(self):
        status, config = compose_config("--project-directory", ".", "-f", str(COOLIFY))
        self.assertEqual(status, 0, config)
        self.assertEqual(set(config["services"]), {"groundhold", "backup"})
        self.assertEqual(set(config["volumes"]), {"groundhold-state", "groundhold-backups"})
        server, backup = config["services"]["groundhold"], config["services"]["backup"]
        for name, service in config["services"].items():
            self.assert_hardened(service, name)
            self.assertEqual(service["build"]["dockerfile"], "server/Dockerfile")
            self.assertEqual(Path(service["build"]["context"]).resolve(), ROOT.resolve())
        self.assertEqual(server["expose"], ["8766"])
        ini = ("bind", str((ROOT / "deploy/coolify/server.ini").resolve()), True)
        self.assertEqual(self.mounts(server), {"/data": ("volume", "groundhold-state", False),
                                               "/backups": ("volume", "groundhold-backups", True),
                                               "/app/server.ini": ini})
        self.assertEqual(self.mounts(backup), {"/data": ("volume", "groundhold-state", True),
                                               "/backups": ("volume", "groundhold-backups", False),
                                               "/app/server.ini": ini})
        self.assertEqual(server["command"], ["--host", "0.0.0.0", "--config", "/app/server.ini", "--state-dir", "/data"])
        self.assertEqual(backup["command"], ["--config", "/app/server.ini", "--state-dir", "/data", "--backup", "/backups"])
        self.assertEqual(server["healthcheck"]["interval"], "30s")
        self.assertEqual(server["healthcheck"]["test"], image_health_check())
        self.assertIn("26 * 3600", backup["healthcheck"]["test"][-1])
        self.assertEqual(backup["depends_on"]["groundhold"]["condition"], "service_healthy")
        self.assertNotIn("expose", backup)

    def test_the_self_host_runs_the_released_image_behind_caddy(self):
        status, config = compose_config("-f", str(SELFHOST), DOMAIN="groundhold.example.com")
        self.assertEqual(status, 0, config)
        self.assertEqual(set(config["services"]), {"groundhold", "backup", "caddy"})
        server, backup, caddy = (config["services"][name] for name in ("groundhold", "backup", "caddy"))
        for name, service in (("groundhold", server), ("backup", backup)):
            self.assert_hardened(service, name)
            self.assertEqual(service["image"], "ghcr.io/saschb2b/groundhold-server:latest")
            self.assertEqual(service["build"]["context"], "https://github.com/saschb2b/Groundhold.git#release")
            self.assertEqual(service["build"]["dockerfile"], "server/Dockerfile")
        self.assertEqual(server["environment"], {"GROUNDHOLD_SERVER_NAME": "Groundhold",
                                                 "GROUNDHOLD_SERVER_MOTD": "Hold the road together",
                                                 "GROUNDHOLD_SERVER_PLAYER_CAP": "64"})
        self.assertEqual(server["healthcheck"]["test"], image_health_check())
        self.assertEqual(backup["command"], ["--state-dir", "/data", "--backup", "/backups"])
        self.assertEqual(self.mounts(backup)["/data"], ("volume", "state", True))
        self.assertEqual(caddy["image"], "caddy:2")
        self.assertEqual(sorted((port["published"], port["target"], port.get("protocol", "tcp"))
                                for port in caddy["ports"]),
                         [("443", 443, "tcp"), ("443", 443, "udp"), ("80", 80, "tcp")], "HTTP/3 on 443/udp too")
        caddyfile = config["configs"]["caddyfile"]["content"]
        self.assertIn("groundhold.example.com {", caddyfile)
        self.assertIn("reverse_proxy groundhold:8766", caddyfile)
        self.assertIn("acme-v02.api.letsencrypt.org", caddyfile)
        # (no access log: Caddy writes one only where a site says `log`)
        self.assertNotRegex(caddyfile, r"(?m)^\s*log\b")
        status, config = compose_config("-f", str(SELFHOST), DOMAIN="groundhold.example.com", VERSION="1.2",
                                        SERVER_NAME="Flats")
        self.assertEqual(config["services"]["backup"]["image"], "ghcr.io/saschb2b/groundhold-server:1.2")
        self.assertEqual(config["services"]["groundhold"]["environment"]["GROUNDHOLD_SERVER_NAME"], "Flats")

    def test_the_self_host_needs_its_domain(self):
        status, error = compose_config("-f", str(SELFHOST))
        self.assertNotEqual(status, 0)
        self.assertIn("set DOMAIN in .env", error)
        status, error = compose_config("-f", str(SELFHOST), DOMAIN="")
        self.assertNotEqual(status, 0)


class ComposePagesTests(unittest.TestCase):
    """What server/README.md and the Compose files' comments tell a host, without Docker."""

    def test_the_readme_runs_the_tools_in_each_stacks_container(self):
        # (the self-host's container is groundhold-groundhold-1, so `docker exec groundhold` would miss it:
        # Compose's own exec names the service; Coolify's Terminal picks the container by its service)
        readme = (ROOT / "server/README.md").read_text()
        self.assertRegex(SELFHOST.read_text(), r"(?m)^  groundhold:$")
        self.assertRegex(COOLIFY.read_text(), r"(?m)^  groundhold:$")
        for command in ("docker compose exec groundhold python3 /app/groundhold-server.pyz --admin list",
                        "docker compose exec groundhold python3 /app/groundhold-server.pyz --restore /backups/",
                        "docker compose restart groundhold",
                        "python3 /app/groundhold-server.pyz --restore /backups/groundhold-state-YYYYMMDD-HHMMSS.tar.gz"):
            self.assertIn(command, readme)
        section = readme[readme.index("## Backups and restores"):readme.index("## What exists and what comes")]
        self.assertIn("**Terminal**, container `groundhold`", section)

    def test_caddys_log_is_not_said_to_hold_no_address(self):
        # (Caddy's error log carries the request, its remote address with it, for every 5xx it answers)
        for page in (SELFHOST, ROOT / "server/README.md"):
            text = re.sub(r"\s+", " ", re.sub(r"(?m)^\s*# ?", " ", page.read_text()))
            self.assertNotIn("so no player's address is written down", text, page.name)
            self.assertIn("names that request's address" if page.name == "README.md" else "names its address", text,
                          page.name)


class SettingsTests(unittest.TestCase):
    def test_the_official_servers_settings(self):
        config = configparser.ConfigParser()
        self.assertTrue(config.read(ROOT / "deploy/coolify/server.ini"))
        settings = config["server"]
        self.assertEqual(settings["name"], "Groundhold")
        for key, most in (("name", SPEC["server_name_bytes"]), ("motd", SPEC["motd_bytes"])):
            self.assertLessEqual(len(settings[key].encode()), most, key)
            self.assertTrue(settings[key].isprintable() and settings[key].isascii(), key)
        expected = {"host": "0.0.0.0", "port": "8766", "origins": "https://saschb2b.github.io", "free_text": "false",
                    "state_dir": "/data", "beacon": "false", "log_days": "0", "backup_days": "14",
                    "stats_days": "365", "maintenance": "", "allowlist": ""}
        self.assertEqual({key: settings[key] for key in expected}, expected)

    def test_the_real_program_starts_with_them(self):
        with real_server("--config", str(ROOT / "deploy/coolify/server.ini")) as port:
            answer = health(port)
        config = configparser.ConfigParser()
        config.read(ROOT / "deploy/coolify/server.ini")
        self.assertEqual((answer["name"], answer["motd"], answer["player_cap"]),
                         (config["server"]["name"], config["server"]["motd"], config["server"].getint("player_cap")))

    def test_the_env_example_names_every_setting_the_self_host_reads(self):
        used = set(re.findall(r"\$\{([A-Z_]+)", SELFHOST.read_text()))
        example = (ROOT / "deploy/selfhost/.env.example").read_text()
        documented = set(re.findall(r"(?m)^#? ?([A-Z_]+)=", example))
        self.assertEqual(used, documented)
        self.assertRegex(example, r"(?m)^DOMAIN=$")

    def test_godot_keeps_out_of_deploy(self):
        self.assertTrue((ROOT / "deploy/.gdignore").is_file())



@unittest.skipUnless(shutil.which("git") and subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--is-inside-work-tree"],
                                                          capture_output=True).returncode == 0,
                     "needs git and a checkout")
class GitIgnoreTests(unittest.TestCase):
    """A server started in a checkout writes its state there: the secret behind every public identity,
    the moderation lists and the names of who is on. None of it may ever be committed."""

    STATE = ("server-data/identity.key", "server-data/moderation.json", "server-data/players.json",
             "server-data/logs/players-2026-10-30.jsonl", "server/server-data/identity.key",
             "server-backups/groundhold-state-20261030-001500.tar.gz",
             "server/server-backups/groundhold-state-20261030-001500.tar.gz")

    def test_the_servers_state_and_backups_are_ignored(self):
        for path in self.STATE:
            result = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "--no-index", path],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, f"{path} is not ignored by .gitignore")

    def test_the_servers_sources_are_not(self):
        for path in ("server/groundhold_server/backup.py", "server/README.md", "deploy/coolify/server.ini"):
            result = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "--no-index", path],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 1, f"{path} is ignored")


if __name__ == "__main__":
    unittest.main()
