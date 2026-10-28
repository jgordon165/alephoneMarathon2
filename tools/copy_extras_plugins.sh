#!/bin/bash
# Copies the optional plugins in Extras/Plugins into a release package's
# Extras/Plugins folder, choosing them by game.
#
#   copy_extras_plugins.sh <source-root> <package> <package-dir>
#
# <package> is AlephOne, Marathon, Marathon2 or MarathonInfinity.
# Each plugin's Plugin.xml decides where it goes: a plugin with
# <scenario name="Marathon 2"/> goes into the Marathon2 package, and so on.
# A plugin with no <scenario> tags works with any game and goes into every
# package. The AlephOne package (the engine without game data) gets every
# plugin, since it may be run with any of the games.
#
# Fails if a plugin has no Plugin.xml, names a scenario this script doesn't
# know (add it to scenario_package below), or doesn't arrive in the package.

set -euo pipefail

if [ $# -ne 3 ]; then
  echo "Usage: $0 <source-root> <AlephOne|Marathon|Marathon2|MarathonInfinity> <package-dir>" >&2
  exit 2
fi

src_root="$1"
package="$2"
package_dir="$3"
plugins_src="$src_root/Extras/Plugins"

case "$package" in
  AlephOne|Marathon|Marathon2|MarathonInfinity) ;;
  *) echo "copy_extras_plugins: unknown package '$package'" >&2; exit 2 ;;
esac

# Plugin.xml scenario name -> package name
scenario_package() {
  case "$1" in
    "Marathon") echo Marathon ;;
    "Marathon 2") echo Marathon2 ;;
    "Marathon Infinity") echo MarathonInfinity ;;
    *) return 1 ;;
  esac
}

[ -d "$plugins_src" ] || exit 0

copied=0
for plugin in "$plugins_src"/*/; do
  [ -d "$plugin" ] || continue
  plugin="${plugin%/}"
  name="$(basename "$plugin")"
  manifest="$plugin/Plugin.xml"
  if [ ! -f "$manifest" ]; then
    echo "copy_extras_plugins: $name has no Plugin.xml" >&2
    exit 1
  fi

  wanted=no
  if [ "$package" = AlephOne ]; then
    wanted=yes
  fi
  scenarios="$(grep -o '<scenario[^>]*name="[^"]*"' "$manifest" | sed 's/.*name="\([^"]*\)"/\1/' || true)"
  if [ -z "$scenarios" ]; then
    wanted=yes
  else
    while IFS= read -r scenario; do
      if ! target="$(scenario_package "$scenario")"; then
        echo "copy_extras_plugins: $name targets unknown scenario '$scenario'" >&2
        exit 1
      fi
      if [ "$target" = "$package" ]; then wanted=yes; fi
    done <<< "$scenarios"
  fi
  if [ "$wanted" != yes ]; then continue; fi

  dest="$package_dir/Extras/Plugins/$name"
  mkdir -p "$dest"
  tar -c --exclude='.svn' --exclude='.git' --exclude='__pycache__' -C "$plugin" . | tar -x -C "$dest"
  if [ ! -f "$dest/Plugin.xml" ]; then
    echo "copy_extras_plugins: $name did not arrive in $dest" >&2
    exit 1
  fi
  echo "copy_extras_plugins: $name -> $package"
  copied=$((copied + 1))
done

echo "copy_extras_plugins: $copied plugin(s) in $package"
