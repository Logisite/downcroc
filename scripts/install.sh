#!/bin/sh
set -eu

VERSION="1.2.3"
PREFIX="${DOWNCROC_PREFIX:-$HOME/.local}"
WHEEL=""
RUN_INIT=1

usage() {
    cat <<'EOF'
install downcroc from a wheel or the package index

usage: install.sh [options]

options:
  --wheel PATH    install this .whl file
  --version VER   install a release version (default: 1.2.3)
  --prefix DIR    install under DIR (default: ~/.local)
  --no-init       do not run downcroc init
  -h, --help      show this help

environment:
  DOWNCROC_PREFIX  same as --prefix
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --wheel)
            [ $# -ge 2 ] || { echo "install.sh: --wheel needs a path" >&2; exit 2; }
            WHEEL="$2"
            shift 2
            ;;
        --version)
            [ $# -ge 2 ] || { echo "install.sh: --version needs a version" >&2; exit 2; }
            VERSION="$2"
            shift 2
            ;;
        --prefix)
            [ $# -ge 2 ] || { echo "install.sh: --prefix needs a path" >&2; exit 2; }
            PREFIX="$2"
            shift 2
            ;;
        --no-init)
            RUN_INIT=0
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "install.sh: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

PYTHON=""
for candidate in python3.14 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 14) else 1)' 2>/dev/null; then
            PYTHON="$candidate"
            break
        fi
    fi
done

case "$VERSION" in
    ""|*[!0-9A-Za-z.+_-]*)
        echo "install.sh: invalid version: $VERSION" >&2
        exit 2
        ;;
esac

case "$PREFIX" in
    /*) ;;
    *) PREFIX="$(pwd)/$PREFIX" ;;
esac

RELEASE_WHEEL="https://github.com/Logisite/downcroc/releases/download/v${VERSION}/downcroc-${VERSION}-py3-none-any.whl"

if [ -z "$PYTHON" ]; then
    echo "install.sh: Python 3.14 or newer is required" >&2
    exit 1
fi

if [ -n "$WHEEL" ] && [ ! -f "$WHEEL" ]; then
    echo "install.sh: wheel not found: $WHEEL" >&2
    exit 1
fi

VENV="$PREFIX/share/downcroc/venv"
BIN="$PREFIX/bin"

mkdir -p "$PREFIX/share/downcroc" "$BIN"
"$PYTHON" -m venv "$VENV"

if [ -n "$WHEEL" ]; then
    "$VENV/bin/python" -m pip install --upgrade "$WHEEL"
else
    SOURCE="${DOWNCROC_WHEEL_URL:-$RELEASE_WHEEL}"
    "$VENV/bin/python" -m pip install --upgrade "$SOURCE"
fi

ln -sfn "$VENV/bin/downcroc" "$BIN/downcroc"

echo
"$BIN/downcroc" --version
echo "installed  $BIN/downcroc"

case ":$PATH:" in
    *":$BIN:"*) ;;
    *) echo "add to PATH: export PATH=\"$BIN:\$PATH\"" ;;
esac

if [ "$RUN_INIT" -eq 1 ]; then
    echo "next: downcroc init"
fi
