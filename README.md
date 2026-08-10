# SUNDIALS_7_8_Rust_port_for_Linux

A line-by-line translation of [SUNDIALS](https://github.com/LLNL/sundials)
7.8.0 into safe Rust. **No `unsafe`, no FFI, no external crates, no build
warnings.** Acceptance is byte-identical printed output against the upstream C
reference examples — **established on Linux running on Intel/AMD x86-64 with
glibc.**

## Platform scope: Linux on x86-64, glibc

> Every numerical result in this repository was measured on **Ubuntu 24.04
> x86-64, glibc 2.39, gcc 13.3.0, rustc 1.93.1**, on a CPU with FMA. The
> gate was then **re-run natively on Debian 12 (glibc 2.36), Fedora 41
> (glibc 2.40) and Arch (glibc 2.44)** — see
> [Distribution coverage](#distribution-coverage-measured-not-argued), which
> reports the one distribution where three variants differ and why. The
> claim does not extend to musl, to arm64, or to Windows.
>
> This is the *good* platform for this port, and the reason is worth stating
> plainly: the upstream reference `.out` files were generated on a glibc host.
> The library and the examples evaluate `sin`, `cos`, `asin`, `acos`, `atan`,
> `sinh`, `cosh`, `acosh`, `exp` and `ln` through `f64` methods that Rust
> `std` documents as having *unspecified precision* and forwards to the host
> libm — so on glibc those calls land on exactly the implementation the
> references came from. The sibling
> [macOS/Apple-Silicon port](https://github.com/once-ere/SUNDIALS_7_8_Rust_port_for_AppleSilicon_macos)
> had to document 52 variants away as Apple-libm divergence; **26 of those are
> byte-identical here.**

## Headline facts

* 7 crates: `sundials_core` plus `cvode_rs`, `cvodes_rs`, `kinsol_rs`,
  `ida_rs`, `idas_rs`, `arkode_rs`. Solver crates depend on the core, never on
  each other.
* 141 modules, one per upstream C file, keeping the exact C function names,
  constants and return-flag conventions (`CV_SUCCESS = 0`; negative fatal,
  positive recoverable).
* Serial only. No MPI, GPU, KLU, SuperLU, LAPACK, Fortran or XBraid backends.
* `cargo build --workspace` → **zero warnings**. `cargo test --workspace
  --lib` → **25 passed**.
* Deterministic `pow` vs the **native glibc `pow`**: **0 mismatches over
  5,900,000 domain inputs and 0 over 20,000,000 unrestricted finite inputs.**
* Example gate: of the 199 reference `(example, argv)` variants,
  **153 are byte-identical, 26 are reference-side divergences (0 port
  defects), and 20 are excluded as KLU/SuperLU**. All six solver crates swept.

## Quick start

```bash
cargo build --workspace
cargo run -p cvode_rs --example cvRoberts_dns
tools/pow_differential.sh all
```

```rust
use cvode_rs::prelude::*;
```

The example gate additionally needs the read-only upstream SUNDIALS 7.8.0 C
tree as this workspace's **parent** directory — it reads
`../examples/<solver>/<serial dir>/*.out`:

```bash
tools/verify_examples.sh all
```

## Relationship to the macOS port

**This repository reuses the macOS port's crate tree wholesale.** All 141
modules were translated from the C sources there; not one line of solver code
was re-derived here, and `ARCHITECTURE.md` and `PROGRESS.md` are inherited
unchanged because they describe the translation, which is
platform-independent. What is new is the target-platform work: a native
x86-64 `pow` oracle and differential, a re-run of the whole verification gate
under glibc, and documentation scoped to Linux.

## The `pow` question

`crates/sundials_core/src/sundials_math.rs` contains `pow_glibc`, a pure-Rust
port of the ARM optimized-routines `pow` (MIT, © 2018 Arm Limited, taken via
musl). The "ARM" in that provenance is a red herring for a Linux/x86-64
target: **that algorithm is what glibc ≥ 2.28 ships** as
`sysdeps/ieee754/dbl-64/e_pow.c`, and on x86-64 glibc ifunc-dispatches to
`__ieee754_pow_fma` — the same source rebuilt with `-mfma -mavx2
-ffp-contract=fast`. Reproducing *that* build, contraction site for
contraction site, is exactly what the Rust routine does.

What was missing was evidence gathered on x86-64. The macOS project measured
against oracle binaries built on arm64 and said so
([`POW_FMA_EXACTNESS.md`](POW_FMA_EXACTNESS.md) §5: "No differential run was
made on a native x86-64 host"). This repository supplies it:

| artefact | role |
|---|---|
| [`tools/pow_oracle.c`](tools/pow_oracle.c) | built with the host `cc`, calls the host `pow`, emits the reference bit-stream |
| [`tools/pow_differential.sh`](tools/pow_differential.sh) | driver; writes `logs/pow_differential.log` |
| `pow_glibc_vs_native_oracle_{domain,random}` | the Rust side, in `sundials_math.rs` |

Both sides regenerate the corpus from the same splitmix64 recurrence rather
than exchanging inputs, so they cannot disagree about what they evaluated.
The result on glibc 2.39 / x86-64 is **0 mismatches on both corpora** — the
two residual 1-ulp disagreements the macOS project could not eliminate are
absent against a native oracle, which is precisely the doubt that document
raised. No new `pow` source was written, because writing one would have
replaced a routine already bit-exact against the target with an unmeasured
rewrite.

`pow` is the only *libm* substitution, but not the only host-C-library one:
`ark_analytic_lsrk_domeigest`, `ark_brusselator_lsrk_domeigest` and
`ark_brusselator_lsrk_externaldomeigest` reproduce the BSD/glibc `rand()`
TYPE_3 additive-feedback generator in Rust, sequence for sequence, because
those examples feed pseudo-random vectors into a dominant-eigenvalue estimator
and the draws are output-observable. See [`NOTICE`](NOTICE).

## Verification results

| | macOS / arm64 (inherited) | **Linux / x86-64 (here)** |
|---|---:|---:|
| IDENTICAL | 127 | **153** |
| divergent, reference-side | 52 | **26** |
| excluded (KLU/SuperLU) | 20 | 20 |
| port defects | 0 | **0** |

**"0 port defects" is measured, not asserted.** A divergence from a shipped
`.out` is a port defect only if the Rust output also differs from what the
pristine upstream C produces on the same machine — so the upstream C library
and its serial examples were built here with cmake + gcc 13.3.0
([`tools/pristine_c_build.sh`](tools/pristine_c_build.sh)) and every
divergent variant run three ways
([`tools/compare_pristine_c.sh`](tools/compare_pristine_c.sh)):

| comparison | result across all 26 |
|---|---|
| **Rust vs pristine C** | **`same` — 26 / 26** |
| pristine C vs shipped `.out` | `DIFF` — 26 / 26 |
| Rust vs shipped `.out` | `DIFF` — 26 / 26 (the gate result) |

The C and the Rust agree with each other and disagree with the shipped
reference, every time: the references are stale, the translation is not
wrong anywhere. The two LAPACK examples are absent from a pristine
`ENABLE_LAPACK=OFF` build, so
[`tools/compare_lapack_substituted.sh`](tools/compare_lapack_substituted.sh)
compiles them with exactly the two tokens the port also substitutes; both
also come out `same`.

Secondarily, [`tools/classify_diffs.sh`](tools/classify_diffs.sh) shows
**15 of the 26 are whitespace-only** — `tr -s ' '` makes the diff empty, so
every printed *value* is byte-identical and only column spacing differs
(references predating the `SUN_TABLE_WIDTH` 28 → 29 change). The other 11
have real content differences, all reference-side and each root-caused in
[`VERIFICATION.md`](VERIFICATION.md): two LAPACK→native dense variants
(`cv[s]Roberts_dnsL`), two upstream `.out` anomalies (`cv[s]Pendulum_dns`),
five trailing-whitespace-stripped references (`cvsKrylovDemo_ls` ×4,
`idasAkzoNob_ASAi_dns`), and two references missing a final blank line the
source prints unconditionally.

## Distribution coverage — measured, not argued

Nothing in the Rust tree is distribution-specific: `std` only, no
`cfg(target_os)`, no `cfg(target_arch)`, no build script, no system library
beyond what `std` itself links. The only distribution-visible dependency is
the libm behind `f64`'s transcendental methods.

The tempting argument is "Debian, Arch and Fedora all ship glibc, so the
claim carries to all of them." **That argument is wrong, and measuring it
is what showed so.** glibc's libm is not frozen across releases.
[`tools/glibc_sweep.sh`](tools/glibc_sweep.sh) fingerprints every function
the port reaches — an FNV-1a hash over 1,000,000 deterministic inputs each,
via [`tools/libm_probe.c`](tools/libm_probe.c) — in each distribution's
container:

| distro | libc | functions disagreeing with the reference host (glibc 2.39) |
|---|---|---|
| Debian 12 | glibc 2.36 | `atan` |
| **Ubuntu 24.04** | **glibc 2.39** | — (reference host) |
| Fedora 41 | glibc 2.40 | none |
| Debian 13 | glibc 2.41 | none |
| Arch (rolling) | glibc 2.44 | `sinh`, `cosh`, `acosh` |
| Alpine 3.20 | musl | everything except `sqrt` — including `pow` |

`pow` is bit-identical across every glibc version tested, so the
deterministic `pow` result carries to all of them. `sqrt` matches
everywhere, as IEEE-754 requires.

Then [`tools/gate_in_container.sh`](tools/gate_in_container.sh) ran the
**full 199-variant gate natively inside three of those containers** to find
out whether the libm differences are output-observable:

| distro | libc | rustc | gate | vs. the reference host |
|---|---|---|---|---|
| Ubuntu 24.04 | 2.39 | 1.93.1 | **153 / 26 / 20** | reference |
| Debian 12 | 2.36 | 1.97.1 | **153 / 26 / 20** | identical variant set |
| Fedora 41 | 2.40 | 1.97.1 | **153 / 26 / 20** | identical variant set |
| Arch | 2.44 | 1.97.1 | **150 / 29 / 20** | +3 variants diverge |

(`IDENTICAL / DIFF / EXCLUDED`; 0 build failures and 0 run failures
everywhere. The containers also used a *newer* rustc than the host, so the
result is toolchain-stable as well as distribution-stable.)

**Conclusion.** The port and its gate carry unchanged to Debian 12, Ubuntu
24.04, Debian 13 and Fedora 41 — glibc 2.36 through 2.41. Debian 12's
`atan` difference exists but is not output-observable: nothing in the
199 variants evaluates `atan` where 2.36 and 2.39 disagree.

On **Arch (glibc 2.44)** exactly three more variants diverge —
`ark_analytic_lsrk_domeigest` (both argv variants) and
`ark_analytic_lsrk_varjac`. This was predicted before the gate was run and
then confirmed by it: `sinh`, `cosh` and `acosh` are called from exactly one
place in the library, [`arkode_lsrkstep.rs:87`](crates/arkode_rs/src/arkode_lsrkstep.rs:87),
and glibc 2.44 changed all three. Everything else — including the other
three LSRK variants — is unaffected. This is a libm-version effect, not a
port defect; running the port on Arch is fine, but three reference outputs
will not reproduce byte-for-byte there.

**musl (Alpine, Void musl) is out of scope**, and now for a measured reason
rather than caution: its `sin`, `cos`, `exp`, `log`, `asin`, `acos`, `atan`
and the hyperbolics all differ from glibc's. (Its `pow` differs too — but
that one does not matter, because the port does not use the host `pow`.)

## Documentation

| file | contents |
|---|---|
| [`current_status.md`](current_status.md) | **start here** — what is done, what is measured, what remains, how to resume |
| [`sundials.md`](sundials.md) | public guide — crate map, worked example, C-to-Rust API conventions |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | handle model, locked porting patterns, numbered deviation classes (inherited) |
| [`VERIFICATION.md`](VERIFICATION.md) | per-variant matrix; Linux results at the top, inherited macOS evidence below |
| [`PROGRESS.md`](PROGRESS.md) | per-file port status (inherited) |
| [`POW_FMA_EXACTNESS.md`](POW_FMA_EXACTNESS.md) | how far the deterministic `pow` is bit-exact, and on which host that was measured |
| [`CLAUDE.md`](CLAUDE.md) | workspace rules for future work in this repo |

## Licence

Derivative work of SUNDIALS, **BSD-3-Clause**, Copyright © 2002–2026 Lawrence
Livermore National Security, Southern Methodist University, University of
Maryland Baltimore County and the SUNDIALS contributors.

The deterministic `pow` in `crates/sundials_core/src/sundials_math.rs` is a
pure-Rust port of the ARM optimized-routines `pow` (via musl's
`src/math/pow.c`, `pow_data.c` and `exp_data.c`), **MIT**, Copyright © 2018
Arm Limited — the algorithm glibc ≥ 2.28 ships on this platform.

Not an LLNL product; not endorsed by the SUNDIALS project. See `sundials.md`
§8 and `NOTICE`.
