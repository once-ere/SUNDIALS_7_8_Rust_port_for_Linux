# current_status.md — SUNDIALS_7_8_Rust_port_for_Linux

**Status: the port is complete and green on Linux / glibc / x86-64.**
Session of 2026-08-10. Read this file first when resuming.

| gate | result |
|---|---|
| `cargo build --workspace` (Linux x86-64) | **0 errors, 0 warnings** |
| `cargo test --workspace --lib` | **25 passed, 0 failed** |
| deterministic `pow` vs **native glibc `pow`**, SUNDIALS domain corpus | **5,900,000 inputs, 0 mismatches** |
| deterministic `pow` vs **native glibc `pow`**, unrestricted corpus | **20,000,000 inputs, 0 mismatches** |
| `tools/verify_examples.sh all` (199 reference variants) | **153 IDENTICAL / 26 reference-side divergences / 20 excluded (KLU/SuperLU)** |
| port defects among the 26 | **0** |

Measured host: Ubuntu 24.04 x86-64, glibc 2.39, gcc 13.3.0, rustc/cargo
1.93.1, CPU with FMA — running as a WSL2 guest on Windows 11, which is a
genuine Linux/glibc/x86-64 userspace and therefore a valid target for
every claim above. See "Open items" for what a bare-metal re-run would add.

---

## 1. What this project is

A pure-Rust port of SUNDIALS 7.8.0 (LLNL) scoped to **Linux on Intel/AMD
x86-64** — Ubuntu 24.04/26.04 and, by the argument in §4, the Debian, Arch
and Fedora families. No `unsafe`, no FFI, no external crates, `std` only.
Seven crates, 141 modules, one per upstream C file, keeping the exact C
names, constants and return-flag conventions.

It **reuses the entire crate tree** of the sibling port
`SUNDIALS_7_8_Rust_port_for_AppleSilicon_macos` (github.com/once-ere/…),
which is where the 141 modules were originally translated from the C
sources. Not one line of solver code was re-derived. What is new here is
the *target-platform* work: the `pow` question below, a native x86-64
oracle, a re-run of the whole verification gate under glibc, and the
documentation that scopes every claim to Linux instead of macOS.

## 2. The `pow` question — resolved

The task set this as the gating item: the deterministic `pow` inherited
from the macOS port is a translation of the **ARM optimized-routines /
musl** `pow`, so does a Linux/x86-64 port need a different one?

