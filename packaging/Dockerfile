# The tools that pack the desktop game for a release (tools/release/package.py; release.yml's desktop
# job, on ubuntu, no Windows runner): NSIS's makensis for the Windows installer, appimagetool with the
# static AppImage runtime (appimage.sh, pinned), zsyncmake for the AppImage's update file, dpkg-deb, and
# the desktop-file and AppStream validators the Linux packages are checked with. Python runs package.py
# itself inside it. Built where it is used, never pushed:
#
#     docker build -t groundhold-packaging packaging
#     docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:/src" -w /src groundhold-packaging \
#         python3 tools/release/package.py linux build/desktop/linux --version 0.9.0 --out dist
FROM debian:trixie-slim
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    python3 nsis zsync file curl ca-certificates desktop-file-utils appstream \
 && rm -rf /var/lib/apt/lists/*
COPY appimage.sh /tmp/appimage.sh
RUN sh /tmp/appimage.sh && rm /tmp/appimage.sh
