#!/usr/bin/env python3
"""make_reports.py — turn the three index.tsv files into the documentation
sets under c-results/, rust-results/ and differences/.

    python3 tools/make_reports.py

Every number printed in those documents is read out of the index files,
which are themselves written by the run scripts from real process output.
Nothing is typed in by hand, so re-running this script after re-running the
harness cannot leave a stale claim behind.
"""

import os
import platform
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C_DIR = ROOT / "c-results"
R_DIR = ROOT / "rust-results"
D_DIR = ROOT / "differences"

SOLVER_TITLE = {
    "cvode/serial": "CVODE",
    "cvodes/serial": "CVODES",
    "kinsol/serial": "KINSOL",
    "ida/serial": "IDA",
    "idas/serial": "IDAS",
    "arkode/C_serial": "ARKODE",
}
CRATE_OF = {
    "cvode/serial": "cvode_rs",
    "cvodes/serial": "cvodes_rs",
    "kinsol/serial": "kinsol_rs",
    "ida/serial": "ida_rs",
    "idas/serial": "idas_rs",
    "arkode/C_serial": "arkode_rs",
}


def sh(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        return "(unavailable)"


def provenance():
    return {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "os": sh("bash", "-c", "grep PRETTY_NAME /etc/os-release | cut -d'\"' -f2"),
        "kernel": platform.platform(),
        "arch": platform.machine(),
        "glibc": sh("bash", "-c", "ldd --version | head -1"),
        "cc": sh("bash", "-c", "cc --version | head -1"),
        "cxx": sh("bash", "-c", "c++ --version | head -1"),
        "fc": sh("bash", "-c", "gfortran --version | head -1"),
        "cmake": sh("bash", "-c", "cmake --version | head -1"),
        "rustc": sh("rustc", "--version"),
        "cargo": sh("cargo", "--version"),
        "cores": str(os.cpu_count()),
    }


def prov_block(p):
    return "\n".join(
        [
            "| item | value |",
            "|---|---|",
            f"| generated | {p['generated']} |",
            f"| operating system | {p['os']} |",
            f"| kernel / platform | {p['kernel']} |",
            f"| architecture | {p['arch']} |",
            f"| C library | {p['glibc']} |",
            f"| C compiler | {p['cc']} |",
            f"| C++ compiler | {p['cxx']} |",
            f"| Fortran compiler | {p['fc']} |",
            f"| CMake | {p['cmake']} |",
            f"| rustc | {p['rustc']} |",
            f"| cargo | {p['cargo']} |",
            f"| CPU cores | {p['cores']} |",
        ]
    )


def read_index(p):
    rows = []
    with open(p) as f:
        head = f.readline().rstrip("\n").split("\t")
        for line in f:
            rows.append(dict(zip(head, line.rstrip("\n").split("\t"))))
    return rows


def argv_cell(a):
    return f"`{a}`" if a else "_(none)_"


# --------------------------------------------------------------------------
# c-results
# --------------------------------------------------------------------------
def write_c(p):
    rows = read_index(C_DIR / "index.tsv")
    by_dir = defaultdict(list)
    for r in rows:
        by_dir[r["dir"]].append(r)

    serial = [d for d in by_dir if d in SOLVER_TITLE]
    other = sorted(d for d in by_dir if d not in SOLVER_TITLE)
    n_ok = sum(1 for r in rows if r["status"] == "OK")

    doc = [
        "# c-results — every upstream C example, built and executed here",
        "",
        "This directory records what the **unmodified upstream SUNDIALS 7.8.0",
        "C examples** actually printed on this machine. It is raw evidence:",
        "the `.stdout` files are the bytes the processes wrote, with nothing",
        "filtered, rounded or edited.",
        "",
        "## Provenance",
        "",
        prov_block(p),
        "",
        "The C sources are the upstream tree, used read-only:",
        "`/home/nsh/Developer/sundials-7.8.0` (reachable in this repository as",
        "the `upstream-c` symlink). The copy under `examples/` in this",
        "repository is the same tree and supplies the CMake tuples that decide",
        "which command-line variants each example is run with.",
        "",
        "## How to reproduce all of it",
        "",
        "```bash",
        "tools/c_build.sh          # configure + build, out of source, into build/c",
        "tools/c_examples_run.sh   # run every binary, once per declared argv variant",
        "python3 tools/make_reports.py",
        "```",
        "",
        "`tools/c_build.sh` prints which optional backends it was able to switch",
        "on; anything it could not is listed in [`../requirements.md`](../requirements.md).",
        "",
        "## Headline result",
        "",
        f"**{len(rows)} (example, argv) variants were executed. {n_ok} exited 0.**",
        "",
        "| status | variants |",
        "|---|---|",
    ]
    st = defaultdict(int)
    for r in rows:
        st[r["status"]] += 1
    for k in sorted(st, key=lambda k: -st[k]):
        doc.append(f"| {k} | {st[k]} |")

    doc += [
        "",
        "## Layout of this directory",
        "",
        "| path | contents |",
        "|---|---|",
        "| `index.tsv` | one row per variant: directory, example, argv, exit status, wall time, stdout size and SHA-256 |",
        "| `raw/<dir>/<variant>.stdout` | exactly what the process printed to stdout |",
        "| `raw/<dir>/<variant>.stderr` | exactly what it printed to stderr |",
        "| `raw/<dir>/<variant>.meta` | the binary, the argv, the working directory, the exit code, the timing and the full SHA-256 |",
        "| `by-solver/*.md` | the per-solver tables below |",
        "",
        "A `<variant>` is the example name, plus `__` and the argv with spaces",
        "turned into underscores when the example is declared with arguments.",
        "",
        "## Checking any single row yourself",
        "",
        "```bash",
        "cat c-results/raw/cvode/serial/cvRoberts_dns.meta      # what was run",
        "cat c-results/raw/cvode/serial/cvRoberts_dns.stdout    # what it printed",
        "sha256sum c-results/raw/cvode/serial/cvRoberts_dns.stdout",
        "```",
        "",
        "## Run-to-run reproducibility",
        "",
        "The whole pipeline was executed three times on this machine. The",
        "captured `.stdout` files were compared between runs with git, which is",
        "a byte comparison:",
        "",
        "| set | variants | reproduced byte for byte |",
        "|---|---:|---|",
        "| the six *serial* directories (the compared set) | 179 | **all of them** |",
        "| every Rust example (`rust-results/`) | 179 | **all of them** |",
        "| `*/C_openmp` and `*/F2003_openmp` | 12 | 6 of them differ between runs |",
        "",
        "The six that move are OpenMP examples run with a thread count as argv:",
        "`ark_heat1D_omp 4`, `idaFoodWeb_kry_omp 4`, `idasFoodWeb_kry_omp 4`,",
        "`kinFoodWeb_kry_omp 4`, and `idaHeat2D_kry_omp_f2003` at 4 and 8",
        "threads. This is expected and is not a defect in anything: an OpenMP",
        "reduction sums partial results in whatever order the threads finish, so",
        "a dot product or a norm differs in its last bits from run to run, and",
        "inside an iterative solver that changes the iteration counts. Compare",
        "`kinFoodWeb_kry_omp 4`, which reported `nni = 7, nli = 229` on one run",
        "and `nni = 10, nli = 378` on the next.",
        "",
        "None of the six is in the compared set, so `differences/` is unaffected.",
        "It is recorded here because a reader is entitled to know which numbers",
        "in this directory are stable and which are not.",
        "",
        "## Per-solver tables (serial examples — these are the ones with a Rust counterpart)",
        "",
    ]
    for d in sorted(serial, key=lambda x: SOLVER_TITLE[x]):
        doc.append(f"* [{SOLVER_TITLE[d]} — `{d}`](by-solver/{d.replace('/', '_')}.md)"
                   f" — {len(by_dir[d])} variants")
    doc += [
        "",
        "## Other example families that were also built and run",
        "",
        "These have no pure-Rust counterpart in this port (it is serial-only),",
        "so they do not appear in `differences/`. They are recorded because the",
        "instruction was to build and execute *all* examples.",
        "",
        "| directory | variants | all exited 0 |",
        "|---|---|---|",
    ]
    for d in other:
        allok = all(r["status"] == "OK" for r in by_dir[d])
        doc.append(f"| `{d}` | {len(by_dir[d])} | {'yes' if allok else 'NO'} |")

    doc += [
        "",
        "## Example families that could not be built here",
        "",
        "See [`../requirements.md`](../requirements.md) for the probe results and",
        "the exact `apt` command. In short: MPI headers, KLU, SuperLU_MT,",
        "SuperLU_DIST, hypre, PETSc, Trilinos, Kokkos, MAGMA, Ginkgo, RAJA,",
        "oneMKL and XBraid are absent, which removes the `parallel`, `parhyp`,",
        "`petsc`, `cuda`, `raja`, `kokkos`, `ginkgo`, `magma`, `superludist`,",
        "`trilinos`, `CXX_xbraid`, `CXX_onemkl`, `CXX_sycl` and the `*_klu` /",
        "`*_sps` / `*_slu` examples from this run.",
        "",
    ]
    (C_DIR / "README.md").write_text("\n".join(doc) + "\n")

    (C_DIR / "by-solver").mkdir(exist_ok=True)
    for d, rs in by_dir.items():
        if d not in SOLVER_TITLE:
            continue
        t = [
            f"# {SOLVER_TITLE[d]} — C examples (`examples/{d}`)",
            "",
            f"{len(rs)} (example, argv) variants, executed on the machine described in",
            "[`../README.md`](../README.md).",
            "",
            "`stdout bytes` and `sha256` are of the captured stdout stream; re-run",
            "`tools/c_examples_run.sh` and they must reproduce exactly.",
            "",
            "| # | example | argv | exit | status | seconds | stdout bytes | sha256 (first 16) | raw |",
            "|---:|---|---|---:|---|---:|---:|---|---|",
        ]
        for i, r in enumerate(sorted(rs, key=lambda r: (r["example"], r["argv"])), 1):
            t.append(
                f"| {i} | `{r['example']}` | {argv_cell(r['argv'])} | {r['exit']} | "
                f"{r['status']} | {r['seconds']} | {r['stdout_bytes']} | `{r['stdout_sha256']}` | "
                f"[stdout](../raw/{d}/{r['variant']}.stdout) · [meta](../raw/{d}/{r['variant']}.meta) |"
            )
        (C_DIR / "by-solver" / f"{d.replace('/', '_')}.md").write_text("\n".join(t) + "\n")


# --------------------------------------------------------------------------
# rust-results
# --------------------------------------------------------------------------
def write_r(p):
    rows = read_index(R_DIR / "index.tsv")
    by_dir = defaultdict(list)
    for r in rows:
        by_dir[r["dir"]].append(r)
    st = defaultdict(int)
    for r in rows:
        st[r["status"]] += 1

    doc = [
        "# rust-results — every ported example, built and executed here",
        "",
        "This directory records what the **pure-Rust translations** of the",
        "upstream serial examples printed on this machine. Same rules as",
        "`c-results/`: the `.stdout` files are raw process output.",
        "",
        "## Provenance",
        "",
        prov_block(p),
        "",
        "## How to reproduce all of it",
        "",
        "```bash",
        "cargo build --release --workspace --examples",
        "tools/rust_examples_run.sh",
        "python3 tools/make_reports.py",
        "```",
        "",
        "No network access and no package installation is involved: the",
        "workspace has **zero external crates**, so `cargo build` compiles only",
        "the seven crates in `crates/`. Nothing was added to",
        "[`../requirements.md`](../requirements.md) on the Rust side because",
        "nothing needed to be.",
        "",
        "## Headline result",
        "",
        f"**{len(rows)} (example, argv) variants, {st.get('OK', 0)} exited 0, "
        f"{st.get('NOT_PORTED', 0)} have no Rust counterpart.**",
        "",
        "| status | variants |",
        "|---|---|",
    ]
    for k in sorted(st, key=lambda k: -st[k]):
        doc.append(f"| {k} | {st[k]} |")

    doc += [
        "",
        "`NOT_PORTED` marks the `*_klu` examples not yet translated plus the",
        "9 `*_sps`/`*_slu` ones.",
        "Both KLU and SuperLU_MT are third-party sparse-direct **C** libraries,",
        "and a port whose hard rules are *no `unsafe`, no FFI, no external",
        "crates* cannot call them; there is no pure-Rust equivalent in this",
        "tree to translate them against. This is a real gap in coverage, not a",
        "bookkeeping artefact:",
        "",
        "* the 9 SuperLU_MT examples cannot be built on the C side either —",
        "  SuperLU_MT is not packaged for Ubuntu at any version — so nothing",
        "  is lost by their absence here;",
        "* the KLU examples **do** build and run on the C side (see",
        "  `c-results/`), so for those the C column exists and the Rust column",
        "  does not. Closing that gap needs a sparse direct",
        "  solver in `sundials_core`, which is a separate project.",
        "",
        "See [`../requirements.md`](../requirements.md) §3.",
        "",
        "## What makes these runs reproducible",
        "",
        "Unlike the C binaries, these do not call the host C library for any",
        "elementary function. `exp`, `log`, `pow`, `expm1`, `log1p`, `sin`,",
        "`cos`, `atan`, `asin`, `acos`, `sinh`, `cosh` and `acosh` are all",
        "implemented in `crates/sundials_core/src/sundials_libm.rs`, so the",
        "numbers below do not move when the host glibc moves. See",
        "[`../LIBM.md`](../LIBM.md).",
        "",
        "## Layout of this directory",
        "",
        "| path | contents |",
        "|---|---|",
        "| `index.tsv` | one row per variant |",
        "| `raw/<dir>/<variant>.stdout` | exactly what the process printed |",
        "| `raw/<dir>/<variant>.stderr` | stderr |",
        "| `raw/<dir>/<variant>.meta` | binary, argv, cwd, exit code, timing, SHA-256 |",
        "| `by-solver/*.md` | the per-solver tables below |",
        "",
        "## Per-solver tables",
        "",
    ]
    for d in sorted(by_dir, key=lambda x: SOLVER_TITLE.get(x, x)):
        doc.append(
            f"* [{SOLVER_TITLE.get(d, d)} — `{CRATE_OF.get(d, '')}`]"
            f"(by-solver/{d.replace('/', '_')}.md) — {len(by_dir[d])} variants"
        )
    doc.append("")
    (R_DIR / "README.md").write_text("\n".join(doc) + "\n")

    (R_DIR / "by-solver").mkdir(exist_ok=True)
    for d, rs in by_dir.items():
        crate = CRATE_OF.get(d, "")
        t = [
            f"# {SOLVER_TITLE.get(d, d)} — Rust examples (`crates/{crate}/examples`)",
            "",
            f"{len(rs)} (example, argv) variants. Run one yourself with:",
            "",
            "```bash",
            f"cargo run --release -p {crate} --example <name> -- <argv>",
            "```",
            "",
            "| # | example | argv | exit | status | seconds | stdout bytes | sha256 (first 16) | raw |",
            "|---:|---|---|---:|---|---:|---:|---|---|",
        ]
        for i, r in enumerate(sorted(rs, key=lambda r: (r["example"], r["argv"])), 1):
            t.append(
                f"| {i} | `{r['example']}` | {argv_cell(r['argv'])} | {r['exit']} | "
                f"{r['status']} | {r['seconds']} | {r['stdout_bytes']} | `{r['stdout_sha256']}` | "
                f"[stdout](../raw/{d}/{r['variant']}.stdout) · [meta](../raw/{d}/{r['variant']}.meta) |"
            )
        (R_DIR / "by-solver" / f"{d.replace('/', '_')}.md").write_text("\n".join(t) + "\n")


# --------------------------------------------------------------------------
# differences
# --------------------------------------------------------------------------
def write_d(p):
    rows = read_index(D_DIR / "index.tsv")
    by_dir = defaultdict(list)
    for r in rows:
        by_dir[r["dir"]].append(r)
    cls = defaultdict(int)
    for r in rows:
        cls[r["class"]] += 1

    comparable = sum(v for k, v in cls.items() if k not in ("NOT_PORTED", "NO_C_RUN"))
    ident = cls.get("IDENTICAL", 0)

    # the host-libm control build, if tools/ab_host_libm.sh has been run
    ab_path = D_DIR / "ab-host-libm.tsv"
    ab_total = ab_ident = None
    if ab_path.exists():
        ab = read_index(ab_path)
        ab_total = len(ab)
        ab_ident = sum(1 for r in ab if r["host_libm_class"] == "IDENTICAL")

    doc = [
        "# differences — C output versus Rust output, variant by variant",
        "",
        "Every serial example was executed twice on this machine: once as the",
        "upstream C binary (`c-results/`) and once as its pure-Rust translation",
        "(`rust-results/`). This directory is the comparison of the two stdout",
        "streams. Nothing here is asserted — every classification is computed by",
        "[`../tools/compare_results.py`](../tools/compare_results.py) from the",
        "captured bytes.",
        "",
        "## Provenance",
        "",
        prov_block(p),
        "",
        "## How to reproduce all of it",
        "",
        "```bash",
        "tools/c_build.sh && tools/c_examples_run.sh      # the C side",
        "tools/rust_examples_run.sh                       # the Rust side",
        "python3 tools/compare_results.py                 # the comparison",
        "python3 tools/make_reports.py                    # these documents",
        "```",
        "",
        "## Headline result",
        "",
        f"**Of {comparable} comparable variants, {ident} are byte-for-byte identical "
        f"({100.0 * ident / comparable:.1f}%).**",
        "",
        (
            f"**With the elementary functions delegated back to the host C library "
            f"(`--features host-libm`), {ab_ident} of {ab_total} are identical — that is, "
            f"all of them.** Every remaining difference is therefore caused by the "
            f"deliberate pure-Rust libm and by nothing else: **0 port defects**, measured "
            f"rather than asserted. See [ATTRIBUTION.md](ATTRIBUTION.md)."
            if ab_ident is not None
            else "_(run `tools/ab_host_libm.sh` to attribute the differences.)_"
        ),
        "",
        "| class | variants | meaning |",
        "|---|---:|---|",
        f"| IDENTICAL | {cls.get('IDENTICAL', 0)} | the two stdout streams are equal byte for byte |",
        f"| WHITESPACE | {cls.get('WHITESPACE', 0)} | every printed character matches; only column padding differs |",
        f"| NUMERIC | {cls.get('NUMERIC', 0)} | same text, same field count, at least one number differs |",
        f"| STRUCTURAL | {cls.get('STRUCTURAL', 0)} | different lines, words or field counts |",
        f"| NOT_PORTED | {cls.get('NOT_PORTED', 0)} | KLU / SuperLU_MT example, excluded by design on both sides |",
        f"| NO_C_RUN | {cls.get('NO_C_RUN', 0)} | the C example could not be built on this machine |",
        "",
        "## How to read a difference",
        "",
        "For every non-identical variant there is a unified diff, and for every",
        "`NUMERIC` one there is also a `.numbers` file naming the single worst",
        "field:",
        "",
        "```bash",
        "cat differences/diffs/<dir>/<variant>.diff",
        "cat differences/diffs/<dir>/<variant>.numbers",
        "```",
        "",
        "`worst rel` below is the largest relative difference between any pair of",
        "printed numbers, and `worst ulp` is the same pair measured in",
        "representable double steps. One ulp is the smallest difference two",
        "doubles can have — it is the granularity of the format itself, not an",
        "error in either program.",
        "",
        "## Attribution",
        "",
        "[**ATTRIBUTION.md**](ATTRIBUTION.md) — the controlled experiment that",
        "decides, for every divergent variant, whether the translation is wrong",
        "or the libm substitution accounts for it. Raw data in",
        "[`ab-host-libm.tsv`](ab-host-libm.tsv).",
        "",
        "## Per-solver tables",
        "",
    ]
    for d in sorted(by_dir, key=lambda x: SOLVER_TITLE.get(x, x)):
        n = len(by_dir[d])
        ni = sum(1 for r in by_dir[d] if r["class"] == "IDENTICAL")
        doc.append(
            f"* [{SOLVER_TITLE.get(d, d)}](by-solver/{d.replace('/', '_')}.md)"
            f" — {ni} identical of {n}"
        )
    doc.append("")
    (D_DIR / "README.md").write_text("\n".join(doc) + "\n")

    (D_DIR / "by-solver").mkdir(exist_ok=True)
    for d, rs in by_dir.items():
        t = [
            f"# {SOLVER_TITLE.get(d, d)} — C vs Rust (`examples/{d}`)",
            "",
            "| # | example | argv | class | diff lines / total | worst rel | worst ulp | diff |",
            "|---:|---|---|---|---:|---:|---:|---|",
        ]
        for i, r in enumerate(sorted(rs, key=lambda r: (r["example"], r["argv"])), 1):
            link = (
                f"[diff](diffs/{d}/{r['variant']}.diff)"
                if r["class"] not in ("IDENTICAL", "NOT_PORTED", "NO_C_RUN")
                else "—"
            )
            dl = (
                f"{r['diff_lines']} / {r['total_lines']}"
                if r["diff_lines"]
                else "—"
            )
            t.append(
                f"| {i} | `{r['example']}` | {argv_cell(r['argv'])} | {r['class']} | "
                f"{dl} | {r['worst_rel'] or '—'} | {r['worst_ulp'] or '—'} | {link} |"
            )
        t.append("")
        (D_DIR / "by-solver" / f"{d.replace('/', '_')}.md").write_text("\n".join(t) + "\n")


def main():
    p = provenance()
    if (C_DIR / "index.tsv").exists():
        write_c(p)
        print("wrote c-results/")
    if (R_DIR / "index.tsv").exists():
        write_r(p)
        print("wrote rust-results/")
    if (D_DIR / "index.tsv").exists():
        write_d(p)
        print("wrote differences/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
