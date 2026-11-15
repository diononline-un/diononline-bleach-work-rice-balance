#!/usr/bin/env bash
# Remove rice-owned artifacts. User wallpapers and other configuration stay.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m rice.installer --uninstall "$@"
