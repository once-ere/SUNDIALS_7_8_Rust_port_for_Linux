#!/usr/bin/env bash
# vendor_evidence.sh — copy a measurement run from the working repository
# that produced it into this one, under evidence/<host-slug>/.
#
#     tools/vendor_evidence.sh <source-repo> <host-slug>
#     tools/vendor_evidence.sh ../SUNDIALS_7_8_Rust_port_for_Linux_on_ubuntu ubuntu-2604-glibc243
#
# The C-vs-Rust pipeline (c_build.sh, c_examples_run.sh, rust_examples_run.sh,
# compare_results.py, make_reports.py) writes c-results/, rust-results/ and
# differences/ at the root of whatever repository it runs in. Those are one
# machine's numbers, so they are filed here under the host that produced them
# rather than at the root, alongside evidence/linux-x86_64-glibc239/.
#
# Moving them down two directory levels breaks the relative links that pointed
# at the source repository's root, so those are rewritten. Nothing else is
# touched: .stdout, .stderr, .meta and the .tsv indexes are copied byte for
# byte, and the script fails if any of them changes.
set -euo pipefail

SRC=${1:?usage: vendor_evidence.sh <source-repo> <host-slug>}
SLUG=${2:?usage: vendor_evidence.sh <source-repo> <host-slug>}
# CDPATH= is not optional: with CDPATH set in the invoking shell -- and it is
# set in at least one shell this was run from -- `cd` echoes the directory it
# landed in, so $(cd ... && pwd) captures that echo *and* pwd, giving a
# two-line $ROOT. Every path built from it then contains a newline, rsync
# happily creates the resulting directory, and the real destination is never
# written. `--` guards a path that begins with a dash.
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DEST="$ROOT/evidence/$SLUG"

case $ROOT in
  *[$'\n\t']* | "") echo "refusing to run: \$ROOT is not a single clean path" >&2; exit 1 ;;
esac

for d in c-results rust-results differences; do
  [ -d "$SRC/$d" ] || { echo "no $d in $SRC — run the pipeline there first" >&2; exit 1; }
done

mkdir -p "$DEST"
for d in c-results rust-results differences; do
  rsync -a --delete "$SRC/$d/" "$DEST/$d/"
done

# requirements.md records which optional C libraries this run could reach, and
# c-results/README.md links to it as ../requirements.md. Vendoring it beside
# the results keeps that link correct without rewriting it.
[ -f "$SRC/requirements.md" ] && cp "$SRC/requirements.md" "$DEST/requirements.md"

# The three README.md files and ATTRIBUTION.md sit at evidence/<slug>/<dir>/,
# so a link written as ../X when they lived at the source root now has to
# reach up three levels. requirements.md is excluded — it was just vendored
# one level up, which is exactly where ../ points.
python3 - "$DEST" <<'PY'
import pathlib
import re
import sys

dest = pathlib.Path(sys.argv[1])
KEEP = {"../requirements.md"}
changed = 0
for md in list(dest.glob("*/README.md")) + list(dest.glob("*/ATTRIBUTION.md")):
    text = md.read_text()

    def fix(m):
        global changed
        target = m.group(1)
        if target in KEEP or not target.startswith("../") or target.startswith("../../"):
            return m.group(0)
        changed += 1
        return "](../../../" + target[3:] + ")"

    new = re.sub(r"\]\((\.\./[^)]+)\)", fix, text)
    if new != text:
        md.write_text(new)
print(f"rewrote {changed} root-relative link(s) for the new depth")
PY

# Every link must resolve from where the file now lives; a vendored evidence
# tree with dangling references is worse than none, because it looks checked.
python3 - "$DEST" <<'PY'
import pathlib
import re
import sys

dest = pathlib.Path(sys.argv[1])
root = dest.parent.parent
ok = bad = 0
for md in sorted(dest.rglob("*.md")):
    for _text, target in re.findall(r"\[([^\]]*)\]\(([^)]+)\)", md.read_text()):
        if target.startswith(("http://", "https://", "#")):
            continue
        t = re.sub(r":\d+$", "", target.split("#")[0])
        if (md.parent / t).exists():
            ok += 1
        else:
            bad += 1
            print(f"  BROKEN  {md.relative_to(root)}  ->  {target}")
print(f"{ok} links resolve, {bad} broken")
sys.exit(1 if bad else 0)
PY

echo "vendored $(find "$DEST" -type f | wc -l) files into evidence/$SLUG"
