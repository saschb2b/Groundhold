"""What a release depends on, read from the files themselves: the export presets (three desktop
presets beside Web, the data and contract files in, the server, deploy files, tests and packaging out,
the brand's icon and the game's id in the Windows exe and the macOS app, macOS universal and left for
the Mac to sign), and release.yml and pages.yml as GitHub would run them (the gate before any build,
every job on the gate's commit, every preset it exports and template it needs, each package made in
the packaging image or on the Mac and started or opened there, the server's workflows by path with the
inputs they declare, the artifacts the release downloads, the deploy last, Pages numbering its build
and publishing the policy page); and across the repository, that the pages
which tell players what to download name the release's own files, and the self-host pulls the image
the release pushes, the pages that tell hosts who reaches their server keep to what the browser
build can do, and the build commands they give work in a fresh clone. A workflow file is read with
PyYAML; those tests are skipped where it is not installed.

    python3 -m unittest discover -s tools/release -t tools/release
"""

import configparser
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile

import assemble
import deploy as deploy_tool
import package

ROOT = Path(__file__).resolve().parents[2]
GAME_ID = "io.github.saschb2b.Groundhold"  # the macOS bundle, the Linux packages, the installer (package.APP_ID)
# the game's files, by the job that makes them
LINUX_AND_WINDOWS = [name for name in assemble.GAME if name != assemble.MACOS_DMG]
try:
    import yaml
except ImportError:  # (the release's own runner has it; the tests below say so when skipped)
    yaml = None


def presets() -> dict[str, dict]:
    """export_presets.cfg's presets by name: their own keys and their options, unquoted."""
    cfg = configparser.ConfigParser(interpolation=None, delimiters=("=",), comment_prefixes=(";",), strict=False)
    cfg.optionxform = str
    cfg.read(ROOT / "export_presets.cfg", encoding="utf-8")
    out = {}
    for section in cfg.sections():
        if re.fullmatch(r"preset\.\d+", section):
            unquote = lambda v: v[1:-1] if len(v) >= 2 and v[0] == v[-1] == '"' else v  # noqa: E731
            own = {k: unquote(v) for k, v in cfg[section].items()}
            own["options"] = {k: unquote(v) for k, v in cfg[section + ".options"].items()}
            out[own["name"]] = own
    return out


def filters(text: str) -> set[str]:
    return {part.strip() for part in text.split(",") if part.strip()}


def workflow(name: str) -> dict:
    data = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
    data["on"] = data.pop(True, data.get("on"))  # (YAML 1.1 reads the key `on` as true)
    return data


def runs(job: dict) -> str:
    return "\n".join(str(step.get("run", "")) for step in job.get("steps", []))


