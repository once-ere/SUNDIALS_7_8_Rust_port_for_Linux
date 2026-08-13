# Gate B — Rust versus C compiled from the same source, on one machine

**Scope: Ubuntu 26.04 LTS, x86-64, glibc 2.43, gcc 15.2.0, rustc 1.96.1.**
Every number in this directory and its subdirectories was measured there and
nowhere else. It does not carry to musl, to arm64, or to Windows, and the
`glibc 2.43` part matters — see [Why two gates](#why-two-gates).

## Read this first: this is not the gate in `VERIFICATION.md`

The repository measures the port **twice**, against two different references,
on two different machines. Both cover *the same 199 `(example, argv)`
variants*, and both report a count of byte-identical outputs, so it is easy to
read one number as a correction of the other. It is not.

| | **Gate A** | **Gate B** (this directory) |
|---|---|---|
| Rust is compared against | the `.out` files **shipped inside** SUNDIALS 7.8.0 | the upstream C **compiled from source here** |
| machine | Ubuntu 24.04, glibc 2.39, rustc 1.93.1 | Ubuntu 26.04, glibc 2.43, rustc 1.96.1 |
| the Rust build's libm | the **host** C library | the **pure-Rust** `sundials_libm.rs` |
| KLU examples | excluded (20 with SuperLU) | 11 ported and compared, 9 SuperLU still out |
| byte-identical | **153** of 199 | **175** of 199 |
| where it lives | [`VERIFICATION.md`](../../VERIFICATION.md), [`../linux-x86_64-glibc239/`](../linux-x86_64-glibc239/) | here |

175 is not "an improvement on 153". They are answers to different questions:

* **Gate A asks whether the port reproduces the published reference output.**
  That is the harder and more conservative question, and the one a user of
  SUNDIALS actually cares about. Its reference is fixed and external, so it
  cannot be gamed — but it was generated years ago on somebody else's libm,
  and Gate A charges the port for that drift.
* **Gate B asks whether the translation agrees with the C it was translated
  from, holding the machine fixed.** Both binaries are built here, minutes
  apart, by the same toolchain. It cannot be blamed for reference drift, but
  its reference is one this repository produced, so it proves faithfulness of
  translation rather than reproduction of a published result.

Neither supersedes the other. Run

```bash
python3 tools/cross_gate.py
```

to print the cross-tabulation of the two over the shared variant set. It
asserts the variant sets are equal before comparing anything, and every figure
in the next section is its output.

## Why two gates

Three facts fall out of putting them side by side, and each is checkable in
one command.

**1. All 26 of Gate A's divergences are byte-identical to pristine C here.**

Gate A's headline is `153 identical / 26 divergent / 20 excluded, 0 port
defects`. The "0 port defects" rests on a comparison against C built on *that*
machine. Gate B repeats it independently — different distribution, different
glibc, different compiler, different rustc, a year of upstream drift — and all
26 come out identical again. A defect would have had to survive both.

**2. Gate B's 15 divergences decompose exactly, with nothing left over.**

| cause | variants | how it is isolated |
|---|---:|---|
| the pure-Rust libm | 8 | `--features host-libm` restores every one of them to byte-identical |
| the pure-Rust sparse LU | 7 | all `*_klu`; they differ under **both** builds |
| unexplained | **0** | — |

The second row has no control build, because there is nothing to switch back
to: KLU is LGPL and this tree is BSD-3 with no FFI. Those seven are covered
instead by direct verification of the replacement solver — see
[`differences/ATTRIBUTION.md`](differences/ATTRIBUTION.md).

**3. The two experiments name the same eight variants.**

The 8 variants that match the shipped `.out` under Gate A but differ from
pristine C under Gate B are *exactly* the 8 that the `host-libm` control build
flips back to identical. Two experiments with nothing in common but the source
tree — different hosts, different glibc, different references — single out the
same set:

```
ark_analytic_lsrk
ark_analytic_lsrk_domeigest                    (both argv variants)
ark_analytic_lsrk_varjac
ark_kpr_mri            [10 4 0.001 -100 100 0.5 1]
cvsDiurnal_FSA_kry     [-sensi sim t]
idasSlCrank_dns
idasSlCrank_FSA_dns
```

That agreement is why the libm attribution is stated as a measurement rather
than an explanation. The four ARKODE LSRK entries were predictable, too.
`sinh`, `cosh`, `acosh` and `ln` are reached from exactly one module in the
whole library — the wrappers `SUNRsinh`, `SUNRcosh`, `SUNRacosh` and `SUNRlog`
are defined in
[`crates/arkode_rs/src/arkode_lsrkstep.rs:83-98`](../../crates/arkode_rs/src/arkode_lsrkstep.rs:83)
and used from two sites in that same file,
[`:1158`](../../crates/arkode_rs/src/arkode_lsrkstep.rs:1158) and
[`:3255`](../../crates/arkode_rs/src/arkode_lsrkstep.rs:3255). The first
chooses the *number of stages*: a last-bit difference there changes an integer,
which changes the method, which changes every line downstream. Verify the
"one module" part with

```bash
grep -rn 'sun_sinh()\|sun_cosh()\|sun_acosh()\|sun_ln()' crates/ --include=*.rs \
  | grep -v sundials_libm.rs | grep -v /examples/
```

## What is in here

| path | contents |
|---|---|
| [`c-results/`](c-results/) | every upstream C example built and run here: 337 variants, raw stdout/stderr/meta, SHA-256 per capture |
| [`rust-results/`](rust-results/) | every ported Rust example run here: 199 variants, same layout |
| [`differences/`](differences/) | the comparison, one row per variant, plus a unified diff for each non-identical one |
| [`differences/ATTRIBUTION.md`](differences/ATTRIBUTION.md) | the controlled A/B experiment that assigns each divergence to a cause |
| [`differences/ab-host-libm.tsv`](differences/ab-host-libm.tsv) | its raw data: default class and `host-libm` class, side by side |

The `.stdout` files are the bytes the processes wrote. Nothing is filtered,
rounded or edited anywhere in this directory — `IDENTICAL` means the bytes
matched.

## Checking any of it yourself

Any single row, end to end:

```bash
cd evidence/ubuntu-2604-glibc243
cat c-results/raw/ida/serial/idaHeat2D_klu.meta      # binary, argv, cwd, exit, timing
diff c-results/raw/ida/serial/idaHeat2D_klu.stdout \
     rust-results/raw/ida/serial/idaHeat2D_klu.stdout   # silence = identical
```

The whole classification, recomputed from the captures:

```bash
awk -F'\t' 'NR>1{c[$5]++} END{for (k in c) print c[k], k}' \
    evidence/ubuntu-2604-glibc243/differences/index.tsv | sort -rn
```

Regenerating it from nothing takes a C toolchain and about twenty minutes.
The commands are in each subdirectory's `README.md`; they write to the
repository root, and this directory is that output moved here and labelled
with the host, because it is one machine's measurement rather than a property
of the port.

## The 9 that have no Rust counterpart

`NOT_PORTED` covers the `*_sps` and `*_slu` examples, and only those. They
need SuperLU_MT, a third-party sparse-direct C library that a port forbidding
`unsafe`, FFI and external crates cannot call — and which is not in the Ubuntu
archive at any version, so the C side could not build them here either.
Nothing is being hidden by their absence: there is no output on either side.
