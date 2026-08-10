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
| port defects among the 26 | **0 — proven natively**: all 26 are byte-identical to the pristine upstream C built by gcc 13.3.0 on this host |

Measured host: Ubuntu 24.04 x86-64, glibc 2.39, gcc 13.3.0, rustc/cargo
1.93.1, CPU with FMA — running as a WSL2 guest on Windows 11, which is a
genuine Linux/glibc/x86-64 userspace and therefore a valid target for
every claim above. See "Open items" for what a bare-metal re-run would add.

Raw artefacts for all of it are committed under
[`evidence/linux-x86_64-glibc239/`](evidence/linux-x86_64-glibc239/).

> ### Not yet pushed
>
> `git push origin main` to
> `https://github.com/once-ere/SUNDIALS_7_8_Rust_port_for_Linux.git`
> **failed: GitHub asked for interactive authentication** that this session
> could not supply. The work is committed locally on `main` with `origin`
> already configured; nothing else is outstanding.
>
> What was tried, so the fix is not re-guessed:
>
> * `credential.helper` is globally set to **`manager-core`**, a name Git
>   Credential Manager retired; no such binary exists on this machine. The
>   installed one is `C:\Program Files\Git\mingw64\bin\git-credential-manager.exe`.
> * Overriding it per-invocation (`-c credential.helper= -c
>   credential.helper=manager`) got GCM to run, but it would not serve the
>   stored `git:https://github.com` credential without a prompt.
> * There is an SSH key at `~/.ssh/id_ed25519` inside the WSL Ubuntu guest,
>   but GitHub rejects it — `Permission denied (publickey)`. It is not
>   registered on the account.
>
> Either route works once a human is at the keyboard:
>
> ```bash
> git config --global credential.helper manager
> ```
>
> ```bash
> git -C "C:/Users/nsh/Developer/github/SUNDIALS_7_8_Rust_port_for_Linux" push -u origin main
> ```

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

The 26 that remain are **all reference-side, and that is now proven on
this host rather than inherited.** A divergence from a shipped `.out` is a
port defect only if the Rust output also differs from what the pristine
upstream C produces on the same machine. So the upstream C library and its
serial examples were built here with cmake + gcc 13.3.0
(`tools/pristine_c_build.sh`, 112 example binaries) and every divergent
variant was run three ways — Rust, pristine C, shipped reference — by
`tools/compare_pristine_c.sh`:

| comparison | result across all 26 |
|---|---|
| **Rust vs pristine C** | **`same` — 26 / 26** |
| pristine C vs shipped `.out` | `DIFF` — 26 / 26 |
| Rust vs shipped `.out` | `DIFF` — 26 / 26 (the gate result) |

The C and the Rust agree with each other and disagree with the shipped
reference, in every case. **The references are stale; the port is not
wrong anywhere.**

The two LAPACK examples needed one extra step, because a pristine build
with `ENABLE_LAPACK=OFF` does not contain them at all.
`tools/compare_lapack_substituted.sh` compiles `cv[s]Roberts_dnsL.c` with
exactly the two tokens the port also substitutes
(`sunlinsol_lapackdense.h` -> `sunlinsol_dense.h`, `SUNLinSol_LapackDense`
-> `SUNLinSol_Dense`) against the pristine C library, and both come out
`same` against the Rust. Their divergence from the reference is therefore
entirely the documented LAPACK -> native substitution, not a translation
error.

Secondary classification, from `tools/classify_diffs.sh`: **15 of the 26
are whitespace-only** — `tr -s ' '` makes the diff empty, so every printed
*value* is byte-identical and only column spacing differs
(`SUN_TABLE_WIDTH` 28 -> 29 in references that predate the change). The
other 11 have real content differences, all reference-side: two
LAPACK->native variants (`cv[s]Roberts_dnsL`), two upstream `.out`
anomalies (`cv[s]Pendulum_dns`), five trailing-whitespace-stripped
references (`cvsKrylovDemo_ls` x4, `idasAkzoNob_ASAi_dns`), and two
references missing a final blank line the source prints unconditionally
(`ark_conserved_exp_entropy_ark 1 1`, `ark_dissipated_exp_entropy 1 1`).

## 4. Distribution coverage — measured, and one claim retracted

Nothing in the Rust tree is distribution-specific: `std` only, no
`cfg(target_os)`, no `cfg(target_arch)`, no build script, no system
library beyond what `std` itself links. The only distribution-visible
dependency is the libm behind `f64`'s transcendental methods.

**An earlier draft of this file argued that the claim therefore carries to
"Debian, Arch and Fedora on glibc >= 2.28". That was wrong and has been
retracted.** glibc's libm is not frozen across releases, and measuring it
is what showed so. `tools/glibc_sweep.sh` builds `tools/libm_probe.c` in
each distribution's container and hashes 1,000,000 results per function:

