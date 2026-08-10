#!/usr/bin/env bash
# gate_in_container.sh — run the full 199-variant example gate inside
# another distribution's container, natively.
#
# tools/glibc_sweep.sh fingerprints each distribution's libm and shows
# where they disagree. Where they do, the only way to know whether the
# disagreement is output-observable is to run the gate there. This script
# does that: it copies the workspace into a container, installs a minimal
# Rust toolchain, builds the release examples and runs
# tools/verify_examples.sh, then prints the IDENTICAL / DIFF / EXCLUDED
# tally and the list of variants that differ from the host's result.
#
#   tools/gate_in_container.sh debian:12 archlinux:latest
#
# Requires docker and network access (each container downloads rustup).
# Nothing is installed on the host and nothing is written into the
# workspace; the container gets read-only mounts and copies what it needs.
# Per-distribution summaries are written to logs/gate-<image>.txt.
set -u
cd "$(dirname "$0")/.."
WS_ROOT="$PWD"
UP="$(cd .. && pwd)"
LOGS="$WS_ROOT/logs"
mkdir -p "$LOGS"

# examples/ may be a symlink in the WSL sandbox; docker needs the real path.
EXAMPLES="$(readlink -f "$UP/examples")"
[ -d "$EXAMPLES" ] || { echo "no upstream examples/ at $UP/examples"; exit 1; }

installer() {
  case "$1" in
    debian*|ubuntu*) echo 'export DEBIAN_FRONTEND=noninteractive; apt-get -qq update >/dev/null && apt-get -qq install -y gcc curl ca-certificates diffutils >/dev/null' ;;
    fedora*)         echo 'dnf -y -q install gcc curl diffutils >/dev/null' ;;
    archlinux*)      echo 'pacman -Sy --noconfirm --quiet gcc curl diffutils >/dev/null' ;;
    *)               echo 'true' ;;
  esac
}

for image in "$@"; do
  tag="${image//[:\/]/-}"
  echo "=== $image ==="
  docker run --rm \
    -v "$WS_ROOT:/src:ro" -v "$EXAMPLES:/w/examples:ro" \
    "$image" bash -c "
      set -e
      $(installer "$image")
      curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --no-modify-path >/dev/null
      export PATH=\$HOME/.cargo/bin:\$PATH
      mkdir -p /w/port
      cp -r /src/. /w/port/
      rm -rf /w/port/target /w/port/logs /w/port/.git
      cd /w/port
      for f in tools/*.sh; do sed -i 's/\r\$//' \"\$f\"; done
      echo \"--- \$(ldd --version 2>/dev/null | head -1) / \$(rustc -V) ---\"
      cargo build --workspace 2>&1 | grep -E '^(warning|error)' | head -20 || true
      bash tools/verify_examples.sh all >/dev/null 2>&1 || true
      echo 'IDENTICAL:' \$(grep -c 'IDENTICAL\$' logs/summary.txt)
      echo 'DIFF:     ' \$(grep -c 'DIFF(' logs/summary.txt)
      echo 'EXCLUDED: ' \$(grep -c 'EXCLUDED' logs/summary.txt)
      echo 'FAIL:     ' \$(grep -c 'FAIL(' logs/summary.txt)
      echo '--- variants reported DIFF here ---'
      grep 'DIFF(' logs/summary.txt | awk '{print \$1, \$2}' | sort
    " 2>&1 | tee "$LOGS/gate-$tag.txt"
  echo
done
