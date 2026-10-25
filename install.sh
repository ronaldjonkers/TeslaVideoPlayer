#!/bin/sh
# Portable bootstrap. The installer itself only uses Python's standard library.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
choose_python() {
    for candidate in ${TESLA_PYTHON:-python3 python3.13 python3.12 python3.11 python3.10 python3.9}; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' 2>/dev/null; then
            SELECTED_PYTHON=$candidate
            return 0
        fi
    done
    return 1
}
if ! choose_python; then
    case " ${*} " in *" --help "*|*" --plan "*) echo 'Python 3.9+ is required for help/plan. Install it first, or set TESLA_PYTHON.' >&2; exit 1;; esac
    [ "$(uname -s)" = Linux ] || { echo 'Automatic installation requires Linux.' >&2; exit 1; }
    [ "$(id -u)" = 0 ] || { echo 'Run with sudo sh install.sh, or install Python 3.9+ first.' >&2; exit 1; }
    if command -v apt-get >/dev/null 2>&1; then apt-get update; DEBIAN_FRONTEND=noninteractive apt-get install -y python3
    elif command -v dnf >/dev/null 2>&1; then
        dnf install -y python3
        if ! choose_python; then dnf install -y python3.11 || dnf install -y python39; fi
    elif command -v yum >/dev/null 2>&1; then
        yum install -y python3
        if ! choose_python; then yum install -y python3.11 || yum install -y python39; fi
    elif command -v zypper >/dev/null 2>&1; then zypper --non-interactive install python3
    elif command -v pacman >/dev/null 2>&1; then pacman -S --needed --noconfirm python
    elif command -v apk >/dev/null 2>&1; then apk add --no-cache python3
    elif command -v xbps-install >/dev/null 2>&1; then xbps-install -Sy python3
    elif command -v emerge >/dev/null 2>&1; then emerge --noreplace dev-lang/python
    else echo 'Unknown package manager. Install Python 3.9+, then rerun this script.' >&2; exit 1
    fi
    choose_python || { echo 'No Python 3.9+ available. Upgrade the OS/Python, set TESLA_PYTHON, or use containers.' >&2; exit 1; }
fi
exec "$SELECTED_PYTHON" "$SCRIPT_DIR/scripts/install.py" "$@"