class PresetsTest(unittest.TestCase):
    def test_web_and_the_three_desktop_presets(self):
        found = presets()
        self.assertEqual({name: p["platform"] for name, p in found.items()},
                         {"Web": "Web", "Linux": "Linux", "Windows": "Windows Desktop", "macOS": "macOS"})

    def test_every_preset_ships_the_data_and_contracts_and_nothing_else(self):
        for name, preset in presets().items():
            include, exclude = filters(preset["include_filter"]), filters(preset["exclude_filter"])
            self.assertTrue({"data/*.json", "shared/net/*.json", "data/*.txt"} <= include, name)
            self.assertTrue({"server/*", "deploy/*", "tests/*", "tools/*", "docs/*", "art_src/*", "packaging/*",
                             "shared/net/transcripts/*"} <= exclude, name)

    def test_desktop_builds_are_single_files_where_they_can_be(self):
        found = presets()
        self.assertEqual(found["Linux"]["options"]["binary_format/architecture"], "x86_64")
        self.assertEqual(found["Windows"]["options"]["binary_format/architecture"], "x86_64")
        for name in ("Linux", "Windows"):
            self.assertEqual(found[name]["options"]["binary_format/embed_pck"], "true", name)

    def test_macos_is_universal_with_the_games_id_and_left_for_the_mac_to_sign(self):
        mac = presets()["macOS"]["options"]
        self.assertEqual(mac["binary_format/architecture"], "universal")
        # (Godot signs nothing: the macOS job signs the app ad hoc with Apple's codesign, pack_macos.py)
        self.assertEqual(mac["codesign/codesign"], "0")
        self.assertEqual(mac["notarization/notarization"], "0", "notarisation off")
        self.assertEqual(mac["application/bundle_identifier"], GAME_ID)
        self.assertEqual(mac["application/icon"], "res://packaging/icons/groundhold.icns")
        self.assertTrue((ROOT / "packaging/icons/groundhold.icns").is_file())
        plist = mac["application/additional_plist_content"]
        self.assertIn("<key>LSMinimumSystemVersion</key><string>10.13</string>", plist)
        self.assertEqual(mac["application/min_macos_version_x86_64"], "10.13", "the lowest of the two")
        self.assertIn("<key>NSLocalNetworkUsageDescription</key>", plist, "macOS 15 asks before Nearby looks")
        self.assertEqual(mac["display/high_res"], "true", "NSHighResolutionCapable")
        self.assertEqual(mac["application/app_category"], "Games")
        project = (ROOT / "project.godot").read_text(encoding="utf-8")
        self.assertIn("textures/vram_compression/import_etc2_astc=true", project,
                      "Godot exports universal (arm64) macOS only with ETC2/ASTC imported")

    def test_windows_carries_the_icon_and_version_and_is_unsigned(self):
        win = presets()["Windows"]["options"]
        self.assertEqual(win["codesign/enable"], "false")
        # (Godot 4.7 rewrites the exe's resources itself, on any system: no rcedit, no Wine)
        self.assertEqual(win["application/modify_resources"], "true")
        self.assertEqual(win["application/icon"], "res://packaging/icons/groundhold.ico")
        self.assertTrue((ROOT / "packaging/icons/groundhold.ico").is_file())
        for key in ("application/file_version", "application/product_version"):
            self.assertEqual(win[key], "", f"{key}: empty, so project.godot's config/version (pe_resources.py)")
        self.assertEqual(win["application/product_name"], "Groundhold")
        self.assertEqual(win["application/company_name"], "Sascha Becker")


