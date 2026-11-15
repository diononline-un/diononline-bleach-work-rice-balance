#!/usr/bin/env bash
# Bootstrap the rice installer from the repository checkout.
# The installer itself performs the host preflight and package installation.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
if ! python3 -c "import tomli_w" >/dev/null 2>&1; then
    sudo pacman -S --needed --noconfirm python-tomli-w
fi
exec python3 -m rice.installer "$@"
