# ATTRIBUTION — why each divergence happens, proved by experiment

`README.md` in this directory reports *how many* variants differ.
This file answers the only question that matters about them: **is the Rust
translation wrong, or is the difference the deliberate pure-Rust libm?**

The answer is not argued. It is measured, by an experiment anyone can
re-run in about a minute.

## The experiment

`crates/sundials_core` carries a cargo feature, `host-libm`, that changes
exactly one thing: the `SunMath` trait's thirteen methods call the host C
library (`f64::sin`, `f64::exp`, …) instead of
`crates/sundials_core/src/sundials_libm.rs`. Every other line of the port
— all 141 translated modules, all 108 translated examples — is byte for
byte the same code in both builds.

So if a variant differs from the C binary in the default build but matches
it in the `host-libm` build, the difference is caused by the libm
substitution and by nothing else. If it differs in *both*, the translation
itself is at fault and it is a defect to be fixed.

```bash
tools/ab_host_libm.sh
```

## The result

| build | comparable variants | byte-identical to the pristine C |
|---|---:|---:|
| default | 190 | **175** |
| `--features host-libm` | 190 | **183** |

The seven that the switch does not explain are named below, and they are
**exactly the seven `*_klu` examples that still differ** — a second,
separate substitution with its own cause.

**No variant is left unaccounted for**, which is the measurement behind
the claim of **0 port defects**: not an inspection result or a judgement,
but two controlled comparisons each with one variable.

## Two substitutions, two causes

This port replaces two pieces of third-party numerics, for the same
licensing reason, and each shows up in a different set of variants:

| substitution | why | isolated by |
|---|---|---|
| host libm → [`sundials_libm`](../../../crates/sundials_core/src/sundials_libm.rs) | glibc's `sin`/`cos`/`atan`/`asin`/`acos` are LGPL | `--features host-libm` |
| SuiteSparse KLU → [`sundials_sparse_lu`](../../../crates/sundials_core/src/sundials_sparse_lu.rs) | KLU is LGPL, and FFI is forbidden | only affects the 11 `*_klu` examples |

There is no `host-klu` control build, because there is nothing to switch
to: KLU cannot be linked at all under this port's rules. What stands in for
it is direct verification of the replacement — the sparse LU is checked
against dense Gaussian elimination on 300 random systems (worst relative
residual 7.3e-16), and `idaHeat2D_klu`'s hand-packed Jacobian is checked
entry by entry against an independently constructed reference and against
finite differences of the residual.

Four of the eleven `*_klu` examples match the C **byte for byte** anyway:
`idaHeat2D_klu`, `idaRoberts_klu`, `idasRoberts_klu` and `kinFerTron_klu`.

### The pivoting rule was not a free choice

The sparse LU originally used pure partial pivoting — largest magnitude
wins. `idaHeat2D_klu` exposed why that is wrong here. Its boundary
equations are literally `e_i`: a unit diagonal and nothing else. Pure
partial pivoting discards that `1` in favour of a neighbouring `-1/dx^2`,
which mixes the boundary and interior unknowns and lets round-off into
components the problem pins exactly. The solution then grew to 8.5e+04
where the C decays to zero — a qualitative divergence, not a last-bit one.

Switching to KLU's documented default, threshold partial pivoting with a
diagonal preference at `tol = 0.001`, fixed it and made three further
variants byte-identical. The lesson is worth recording: for these matrices
the pivoting rule is output-critical, and matching KLU's was the faithful
choice rather than the merely defensible one.

Raw data: [`ab-host-libm.tsv`](ab-host-libm.tsv), one row per variant, with
the default-build class and the host-libm-build class side by side.

## The variants the libm accounts for

These differ in the default build and match under `--features host-libm`:

| variant | elementary functions on its hot path |
|---|---|
| `cvodes/serial/cvsDiurnal_FSA_kry__-sensi_sim_t` | `sin` in the diurnal source term |
| `idas/serial/idasSlCrank_dns` | `sin`, `cos` in the crank geometry |
| `idas/serial/idasSlCrank_FSA_dns` | same |
| `arkode/C_serial/ark_analytic_lsrk` | `sinh`, `cosh`, `acosh`, `log` (LSRK stage-count formula) |
| `arkode/C_serial/ark_analytic_lsrk_varjac` | same |
| `arkode/C_serial/ark_analytic_lsrk_domeigest` | same |
| `arkode/C_serial/ark_analytic_lsrk_domeigest__arkid.dom_eig_est_init_preprocess_iters_1_sundomeigestimator.max_iters_1` | same |
| `arkode/C_serial/ark_kpr_mri__10_4_0.001_-100_100_0.5_1` | `sin`, `cos` in the reference solution |

The ARKODE **LSRK** entries are not a coincidence and were predictable:
`SUNRsinh`, `SUNRcosh`, `SUNRacosh` and `SUNRlog` are called from exactly
one place in the whole library,
[`crates/arkode_rs/src/arkode_lsrkstep.rs:87`](../../../crates/arkode_rs/src/arkode_lsrkstep.rs:87),
and they feed the formula that chooses the *number of stages*. A last-bit
difference there changes an integer, which changes the method, which
changes everything downstream. The sibling Linux repository observed the
same variants breaking on Arch's glibc 2.44 for the same reason — glibc
changed `sinh`, `cosh` and `acosh` between 2.41 and 2.44.

The rest is ordinary adaptive-integrator chaos: a one-ulp difference in
`sin` inside a right-hand side moves an error estimate, which moves a
step-size decision, which moves the whole trajectory. Note what the
magnitudes actually are — `idasSlCrank_dns` differs in the 13th
significant digit of one printed number, and `ark_kpr_mri` in the third
digit of one error estimate on one of 74 lines.

## Which side is closer to the true answer?

The pure-Rust one, measurably. `tools/libm_differential.sh` measures every
function against a 113-bit `__float128` reference (see
[`../LIBM.md`](../../../LIBM.md)):

| function | pure-Rust max error | host glibc 2.43 max error |
|---|---|---|
| `sin`, `cos`, `atan`, `asin`, `acos` | 0.5000 ulp | 0.5039 – 0.5185 ulp |
| `expm1`, `log1p` | 0.5000 ulp | 0.7420 – 0.7996 ulp |
| `sinh`, `cosh` | 0.5000 ulp | 0.9813 – 1.7510 ulp |
| `exp`, `log`, `acosh` | as glibc (same source) | same |

0.5000 ulp is correct rounding — the smallest error a binary64 result can
have. So on these eight variants the C column is not a target the Rust
column failed to hit; it is the less accurate of the two.

## What would count as a defect

A row of `ab-host-libm.tsv` whose `host_libm_class` is `DIFFERS` **and
whose example is not one of the eleven `*_klu`**. The `*_klu` rows differ
under both builds by construction, because the `host-libm` switch does not
touch the sparse LU — there is no KLU to switch back to. They are covered
instead by the direct verification described above.

On that criterion there are currently no defects. `tools/ab_host_libm.sh`
prints every still-divergent variant under "variants that remain divergent
even with the host libm"; a new non-`klu` entry there must be fixed before
the change lands (`../CLAUDE.md` § "Classifying a divergence").