@unittest.skipIf(yaml is None, "needs PyYAML")
class ReleaseWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.flow = workflow("release.yml")
        self.jobs = self.flow["jobs"]

    def needs(self, name):
        needs = self.jobs[name].get("needs", [])
        return set(needs if isinstance(needs, list) else [needs])

    def test_a_tag_publishes_and_a_run_by_hand_is_a_dry_run(self):
        self.assertEqual(self.flow["on"]["push"], {"tags": ["v*"]})
        inputs = self.flow["on"]["workflow_dispatch"]["inputs"]
        self.assertFalse(inputs["tag"].get("required", False), "no tag: a dry run of the branch")
        self.assertIs(inputs["dry_run"]["default"], True)
        self.assertEqual(self.flow["permissions"], {"contents": "read"})
        self.assertEqual(self.flow["defaults"]["run"]["shell"], "bash")

    def test_the_gate_comes_before_everything(self):
        gate = self.jobs["gate"]
        text = runs(gate)
        self.assertLess(text.index("tools/release/gate.py plan"), text.index('tools/release/gate.py check "v$VERSION"'))
        self.assertIn("python3 -m unittest discover -s tools/release -t tools/release", text)
        plan = next(step for step in gate["steps"] if step.get("id") == "plan")
        self.assertEqual(set(plan["env"]), {"EVENT", "REF_TYPE", "REF_NAME", "INPUT_TAG", "INPUT_DRY_RUN"})
        self.assertIn("refs/tags/", gate["steps"][0]["with"]["ref"], "a tag is checked out as a tag")
        self.assertEqual(set(gate["outputs"]), {"tag", "version", "publish", "sha", "build_seq"})
        for name in self.jobs:
            if name != "gate":
                self.assertIn("gate", self.needs(name), name)

    def test_every_job_builds_the_gates_commit(self):
        for name, job in self.jobs.items():
            if name == "gate":
                continue
            ref = job["with"]["ref"] if "uses" in job else job["steps"][0]["with"]["ref"]
            self.assertEqual(ref, "${{ needs.gate.outputs.sha }}", name)

    def test_the_desktop_job_exports_every_desktop_preset_with_the_templates_it_needs(self):
        text = runs(self.jobs["desktop"])
        exported = re.findall(r'--export-release "([^"]+)"', text)
        self.assertEqual(exported, ["Linux", "Windows", "macOS"])
        self.assertTrue(set(exported) <= set(presets()))
        for template in ("linux_release.x86_64", "windows_release_x86_64.exe", "macos.zip", "version.txt"):
            self.assertIn("templates/" + template, text)
        self.assertIn("desktop_smoke.py build/desktop/linux/groundhold.x86_64", text)
        self.assertLess(text.index("stamp.py build-json"), text.index("--export-release"))

    def test_the_desktop_job_packs_in_the_packaging_image_and_starts_each_package(self):
        text = runs(self.jobs["desktop"])
        # (the icon and version Godot writes into the exe, read before anything is packed)
        self.assertIn("pe_resources.py build/desktop/windows/Groundhold.exe --icon packaging/icons/groundhold.ico "
                      '--version "$VERSION"', text)
        self.assertIn("docker build -t groundhold-packaging packaging", text)
        self.assertIn('docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:/src" -w /src groundhold-packaging', text)
        self.assertEqual(re.findall(r'"\$\{pack\[@\]\}" (\w+) build/desktop/\w+ --version "\$VERSION" --out dist', text),
                         ["windows", "linux"])
        self.assertLess(text.index("docker build"), text.index('"${pack[@]}" windows'))
        for check in ("file dist/groundhold-windows-x64-setup.exe | tee /dev/stderr | grep -q 'Nullsoft Installer'",
                      "pe_resources.py dist/groundhold-windows-x64-setup.exe",
                      "unzip -l dist/groundhold-windows-x64.zip",
                      "readelf -p .upd_info dist/groundhold-x86_64.AppImage",
                      "'gh-releases-zsync|saschb2b|Groundhold|latest|groundhold-x86_64.AppImage.zsync'",
                      "test -s dist/groundhold-x86_64.AppImage.zsync",
                      "APPIMAGE_EXTRACT_AND_RUN=1 python3 tools/release/desktop_smoke.py dist/groundhold-x86_64.AppImage",
                      "dpkg-deb -I dist/groundhold_amd64.deb",
                      'dpkg-deb -x dist/groundhold_amd64.deb "$RUNNER_TEMP/deb"',
                      'desktop_smoke.py "$RUNNER_TEMP/deb/usr/bin/groundhold"',
                      "tar -xvzf dist/groundhold-linux-x64.tar.gz",
                      'desktop_smoke.py "$RUNNER_TEMP/tar/Groundhold/groundhold"'):
            self.assertIn(check, text)
        boots = re.findall(r'desktop_smoke\.py (\S+) --build-seq "\$BUILD_SEQ"', text)
        self.assertEqual(len(boots), 4, f"the export, the AppImage, the .deb's and the tar.gz's game: {boots}")
        upload = [s["with"] for s in self.jobs["desktop"]["steps"] if s.get("uses", "").startswith("actions/upload-artifact")]
        self.assertEqual(upload[0]["name"], "game-desktop")
        self.assertEqual(upload[0]["path"].split(), [f"dist/{name}" for name in LINUX_AND_WINDOWS])
        self.assertEqual(upload[1], {"name": "macos-export", "path": "build/desktop/macos/Groundhold.zip",
                                     "if-no-files-found": "error", "retention-days": 3})

    def test_the_macos_job_signs_packs_and_checks_on_a_mac(self):
        job = self.jobs["macos"]
        self.assertEqual(job["runs-on"], "macos-15")
        self.assertEqual(GAME_ID, package.APP_ID)
        self.assertEqual(self.needs("macos"), {"gate", "desktop"})
        download = next(s["with"] for s in job["steps"] if s.get("uses", "").startswith("actions/download-artifact"))
        self.assertEqual(download, {"name": "macos-export", "path": "build/desktop/macos"})
        text = runs(job)
        self.assertIn('package.py macos build/desktop/macos/Groundhold.zip --version "$VERSION" --out dist', text)
        for check in ('lipo -archs "$bin"', '*" x86_64 "*', '*" arm64 "*', 'codesign --verify --deep --strict',
                      "plutil -extract CFBundleIdentifier raw", f"= {package.APP_ID}",
                      "plutil -extract LSMinimumSystemVersion raw",
                      'desktop_smoke.py "$bin" --build-seq "$BUILD_SEQ"', "hdiutil verify dist/groundhold-macos.dmg",
                      'test -L "$RUNNER_TEMP/dmg/Applications"', 'test -s "$RUNNER_TEMP/dmg/Read me.txt"'):
            self.assertIn(check, text)
        self.assertLess(text.index("package.py macos"), text.index("hdiutil verify"))
        upload = next(s["with"] for s in job["steps"] if s.get("uses", "").startswith("actions/upload-artifact"))
        self.assertEqual((upload["name"], upload["path"]), ("game-macos", f"dist/{assemble.MACOS_DMG}"))

    def test_godot_and_its_templates_are_checked_before_they_are_unpacked(self):
        # (the step itself, in bash, with a curl that serves files from a folder: right sums pass,
        # a changed byte or a file the sums do not list fails before anything is unpacked)
        steps = self.jobs["desktop"]["steps"]
        cache = next(step for step in steps if step.get("id") == "godot")
        self.assertIn("sha512", cache["with"]["key"], "a cache from before the check is never used")
        step = next(step for step in steps if "SHA512-SUMS.txt" in str(step.get("run", "")))
        version = self.flow["env"]["GODOT_VERSION"]
        editor, templates = f"Godot_v{version}-stable_linux.x86_64.zip", f"Godot_v{version}-stable_export_templates.tpz"

        def run(tamper=None, listed=(editor, templates)):
            root = Path(tempfile.mkdtemp(prefix="groundhold-godot-"))
            self.addCleanup(shutil.rmtree, root, True)
            served, home, tools = root / "served", root / "home", root / "bin"
            for folder in (served, home, tools):
                folder.mkdir()
            with zipfile.ZipFile(served / editor, "w") as archive:
                archive.writestr(f"Godot_v{version}-stable_linux.x86_64", b"godot")
            with zipfile.ZipFile(served / templates, "w") as archive:
                for name in ("linux_release.x86_64", "windows_release_x86_64.exe", "macos.zip", "version.txt",
                             "web_release.zip"):
                    archive.writestr("templates/" + name, name.encode())
            sums = "".join(f"{hashlib.sha512((served / name).read_bytes()).hexdigest()}  {name}\n" for name in listed)
            (served / "SHA512-SUMS.txt").write_text(sums + "0" * 128 + "  Godot_other.zip\n")
            if tamper:
                with open(served / tamper, "ab") as stream:
                    stream.write(b"\0")
            curl = tools / "curl"
            curl.write_text('#!/bin/bash\nwhile [ $# -gt 0 ]; do case "$1" in -o) out="$2"; shift 2;; -*) shift;; '
                            '*) url="$1"; shift;; esac; done\ncp "$SERVED/${url##*/}" "$out"\n')
            curl.chmod(0o755)
            env = dict(os.environ, HOME=str(home), SERVED=str(served), GODOT_VERSION=version,
                       PATH=f"{tools}{os.pathsep}{os.environ['PATH']}")
            done = subprocess.run(["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", step["run"]],
                                  env=env, capture_output=True, text=True, timeout=60)
            return done, home / "godot"

        done, godot = run()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual((godot / "godot").read_bytes(), b"godot")
        self.assertEqual(sorted(p.name for p in (godot / "templates").iterdir()),
                         ["linux_release.x86_64", "macos.zip", "version.txt", "windows_release_x86_64.exe"])
        for case in ({"tamper": editor}, {"tamper": templates}, {"listed": (editor,)}):
            done, godot = run(**case)
            self.assertNotEqual(done.returncode, 0, case)
            self.assertFalse((godot / "godot").exists(), f"{case}: unpacked before the check")
            self.assertFalse((godot / "templates").exists(), case)

    def test_the_server_workflows_by_path_with_the_inputs_they_declare(self):
        self.assertEqual(self.jobs["server-native"]["uses"], "./.github/workflows/server-native.yml")
        self.assertEqual(self.jobs["server-image"]["uses"], "./.github/workflows/server-image.yml")
        self.assertEqual(self.jobs["server-image"]["permissions"]["packages"], "write")
        self.assertEqual(self.jobs["server-image"]["with"]["push"], "${{ needs.gate.outputs.publish == 'true' }}")
        for name in ("server-native", "server-image"):
            called = workflow(self.jobs[name]["uses"].rsplit("/", 1)[1])["on"]["workflow_call"]["inputs"]
            given = self.jobs[name]["with"]
            self.assertTrue(set(given) <= set(called), f"{name} passes an input its workflow lacks")
            self.assertTrue({key for key, spec in called.items() if spec.get("required")} <= set(given), name)
            self.assertEqual(given["version"], "${{ needs.gate.outputs.version }}", name)

    def test_the_image_is_pushed_only_once_the_release_builds(self):
        # (a tag whose export or native smoke fails publishes no release and moves no branch:
        # nor may its image become the self-hosts' `latest`; review M5 round 2)
        self.assertTrue({"gate", "desktop", "macos", "server-native"} <= self.needs("server-image"))

    def test_the_release_downloads_what_the_jobs_upload(self):
        native = workflow("server-native.yml")["jobs"]["native"]
        upload = next(s for s in native["steps"] if s.get("uses", "").startswith("actions/upload-artifact"))
        self.assertEqual(upload["with"]["name"], "server-${{ matrix.target }}")
        self.assertEqual(upload["with"]["path"], "build/release/groundhold-server-*.zip")
        downloads = [s["with"] for s in self.jobs["publish"]["steps"]
                     if s.get("uses", "").startswith("actions/download-artifact")]
        self.assertIn({"pattern": "server-*", "merge-multiple": True, "path": "dist"}, downloads)
        uploaded = set()
        for job in ("desktop", "macos"):
            game = next(s["with"] for s in self.jobs[job]["steps"] if s.get("uses", "").startswith("actions/upload-artifact"))
            self.assertIn({"name": game["name"], "path": "dist"}, downloads, job)
            uploaded |= {Path(path).name for path in game["path"].split()}
        self.assertEqual(uploaded, set(assemble.GAME), "every game file reaches the release")
        self.assertNotIn("macos-export", {d.get("name") for d in downloads}, "the export is no file of a release")

    def test_the_release_carries_the_notes_and_every_file(self):
        publish = self.jobs["publish"]
        self.assertEqual(self.needs("publish"), {"gate", "desktop", "macos", "server-native"})
        self.assertEqual(publish["permissions"]["contents"], "write")
        text = runs(publish)
        self.assertIn("tools/release/assemble.py dist --list files.txt", text)
        self.assertIn('release_notes.py "v$VERSION" --dist dist > NOTES.md', text)
        self.assertIn('release_notes.py "v$VERSION" --title > TITLE.txt', text)
        self.assertLess(text.index("assemble.py dist"), text.index("--dist dist"), "the sums before the notes")
        self.assertIn('gh release create "$TAG" --verify-tag --title "$title"', text)
        self.assertIn('gh release edit "$TAG" --title "$title"', text)
        step = next(s for s in publish["steps"] if "gh release create" in str(s.get("run", "")))
        self.assertEqual(step["if"], "needs.gate.outputs.publish == 'true'")
        kept = next(s for s in publish["steps"] if s.get("with", {}).get("name") == "release-dry-run")
        self.assertEqual(kept["if"], "needs.gate.outputs.publish != 'true'")

    def test_the_deploy_is_last_and_moves_the_release_branch(self):
        deploy = self.jobs["deploy"]
        others = set(self.jobs) - {"deploy"}
        # (everything else is upstream of the deploy: it needs each job, or a job that needs it)
        upstream = set(self.needs("deploy"))
        for name in self.needs("deploy"):
            upstream |= self.needs(name)
        self.assertEqual(upstream, others)
        self.assertEqual(deploy["permissions"], {"contents": "write"})
        self.assertEqual(deploy["if"], "needs.gate.outputs.publish == 'true'")
        self.assertIn("RELEASE_BRANCH_TOKEN", deploy["steps"][0]["with"]["token"])
        self.assertIn("github.token", deploy["steps"][0]["with"]["token"])
        text = runs(deploy)
        self.assertLess(text.index('tools/release/deploy.py push "$SHA" --tag "$TAG"'),
                        text.index("tools/release/deploy.py coolify"))
        push = next(step for step in deploy["steps"] if step.get("id") == "push")
        self.assertIn("--newest-only", push["run"], "a tag push moves the branch only to the newest release")
        self.assertEqual(push["env"], {"EVENT": "${{ github.event_name }}"})
        step = next(step for step in deploy["steps"] if "coolify" in str(step.get("run", "")))
        self.assertEqual(step["env"], {name: "${{ secrets.%s }}" % name for name in deploy_tool.SECRETS})
        self.assertEqual(step["if"], "steps.push.outputs.moved == 'true'")
        # (test_deploy.WorkflowStepsTest runs the push step itself against a bare repository)

    def test_no_job_can_hold_a_runner_for_hours(self):
        # (GitHub's default is six hours: a hung gh call or git push would keep a runner that long)
        for name, job in self.jobs.items():
            if "uses" in job:
                continue
            self.assertIn("timeout-minutes", job, name)
            self.assertLessEqual(job["timeout-minutes"], 40, name)
        for name in ("gate", "publish", "deploy"):
            self.assertLessEqual(self.jobs[name]["timeout-minutes"], 15, name)