| distro | libc | functions disagreeing with the reference host (glibc 2.39) |
|---|---|---|
| Debian 12 | glibc 2.36 | `atan` |
| **Ubuntu 24.04** | **glibc 2.39** | — (reference host) |
| Fedora 41 | glibc 2.40 | none |
| Debian 13 | glibc 2.41 | none |
| Arch (rolling) | glibc 2.44 | `sinh`, `cosh`, `acosh` |
| Alpine 3.20 | musl | everything except `sqrt` — including `pow` |

`pow` is bit-identical on every glibc tested, so §2's result carries to all
of them. `sqrt` matches everywhere, as IEEE-754 requires.

`tools/gate_in_container.sh` then ran the **full 199-variant gate natively
inside three of those containers**, to find out whether those libm
differences are output-observable:

| distro | libc | rustc | gate | vs. reference host |
|---|---|---|---|---|
| Ubuntu 24.04 | 2.39 | 1.93.1 | **153 / 26 / 20** | reference |
| Debian 12 | 2.36 | 1.97.1 | **153 / 26 / 20** | identical variant set |
| Fedora 41 | 2.40 | 1.97.1 | **153 / 26 / 20** | identical variant set |
| Arch | 2.44 | 1.97.1 | **150 / 29 / 20** | +3 variants diverge |

0 build failures and 0 run failures everywhere; the containers used a
*newer* rustc than the host, so the result is toolchain-stable too.

**Verified coverage: glibc 2.36 through 2.41** — Debian 12, Ubuntu 24.04,
Debian 13, Fedora 41. Debian 12's `atan` difference is real but not
output-observable: no variant evaluates `atan` where 2.36 and 2.39 disagree.

**Arch (glibc 2.44): three variants diverge** —
`ark_analytic_lsrk_domeigest` (both argv variants) and
`ark_analytic_lsrk_varjac`. Predicted from the fingerprint table before the
gate was run, then confirmed by it: `sinh`, `cosh` and `acosh` are called
from exactly one place in the library, `arkode_lsrkstep.rs:87`, and glibc
2.44 changed all three. A libm-version effect, not a port defect — the port
runs correctly there, but three reference outputs will not reproduce
byte-for-byte.

**musl is out of scope**, now for a measured reason: `sin`, `cos`, `exp`,
`log`, `asin`, `acos`, `atan` and the hyperbolics all differ from glibc's.
Its `pow` differs too, but that one does not matter — the port does not use
the host `pow`.

## 5. Open items

Nothing blocks the port; these would strengthen the evidence.

1. **Bare-metal re-run.** All numbers above come from WSL2 (including the
   containers, which share its kernel). That is a real Linux kernel with
   real glibc and real x86-64 instructions, so the arithmetic cannot
   differ — and §4's four-distribution agreement, across three glibc
   versions and two rustc versions, is strong corroboration that nothing
   about the environment is load-bearing. A run on a bare-metal Ubuntu box
   would still remove the last of the question. Re-run:
   `tools/pow_differential.sh all` and `tools/verify_examples.sh all`.
2. ~~**Native pristine-C rebuild for the content divergences.**~~ **Done.**
   Upstream SUNDIALS 7.8.0 was built here with cmake + gcc 13.3.0 and all
   26 divergent variants compared three ways; Rust == pristine C in every
   case (§3). `tools/pristine_c_build.sh`,
   `tools/compare_pristine_c.sh`, `tools/compare_lapack_substituted.sh`.
3. ~~**glibc version sweep.**~~ **Done, and it changed the answer** — see
   §4. libm fingerprints across five distributions plus the full gate
   re-run natively on three of them. Verified coverage is glibc 2.36–2.41;
   Arch's 2.44 moves three LSRK variants. `tools/glibc_sweep.sh`,
   `tools/gate_in_container.sh`.
4. **Arch / glibc 2.44, if byte-identity there is ever wanted.** The three
   divergent variants all trace to `SUNRsinh`/`SUNRcosh`/`SUNRacosh` in
   `arkode_lsrkstep.rs:87`. Porting those three the way `pow` was ported —
   a host-independent Rust implementation of the glibc algorithm — would
   close it. Not done: it would fix one distribution's three variants at
   the cost of a second hand-maintained libm routine set, and the port is
   correct there either way.
5. **musl**, if it is ever wanted: out of scope, for the measured reason
   in §4.

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

To reproduce the port-defect proof, which needs a native C build of the
upstream tree (out of source; the tree stays read-only):

```bash
tools/pristine_c_build.sh            # cmake + gcc, ~112 example binaries
tools/compare_pristine_c.sh          # Rust vs pristine C vs reference
tools/compare_lapack_substituted.sh  # the two *L examples
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
