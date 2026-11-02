#!/bin/sh
# appimagetool and the AppImage runtime for the Linux release's AppImage (tools/release/pack_linux.py),
# pinned by version and SHA-256, as Cyberworld Endless pins them. The runtime is the static type-2 one:
# the AppImage starts without libfuse2 on the player's system, and with APPIMAGE_EXTRACT_AND_RUN=1
# where there is no FUSE at all (containers, CI). appimagetool is itself an AppImage, unpacked here,
# since a container has no FUSE either. https://github.com/AppImage
set -e
TOOL_VER=1.9.1
TOOL_SHA=ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0
RUNTIME_VER=20251108
RUNTIME_SHA=2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d
mkdir -p /opt/appimage
cd /opt/appimage
curl -fsSL -o appimagetool.AppImage "https://github.com/AppImage/appimagetool/releases/download/$TOOL_VER/appimagetool-x86_64.AppImage"
echo "$TOOL_SHA  appimagetool.AppImage" | sha256sum -c -
curl -fsSL -o runtime-x86_64 "https://github.com/AppImage/type2-runtime/releases/download/$RUNTIME_VER/runtime-x86_64"
echo "$RUNTIME_SHA  runtime-x86_64" | sha256sum -c -
chmod +x appimagetool.AppImage
./appimagetool.AppImage --appimage-extract >/dev/null
mv squashfs-root appimagetool
rm appimagetool.AppImage
ln -s /opt/appimage/appimagetool/AppRun /usr/local/bin/appimagetool
chmod -R a+rX /opt/appimage