@unittest.skipIf(yaml is None, "needs PyYAML")
class AcrossTheRepositoryTest(unittest.TestCase):
    """What players and hosts are told to download or pull is what a release makes."""

    # (any file name a page could send a player to download; a server's backup archive,
    # groundhold-state-<time>.tar.gz, and the server's program in its archive, groundhold-server.exe,
    # are no downloads)
    MENTIONED = re.compile(r"\bgroundhold[-_](?!state-|server\.)[A-Za-z0-9._-]*?"
                           r"\.(?:zip|exe|dmg|AppImage\.zsync|AppImage|deb|tar\.gz)\b")

    def test_the_pages_that_name_release_files_name_only_those(self):
        seen = set()
        for page in ("README.md", "server/README.md", "web/index.html", "web/policy.html",
                     *[f"tools/release/readme/{name}" for name in ("linux.txt", "windows.txt", "macos.txt")]):
            text = (ROOT / page).read_text(encoding="utf-8")
            for name in set(self.MENTIONED.findall(text)):
                seen.add(name)
                self.assertIn(name, assemble.FILES, f"{page} names {name}, which no release has")
        self.assertTrue(set(assemble.GAME) <= seen, "the pattern sees every kind of the game's files")

    def test_the_pattern_sees_old_and_wrong_names(self):
        text = ("groundhold-macos.zip, groundhold-linux-x64.zip, groundhold-0.6.0-linux-x86_64.zip, groundhold.dmg, "
                "groundhold-amd64.deb, groundhold-state-20261030-001500.tar.gz, groundhold-server.exe")
        self.assertEqual(self.MENTIONED.findall(text), ["groundhold-macos.zip", "groundhold-linux-x64.zip",
                                                         "groundhold-0.6.0-linux-x86_64.zip", "groundhold-amd64.deb"])

    def test_the_macos_steps_put_the_terminal_first(self):
        # (Control-click > Open and Open Anyway do not get past "is damaged"; the quarantine step does)
        for page in ("README.md", "web/index.html", "tools/release/readme/macos.txt"):
            text = (ROOT / page).read_text(encoding="utf-8")
            self.assertLess(text.index("xattr -dr com.apple.quarantine"), text.index("Control-click"), page)

    def test_the_macos_steps_reach_macos_15_and_apple_silicon(self):
        # (macOS 15 dropped Control-click > Open for an unsigned app: Open Anyway in System
        # Settings is the way without Terminal there; an ad-hoc signature the fallback on
        # Apple silicon; review M5 round 2: the site gave neither)
        for page in ("README.md", "web/index.html", "tools/release/readme/macos.txt"):
            text = " ".join((ROOT / page).read_text(encoding="utf-8").split())
            self.assertIn("Open Anyway", text, page)
            self.assertIn("codesign --force --deep --sign -", text, page)

    def test_the_readmes_name_every_file(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for name in assemble.GAME:
            self.assertTrue(name in readme, f"README.md, Play together, names no {name}")
            if name != assemble.ZSYNC:
                link = f"https://github.com/saschb2b/Groundhold/releases/latest/download/{name}"
                self.assertIn(link, readme, f"README.md links {name} on the newest release")
        self.assertIn("releases/latest", readme)
        site = (ROOT / "web/index.html").read_text(encoding="utf-8")
        for name in assemble.GAME:
            if name != assemble.ZSYNC:
                self.assertIn(f"releases/latest/download/{name}", site, f"the site links {name}")

    def test_the_engines_licence_names_the_engine_the_release_builds_with(self):
        version = workflow("release.yml")["env"]["GODOT_VERSION"]
        text = (ROOT / "packaging/licenses/Godot-Engine.txt").read_text(encoding="utf-8")
        self.assertIn(f"Godot Engine {version} ", text)
        self.assertIn(f"/blob/{version}-stable/COPYRIGHT.txt", text)
        server = (ROOT / "server/README.md").read_text(encoding="utf-8")
        for name in assemble.SERVER:
            self.assertTrue(name.removeprefix("groundhold-server") in server, f"server/README.md names no {name}")

    def test_the_self_host_pulls_the_image_the_release_pushes(self):
        image = workflow("server-image.yml")["jobs"]["image"]
        meta = next(step for step in image["steps"] if step.get("id") == "meta")
        published = meta["with"]["images"]
        compose = yaml.safe_load((ROOT / "deploy/selfhost/compose.yaml").read_text(encoding="utf-8"))
        for name in ("groundhold", "backup"):
            service = compose["services"][name]
            repository, tag = re.fullmatch(r"([^:]+):(.+)", service["image"]).groups()
            owner = re.fullmatch(r"https://github.com/([^/]+)/Groundhold\.git#release", service["build"]["context"])
            self.assertIsNotNone(owner, "the fallback builds the release branch the deploy moves")
            self.assertEqual(repository, published.replace("${{ github.repository_owner }}", owner.group(1)), name)
            self.assertEqual(tag, "${VERSION:-latest}", name)
        self.assertIn("type=raw,value=latest", meta["with"]["tags"], "latest, which the self-host pulls")
        self.assertIn("ghcr.io/saschb2b/groundhold-server", (ROOT / "server/README.md").read_text(encoding="utf-8"))


def prose(page: str) -> str:
    """A page's text with its line breaks and comment marks folded into single spaces."""
    text = (ROOT / page).read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", re.sub(r"(?m)^\s*#+ ?", " ", text))


class BrowserReachTest(unittest.TestCase):
    """The published browser game joins only the official server (design 5.3, 6.11): its Join panel
    hides the address field, and a code or a play/?join= link goes to data/net.json's server. So no
    page tells a host that browser players reach a server of their own, and the hosts' pages say how
    they can: a web build of their own, its page's origin in `origins`."""

    PAGES = ("README.md", "server/README.md", "deploy/selfhost/compose.yaml", "server/groundhold_server/hosting.py",
             "server/groundhold_server/cli.py", "docs/design/core-loop.md", "web/index.html")
    # (the promises M5's first pages made, and any like them)
    PROMISES = re.compile(r"browser players reach (?:it )?too|browser (?:can|could) reach (?:it )?too"
                          r"|browser game comes in too|browsers need wss|works from the browser too"
                          r"|browser players can use any|`?wss://`? as desktop", re.IGNORECASE)

    def test_the_web_build_hides_the_address_field(self):
        # (should the web build ever offer the field, these pages may promise browser players more)
        join = (ROOT / "scripts/ui/join_panel.gd").read_text(encoding="utf-8")
        self.assertIn('lan = not OS.has_feature("web")', join)
        self.assertIn("_nearby_box.visible = on", join)
        self.assertRegex(join, r"_address = LineEdit\.new\(\)")
        address_row = join[join.index("_address = LineEdit.new()") - 1500:join.index("_address = LineEdit.new()")]
        self.assertIn("_nearby_box", address_row, "the address field is in the box the web build hides")

    def test_no_page_promises_browser_players_a_server_of_their_own(self):
        for page in self.PAGES:
            found = self.PROMISES.search(prose(page))
            self.assertIsNone(found, f"{page}: {found and found.group(0)!r}")

    def test_the_hosts_pages_say_the_browser_joins_only_the_official_server(self):
        for page in ("README.md", "server/README.md", "deploy/selfhost/compose.yaml"):
            self.assertTrue("joins only the official server" in prose(page), page)
        for page in ("server/README.md", "deploy/selfhost/compose.yaml"):
            self.assertIn("data/net.json", prose(page), f"{page}: how browser players can come, a web build of the host's")
            self.assertIn("origins", prose(page), page)
        from_banner = (ROOT / "server/groundhold_server/hosting.py").read_text(encoding="utf-8")
        self.assertIn("the browser game joins the official server alone", from_banner)


class DocumentedCommandsTest(unittest.TestCase):
    """The build and run commands the pages give work in a fresh clone: Godot imports the project once
    before it can run or export it (no .godot/ in the repository), and makes no export folder itself."""

    PAGES = ("README.md", "AGENTS.md", "server/README.md", "tests/web/flow_join_link_through_iframe.py")
    EXPORT = re.compile(r'--export-release "?([A-Za-z]+)"? (?:"?\$PWD/)?([\w./-]+)')

    def test_every_export_makes_its_folder_first(self):
        seen = 0
        for page in self.PAGES:
            text = prose(page)
            for found in self.EXPORT.finditer(text):
                seen += 1
                folder = found.group(2).rsplit("/", 1)[0]
                before = text[max(0, found.start() - 160):found.start()]
                self.assertIn(f"mkdir -p {folder}", before, f"{page}: the {found.group(1)} export into {folder}")
        self.assertGreaterEqual(seen, 3)

    def test_the_readmes_import_before_they_run_the_game(self):
        for page in ("README.md", "server/README.md"):
            text = prose(page)
            runs = [found.start() for found in re.finditer(r"godot (?:--headless )?--path \. (?!--import)", text)]
            self.assertTrue(runs, page)
            imported = text.find("godot --headless --path . --import")
            self.assertTrue(0 <= imported < runs[0], f"{page}: the first `godot --path .` comes before an import")


@unittest.skipIf(yaml is None, "needs PyYAML")
class PagesWorkflowTest(unittest.TestCase):
    def test_the_web_build_is_numbered_by_its_run(self):
        build = runs(workflow("pages.yml")["jobs"]["build"])
        self.assertIn('stamp.py build-json --build-seq "$GITHUB_RUN_NUMBER"', build)
        self.assertIn('stamp.py shell --build-seq "$GITHUB_RUN_NUMBER" site/play/game/index.html', build)
        self.assertLess(build.index("build-json"), build.index("--export-release"), "build.json before the export")
        self.assertLess(build.index("--export-release"), build.index("stamp.py shell"), "the shell after it")

    def test_the_join_link_runs_on_the_exported_site(self):
        job = workflow("pages.yml")["jobs"]["join-link"]
        self.assertEqual(job["needs"], "build")
        self.assertIn("flow_join_link_through_iframe.py --game site/play/game", runs(job))

    def test_the_site_publishes_the_policy_page_and_links_it(self):
        build = runs(workflow("pages.yml")["jobs"]["build"])
        copy = next(line for line in build.splitlines() if "web/index.html" in line and line.strip().startswith("cp "))
        self.assertIn("web/policy.html", copy.split(), "policy.html beside index.html, at /Groundhold/policy.html")
        for page, link in (("web/index.html", 'href="policy.html"'), ("web/play/index.html", 'href="../policy.html"')):
            self.assertIn(link, (ROOT / page).read_text(encoding="utf-8"), page)
        policy = (ROOT / "web/policy.html").read_text(encoding="utf-8")
        self.assertIn('href="assets/site.css"', policy, "beside index.html, its links relative alike")


if __name__ == "__main__":
    unittest.main()
