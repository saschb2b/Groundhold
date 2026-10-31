#!/usr/bin/env python3
"""The official server deploys on release tags, never on a push to main (design 6.11, 6.13):
release.yml's last job moves the `release` branch, which the Coolify app tracks, to the tagged
commit, then asks Coolify to deploy it.

    python3 tools/release/deploy.py push <commit> --tag vX.Y.Z [--newest-only]
                                     # git push --force origin <commit>:refs/heads/release
    python3 tools/release/deploy.py coolify
                                     # GET $COOLIFY_API_URL/api/v1/deploy?uuid=$COOLIFY_APP_UUID&force=false
                                     # with Authorization: Bearer $COOLIFY_TOKEN
    python3 tools/release/deploy.py newest vX.Y.Z
                                     # latest=true|false, minor=true|false (server-image.yml)

`push` forces, so a release of an older tag by hand (a rollback by workflow_dispatch) moves the
branch back. With `--newest-only`, which a tag push passes, it moves only to the newest release:
two tags pushed close together release in parallel, and the older one's deploy, should it come
last, must not take the official server back. It asks the remote for its tags at that moment
(`git ls-remote --tags`, which a shallow checkout can do) and, when a higher vX.Y.Z than `--tag`
is there, leaves the branch where it is with a notice. Either way it writes `moved=true|false` to
$GITHUB_OUTPUT, and the workflow asks Coolify only after a move.

`newest` answers the same question for the image's moving tags: `latest` only for the newest
release, `X.Y` only for the newest of its X.Y (a 1.0.5 after 1.1.0 moves `1.0`, not `latest`).

`coolify` reads three settings from the environment, the repository's secrets in the workflow
(server/README.md, Deploy on a release tag):

- COOLIFY_API_URL: the Coolify instance, https://coolify.example.com (a trailing / or /api/v1 is
  accepted; plain http:// only for this computer, 127.0.0.1 or localhost, so the token never
  travels unencrypted);
- COOLIFY_TOKEN: an API token of that instance with the deploy permission;
- COOLIFY_APP_UUID: the app's UUID (its page's address in Coolify ends in it).

Without any of them it prints a notice and succeeds (the branch moved; Coolify deploys it by its
own Auto Deploy, or by its Deploy button); with only some it fails, as a setup half done; with all
three it fails unless Coolify answers 2xx with a deployment queued (deployments[].deployment_uuid,
as Coolify v4 answers). A redirect is not followed (urllib would send the token on to wherever it
points) but fails. It never prints the token or the instance's address. Standard library only.
"""

import argparse
import json
import os
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

SECRETS = ("COOLIFY_API_URL", "COOLIFY_TOKEN", "COOLIFY_APP_UUID")
COMMIT = re.compile(r"[0-9a-f]{40}")
TAG = re.compile(r"v(\d+)\.(\d+)\.(\d+)")


def release_tags(remote: str, repo: str):
    """The remote's release tags vX.Y.Z as they are now, by version; None when it cannot be asked."""
    done = subprocess.run(["git", "ls-remote", "--tags", remote, "refs/tags/v*"], cwd=repo, check=False,
                          capture_output=True, text=True)
    if done.returncode != 0:
        print(done.stderr.strip(), file=sys.stderr)
        return None
    found = {}
    for line in done.stdout.splitlines():
        name = line.split("\t", 1)[-1].removeprefix("refs/tags/").removesuffix("^{}")
        version = parse(name)
        if version is not None:
            found[name] = version
    return found


def parse(tag: str):
    match = TAG.fullmatch(tag)
    return tuple(int(part) for part in match.groups()) if match else None


def newer_than(tag: str, tags) -> list[str]:
    """The tags among `tags` above `tag`, highest first."""
    mine = parse(tag)
    return sorted((name for name, version in tags.items() if version > mine), key=tags.get, reverse=True)