**Answer: no — the algorithm is already the right one, but its evidence
was not.** ARM's optimized-routines `pow` *is* what glibc >= 2.28 ships as
`sysdeps/ieee754/dbl-64/e_pow.c`; on x86-64 glibc ifunc-dispatches to
`__ieee754_pow_fma`, the same source rebuilt with `-mfma -mavx2
-ffp-contract=fast`. So the correct x86-64 target is that FMA-contracted
build, and the Rust routine already reproduces its contraction map. What
was missing was any measurement made **on x86-64**: the macOS project
measured against oracle binaries built on arm64 and said so explicitly
(`POW_FMA_EXACTNESS.md` §5, "No differential run was made on a native
x86-64 host").

That measurement now exists and is part of this repository:

* `tools/pow_oracle.c` — builds with the host `cc`, calls the host `pow`,
  emits the reference bit-stream. Must be built and run on the target.
* `tools/pow_differential.sh` — driver; writes `logs/pow_differential.log`.
* `pow_glibc_vs_native_oracle_{domain,random}` in
  `crates/sundials_core/src/sundials_math.rs` — the Rust side. Both sides
  regenerate the corpus from the same splitmix64 recurrence, so they
  cannot disagree about which inputs they evaluated. With no oracle file
  in the environment the tests report "not run" and pass, so `cargo test`
  stays green on hosts where the oracle would be meaningless.

Result on Ubuntu 24.04 / glibc 2.39 / x86-64: **0 mismatches over
5,900,000 domain inputs and 0 over 20,000,000 unrestricted finite inputs.**
The two residual 1-ulp disagreements the macOS project could not eliminate
do not exist against a native glibc oracle — they were artefacts of the
arm64-built oracle, which is exactly the doubt that document raised.

No new `pow` source was written: writing one would have replaced a routine
already bit-exact against the target with an unmeasured rewrite.

## 3. Verification gate, Linux vs macOS

| | macOS / arm64 (inherited) | **Linux / x86-64 (this repo)** |
|---|---:|---:|
| IDENTICAL | 127 | **153** |
| divergent, reference-side | 52 | **26** |
| excluded (KLU/SuperLU) | 20 | 20 |
| port defects | 0 | **0** |

26 variants that diverged on macOS are byte-identical here. That is the
predicted effect and the main evidence for the platform claim: the host
libm now *is* the libm that generated the upstream `.out` files. The port
takes `sin`, `cos`, `asin`, `acos`, `atan`, `sinh`, `cosh`, `acosh`, `exp`
and `ln` from the host through `f64`'s unspecified-precision methods; on a
glibc host that is glibc, so the mismatch the macOS port had to document
away simply is not there.

The 26 that remain split cleanly (`tools/classify_diffs.sh`, run on this
host):

* **15 are whitespace-only** — `tr -s ' '` makes the diff empty, i.e.
  every printed *value* is byte-identical and only column spacing differs
  (`SUN_TABLE_WIDTH` 28 -> 29 in the shipped references). Proven here, on
  this host, this session.
* **11 have content differences**, each already root-caused in the
  inherited `VERIFICATION.md` as reference-side: two LAPACK->native dense
  variants (`cv[s]Roberts_dnsL`), two upstream `.out` anomalies
  (`cv[s]Pendulum_dns`), five trailing-whitespace-stripped references
  (`cvsKrylovDemo_ls` x4, `idasAkzoNob_ASAi_dns`), and two references
  missing a final blank line the source prints unconditionally
  (`ark_conserved_exp_entropy_ark 1 1`, `ark_dissipated_exp_entropy 1 1`).

## 4. Why the claim extends to Debian, Arch and Fedora

Nothing in the Rust tree is distribution-specific: `std` only, no
`cfg(target_os)`, no `cfg(target_arch)`, no build script, no system
library beyond what `std` itself links. The only distribution-visible
dependency is the libm behind `f64`'s transcendental methods, and every
mainstream distribution in those three families ships **glibc** — the same
implementation, with `pow` on x86-64 taking the same ifunc FMA path on any
CPU made since Haswell. The reasoning holds for glibc >= 2.28 (Debian 10+,
Ubuntu 18.10+, Fedora 29+, and rolling Arch).

It does **not** automatically hold for musl-based distributions (Alpine,
Void musl). musl's `pow` is the same ARM optimized-routines algorithm, so
`pow` itself agrees, but musl's `sin`/`cos`/`exp`/`log` are not glibc's and
the gate has not been run there. Treated as out of scope, not as verified.

## 5. Open items

Nothing blocks the port; these would strengthen the evidence.

1. **Bare-metal re-run.** All numbers above come from WSL2, which is a
   real Linux kernel with real glibc and real x86-64 instructions — the
   arithmetic cannot differ — but a run on a bare-metal Ubuntu box would
   remove the question. Re-run: `tools/pow_differential.sh all` and
   `tools/verify_examples.sh all`.
2. **Native pristine-C rebuild for the 11 content divergences.** The macOS
   project root-caused each against a pristine upstream C build made
   *there*; this session re-verified the 15 whitespace ones natively but
   carried the other 11 over on the strength of that earlier work. Build
   upstream SUNDIALS 7.8.0 with cmake/gcc on Linux and re-confirm
   "port == pristine C" for those 11. Expected to hold — several of them
   are pure formatting facts about the shipped `.out` files, independent
   of any host.
3. **glibc version sweep.** Measured against 2.39. A quick re-run of
   `tools/pow_differential.sh domain` under a Debian 12 (2.36) and a
   Fedora 41 (2.40) container would turn §4's argument into a measurement.
4. **musl**, if it is ever wanted: out of scope today (§4).

## 6. How to reproduce, from a clean checkout

On a Linux x86-64 host with rustup and a C compiler:

```bash
git clone https://github.com/once-ere/SUNDIALS_7_8_Rust_port_for_Linux.git
cd SUNDIALS_7_8_Rust_port_for_Linux
cargo build --workspace          # 0 warnings
cargo test  --workspace --lib    # 25 passed
tools/pow_differential.sh all    # 0 mismatches / 25.9M inputs
```

The example gate additionally needs the read-only upstream SUNDIALS 7.8.0
C tree as this workspace's **parent** directory, because it reads
`../examples/<solver>/<serial dir>/*.out`:

```bash
tools/verify_examples.sh all     # then read logs/summary.txt
tools/classify_diffs.sh          # second pass over the non-IDENTICAL ones
```

From Windows, `tools/wsl_sync_build.sh {build|test|rel|gate|pow}` mirrors
the working copy into a WSL Ubuntu sandbox (`~/sdl/port`, with
`~/sdl/examples` symlinked at the C tree) and runs the step there. It also
strips CRLF from `tools/*.sh`, which a Windows checkout can introduce;
`.gitattributes` pins those files to LF to prevent it.

## 7. Provenance

* Upstream: SUNDIALS 7.8.0, LLNL, BSD-3-Clause. Read-only reference at
  `C:\Users\nsh\Developer\sundials-7.8.0` on the machine this was built on.
* Crate tree: inherited wholesale from
  `SUNDIALS_7_8_Rust_port_for_AppleSilicon_macos`, BSD-3-Clause, same
  author lineage. `ARCHITECTURE.md`, `PROGRESS.md` and the body of
  `VERIFICATION.md` come from there unchanged and remain accurate — they
  describe the translation, which is platform-independent.
* Deterministic `pow`: ARM optimized-routines via musl `src/math/pow.c`,
  MIT, (c) 2018 Arm Limited — the algorithm glibc >= 2.28 ships. See
  `NOTICE` and `POW_FMA_EXACTNESS.md`.
* New in this repository: `tools/pow_oracle.c`,
  `tools/pow_differential.sh`, `tools/classify_diffs.sh`,
  `tools/wsl_sync_build.sh`, the two differential unit tests,
  `.gitattributes`, this file, and the Linux scoping in `README.md`,
  `CLAUDE.md`, `POW_FMA_EXACTNESS.md` and `VERIFICATION.md`.
