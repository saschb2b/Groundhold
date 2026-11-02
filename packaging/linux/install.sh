#!/bin/sh
# Adds Groundhold to the desktop's application menu, with its icon, pointing at this folder (the
# tar.gz's Groundhold/). Run it again after moving the folder; ./install.sh --remove takes the entry
# and the icons away again, and the folders it left empty. Your name, Builders and settings are not
# touched either way: they live in ~/.local/share/godot/app_userdata/Groundhold/.
set -e
id=io.github.saschb2b.Groundhold
here=$(cd "$(dirname "$0")" && pwd)
share="${XDG_DATA_HOME:-$HOME/.local/share}"
apps="$share/applications"
sizes="16 24 32 48 64 128 256 512"
refresh() {
	update-desktop-database "$apps" >/dev/null 2>&1 || true
}
# (a folder left empty goes, those install.sh made with it; one with anything else in it stays)
prune() {
	for d in "$@"; do rmdir "$d" 2>/dev/null || true; done
}
if [ "$1" = --remove ]; then
	rm -f "$apps/$id.desktop"
	for s in $sizes; do
		rm -f "$share/icons/hicolor/${s}x$s/apps/$id.png"
		prune "$share/icons/hicolor/${s}x$s/apps" "$share/icons/hicolor/${s}x$s"
	done
	prune "$share/icons/hicolor" "$share/icons"
	if ls "$apps"/*.desktop >/dev/null 2>&1; then
		refresh
	else
		# (no entry left: the menu's cache update-desktop-database wrote for ours goes too)
		rm -f "$apps/mimeinfo.cache"
		prune "$apps"
	fi
	echo "Removed Groundhold from the application menu."
	exit 0
fi
if [ -n "$1" ]; then
	echo "usage: ./install.sh [--remove]" >&2
	exit 2
fi
mkdir -p "$apps"
for s in $sizes; do
	mkdir -p "$share/icons/hicolor/${s}x$s/apps"
	cp "$here/icons/$s.png" "$share/icons/hicolor/${s}x$s/apps/$id.png"
done
cat > "$apps/$id.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Groundhold
GenericName=Tower Defense
Comment=A co-op tower defense for one to four players
Exec="$here/groundhold"
Path=$here
Icon=$id
Terminal=false
Categories=Game;StrategyGame;
Keywords=tower defense;TD;co-op;multiplayer;strategy;
StartupWMClass=Groundhold
DESKTOP
refresh
echo "Added Groundhold to the application menu ($apps/$id.desktop)."