def output(environ, **values) -> None:
    """Step outputs, where the workflow gave a file for them."""
    if environ.get("GITHUB_OUTPUT"):
        with open(environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            for key, value in values.items():
                stream.write(f"{key}={value}\n")


def push(commit: str, remote: str, branch: str, repo: str, tag: str = "", newest_only: bool = False,
         environ=None) -> int:
    environ = {} if environ is None else environ
    if not COMMIT.fullmatch(commit):
        print(f"::error title=Deploy::{commit!r} is not a full commit id", file=sys.stderr)
        return 1
    if (tag or newest_only) and parse(tag) is None:
        print(f"::error title=Deploy::{tag!r} is not a release tag vX.Y.Z", file=sys.stderr)
        return 1
    ref = f"refs/heads/{branch}"
    if newest_only:
        tags = release_tags(remote, repo)
        if tags is None:
            print(f"::error title=Deploy::cannot list {remote}'s tags to see whether {tag} is the newest",
                  file=sys.stderr)
            return 1
        above = newer_than(tag, tags)
        if above:
            print(f"::notice title=Deploy::{tag} is not the newest release ({above[0]} is): {ref} stays where "
                  f"it is, and Coolify is not asked. Run the Release workflow by hand with {tag} to roll back.")
            output(environ, moved="false")
            return 0
    done = subprocess.run(["git", "push", "--force", remote, f"{commit}:{ref}"], cwd=repo, check=False)
    if done.returncode != 0:
        print(f"::error title=Deploy::git push of {commit[:12]} to {ref} failed", file=sys.stderr)
        return 1
    print(f"{remote} {ref} is now {commit}" + (f" ({tag})" if tag else ""))
    output(environ, moved="true")
    return 0


def newest(tag: str, remote: str, repo: str, environ) -> int:
    """Whether `tag` is the newest release (latest) and the newest of its X.Y (minor)."""
    mine = parse(tag)
    if mine is None:
        print(f"::notice title=Image::{tag!r} is not a release tag vX.Y.Z: neither latest nor X.Y")
        output(environ, latest="false", minor="false")
        return 0
    tags = release_tags(remote, repo)
    if tags is None:
        print(f"::error title=Image::cannot list {remote}'s tags to see whether {tag} is the newest", file=sys.stderr)
        return 1
    above = newer_than(tag, tags)
    same_minor = [name for name in above if tags[name][:2] == mine[:2]]
    latest, minor = not above, not same_minor
    print(f"{tag}: latest {'yes' if latest else 'no (' + above[0] + ')'}, "
          f"{mine[0]}.{mine[1]} {'yes' if minor else 'no (' + same_minor[0] + ')'}")
    output(environ, latest=str(latest).lower(), minor=str(minor).lower())
    return 0


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect answered as the error it is: urllib would resend the Authorization header to it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102 (urllib's hook)
        return None


def _unnamed(reason, parts) -> str:
    """Why a request got no answer, without the instance's address: GitHub masks the secret
    whole, and a TLS error (a hostname mismatch) or a socket's names its host alone."""
    if isinstance(reason, ssl.SSLError):
        return "a TLS error (the certificate, or the protocol)"
    text = str(reason)
    for name in sorted({parts.netloc, parts.hostname or ""} - {""}, key=len, reverse=True):
        text = text.replace(name, "***")
    return text


def coolify(environ, timeout: float) -> int:
    present = [name for name in SECRETS if environ.get(name, "").strip()]
    if not present:
        print("::notice title=Coolify::No COOLIFY_API_URL, COOLIFY_TOKEN and COOLIFY_APP_UUID secrets: the release "
              "branch moved, and Coolify deploys it by its own webhook or by hand (server/README.md)")
        return 0
    if len(present) < len(SECRETS):
        missing = ", ".join(name for name in SECRETS if name not in present)
        print(f"::error title=Coolify::{missing} missing beside {', '.join(present)}: set all three or none",
              file=sys.stderr)
        return 1
    base = environ["COOLIFY_API_URL"].strip().rstrip("/")
    if base.endswith("/api/v1"):
        base = base[:-len("/api/v1")]
    parts = urllib.parse.urlsplit(base)
    local = parts.scheme == "http" and parts.hostname in ("127.0.0.1", "localhost", "::1")
    if parts.scheme != "https" and not local:
        print("::error title=Coolify::COOLIFY_API_URL must be an https:// URL (plain http:// only on this "
              "computer): the token would travel unencrypted", file=sys.stderr)
        return 1
    query = urllib.parse.urlencode({"uuid": environ["COOLIFY_APP_UUID"].strip(), "force": "false"})
    request = urllib.request.Request(f"{base}/api/v1/deploy?{query}", method="GET", headers={
        "Authorization": "Bearer " + environ["COOLIFY_TOKEN"].strip(), "Accept": "application/json",
        "User-Agent": "groundhold-release"})
    try:
        with urllib.request.build_opener(_NoRedirect).open(request, timeout=timeout) as response:
            status, body = response.status, response.read(65536)
    except urllib.error.HTTPError as exc:
        status, body = exc.code, exc.read(65536)
    except (urllib.error.URLError, OSError) as exc:
        print(f"::error title=Coolify::no answer from the Coolify instance (COOLIFY_API_URL): "
              f"{_unnamed(exc.reason if isinstance(exc, urllib.error.URLError) else exc, parts)}", file=sys.stderr)
        return 1
    text = body.decode("utf-8", "replace").replace(environ["COOLIFY_TOKEN"].strip(), "***")
    if not 200 <= status < 300:
        moved = " (a redirect, not followed: COOLIFY_API_URL should be the instance's own address)" \
            if 300 <= status < 400 else ""
        print(f"::error title=Coolify::the deploy API answered {status}{moved}: {text[:500]}", file=sys.stderr)
        return 1
    try:
        started = [d["deployment_uuid"] for d in json.loads(text).get("deployments") or []
                   if isinstance(d, dict) and d.get("deployment_uuid")]
    except (ValueError, AttributeError, TypeError):
        started = []
    if not started:
        print(f"::error title=Coolify::Coolify queued no deployment: {text[:500]}", file=sys.stderr)
        return 1
    print(f"Coolify queued deployment {', '.join(started)}")
    return 0


def main(argv=None, environ=None) -> int:
    environ = os.environ if environ is None else environ
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("push", help="move the release branch to a commit")
    one.add_argument("commit")
    one.add_argument("--tag", default="", help="the release tag vX.Y.Z of the commit")
    one.add_argument("--newest-only", action="store_true",
                     help="move it only when --tag is the remote's newest release tag (a tag push)")
    one.add_argument("--remote", default="origin")
    one.add_argument("--branch", default="release")
    one.add_argument("--repo", default=".", help="the checkout to push from")
    two = sub.add_parser("coolify", help="ask Coolify to deploy the app")
    two.add_argument("--timeout", type=float, default=60)
    three = sub.add_parser("newest", help="whether a release tag is the newest, and the newest of its X.Y")
    three.add_argument("tag")
    three.add_argument("--remote", default="origin")
    three.add_argument("--repo", default=".")
    args = parser.parse_args(argv)
    if args.command == "push":
        return push(args.commit, args.remote, args.branch, args.repo, args.tag, args.newest_only, environ)
    if args.command == "newest":
        return newest(args.tag, args.remote, args.repo, environ)
    return coolify(environ, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
