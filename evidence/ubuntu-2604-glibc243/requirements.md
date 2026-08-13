# requirements.md — what this machine has, and what it is missing

**Machine of record.** Ubuntu 26.04 LTS ("Resolute Raccoon"), x86-64,
glibc 2.43, gcc 15.2.0, cmake 4.2.3, rustc/cargo 1.96.1, 24 cores,
NVIDIA GeForce RTX 5090 Laptop GPU (driver 595.84, CUDA 13.1).
Everything in `c-results/`, `rust-results/` and `differences/` was produced
on this machine.

Regenerate the probe table yourself at any time — it needs no root and
installs nothing:

```bash
tools/c_requirements.sh
```

---

## 1. Status table (probed, not assumed)

"Present" means the headers and libraries are installed. Whether SUNDIALS
can actually *use* them is a separate question, answered in §3.

| component | installed | usable by the build | what it unlocks | apt package |
|---|---|---|---|---|
| C compiler (cc) | yes | yes | everything | `gcc` |
| C++ compiler | yes | yes | `examples/*/CXX_*` | `g++` |
| Fortran compiler | yes | yes | `examples/*/F2003_*` | `gfortran` |
| CMake | yes | yes | the whole C build | `cmake` |
| OpenMP runtime | yes | yes | `examples/*/C_openmp` | ships with `gcc` |
| pthreads | yes | yes | the pthreads NVector | ships with glibc |
| libquadmath | yes | yes | the ulp figures in `LIBM.md` | ships with `gcc` |
| BLAS / LAPACK | yes | yes | the `*_dnsL` / `*_bndL` examples | `libblas-dev` `liblapack-dev` |
| MPI (OpenMPI) | yes | yes | `parallel`, `C_parallel`, `CXX_parallel`, `F2003_parallel` | `libopenmpi-dev` |
| KLU (SuiteSparse) | yes | yes | the 11 `*_klu` examples | `libsuitesparse-dev` |
| hypre | yes | yes | `parhyp`, `C_parhyp`, `CXX_parhyp` | `libhypre-dev` |
| **PETSc** | yes | **no** — §3.1 | `petsc`, `C_petsc` | `petsc-dev` |
| **SuperLU_DIST** | yes | **no** — §3.2 | `superludist`, `CXX_superludist` | `libsuperlu-dist-dev` |
| **Kokkos** | yes | **no** — §3.3 | `cvode/kokkos` | `libkokkos-dev` |
| **Trilinos (Tpetra)** | yes | **no** — §3.4 | `ida/trilinos` | `libtrilinos-tpetra-dev` + `libtrilinos-teuchos-dev` |
| **CUDA 13.1 + RTX 5090** | yes | **no** — §3.5 | `cuda`, `mpicuda` | already installed |
| **MAGMA** | yes | **no** — §3.6 | `cvode/magma` | `libmagma-dev` |
| **SuperLU_MT** | **no** | no | the 9 `*_sps` / `*_slu` examples | _not packaged for Ubuntu_ |
| **Ginkgo** | **no** | no | `cvode/ginkgo` | _not packaged for Ubuntu_ |
| **RAJA** | **no** | no | `*/raja`, `mpiraja` | _not packaged for Ubuntu_ |
| **oneMKL / SYCL** | **no** | no | `CXX_onemkl`, `CXX_sycl` | _not packaged for Ubuntu_ |
| **XBraid** | **no** | no | `arkode/CXX_xbraid` | _not packaged for Ubuntu_ |

## 2. What was installed for this work

```bash
sudo apt install libopenmpi-dev libsuitesparse-dev libhypre-dev petsc-dev libsuperlu-dist-dev libtrilinos-tpetra-dev libkokkos-dev libmagma-dev
```

Effect, measured: the C example build went from **164 binaries to 233**, and
the executed variant set from 259 to the number in
[`c-results/README.md`](c-results/README.md). MPI, KLU and hypre all became
usable; the other four did not, for the reasons in §3.

`libtrilinos-teuchos-dev` was installed afterwards, on the evidence in
§3.4. It removed the error it was diagnosed for, but did not make Trilinos
usable: the failure simply moved one layer down, into the same broken
Kokkos package described in §3.3. Both are now blocked by that one Ubuntu
bug.

## 3. Installed but not usable, with the exact reason

`tools/c_build.sh` enables optional backends as a **ladder**: it tries the
full set, then drops entries one at a time until CMake both configures and
builds. The level that succeeded is printed and logged. Each diagnosis
below was then confirmed by configuring that backend *in isolation*, so it
is not an artefact of the ladder's drop order.

The set that works on this machine is **MPI + LAPACK + KLU + hypre**.

### 3.1 PETSc — index-width mismatch with SUNDIALS

```
src/sunnonlinsol/petscsnes/sunnonlinsol_petscsnes.c:352:54: error:
  passing argument 2 of 'SNESGetIterationNumber' from incompatible pointer type
  expected 'PetscInt *' {aka 'int *'} but argument is of type 'sunindextype *' {aka 'long int *'}
```

SUNDIALS defaults to a 64-bit `sunindextype`; Ubuntu's PETSc 3.24 is built
with a 32-bit `PetscInt`. gcc 15 treats the mismatch as an error rather
than a warning. Not a packaging fault on either side — the two were
configured with different index widths.

*Workaround, not applied here:* rebuild with `-DSUNDIALS_INDEX_SIZE=32`.
That changes the index type of the whole library, so its example outputs
would no longer be the same configuration the Rust port is compared
against. It is left off deliberately.

### 3.2 SuperLU_DIST — upstream find-module cannot read Ubuntu's config header

```
Could NOT find SUPERLUDIST (missing: SUPERLUDIST_INDEX_SIZE)
  (found suitable version "9.2.1", minimum required is "7.0.0")
  cmake/tpl/FindSUPERLUDIST.cmake:157
```

The library is found and its version accepted, but
`FindSUPERLUDIST.cmake` derives `SUPERLUDIST_INDEX_SIZE` by grepping
`superlu_dist_config.h` for `#define XSDK_INDEX_SIZE 64`. Ubuntu's header
instead contains `/* #undef XSDK_INDEX_SIZE */` followed by an `#if
defined(...)` guard, and the module leaves the variable unset. Passing
`-DSUPERLUDIST_INDEX_SIZE=32` on the command line does not help, because
the module re-`set(... CACHE ... FORCE)`s it. This is a SUNDIALS 7.8.0
find-module limitation.

### 3.3 Kokkos — the Ubuntu package's CMake config is broken

```
The imported target "Kokkos::kokkosalgorithms" references the file
   "/usr/lib/x86_64-linux-gnu/libkokkosalgorithms.a"
but this file does not exist.
```

`libkokkos-dev` 5.0.2-2 installs `libkokkoscore.so` and
`libkokkoscontainers.so` and nothing else, yet its CMake config declares
four `STATIC IMPORTED` targets — including `kokkosalgorithms` and
`kokkossimd`, whose `.a` files exist nowhere on the system. In Kokkos 5.x
those components are header-only (`/usr/include/kokkos/Kokkos_StdAlgorithms.hpp`,
`/usr/include/kokkos/std_algorithms/`), so the archives are not merely
missing — they should not exist at all, and the packaged config is simply
wrong. Nothing on the SUNDIALS side can work around it, and it blocks
Trilinos too (§3.4).

### 3.4 Trilinos — a missing dependency, and then the Kokkos bug

Trilinos failed twice, for two different reasons. The first was a genuine
missing dependency:

```
CMake Error at .../cmake/TpetraCore/TpetraCoreConfig.cmake:202 (include):
  include could not find requested file:
    /usr/lib/x86_64-linux-gnu/cmake/TpetraCore/../Teuchos/TeuchosConfig.cmake
```

`libtrilinos-tpetra-dev` does not depend on the Teuchos development
package, but its CMake config includes it. Installing
`libtrilinos-teuchos-dev` fixed that error exactly as predicted — and
exposed the next one:

```
CMake Error at .../cmake/Kokkos/KokkosTargets.cmake:130 (message):
  The imported target "Kokkos::kokkosalgorithms" references the file
     "/usr/lib/x86_64-linux-gnu/libkokkosalgorithms.a"
  but this file does not exist.
```

That is §3.3 again. `TrilinosConfig.cmake` lists `Kokkos` among its
required components, and there is exactly one Kokkos CMake package on the
system — the broken one. `libtrilinos-kokkos-dev` does not help: Trilinos
16.1 resolves the component through
`/usr/lib/x86_64-linux-gnu/cmake/Kokkos` either way.

**So Trilinos is not fixable by installing packages on this machine.** It
becomes usable only when the `libkokkos-dev` CMake config stops declaring
static targets for components Kokkos 5.x ships as header-only.

### 3.5 CUDA — nvcc 13.1 headers clash with glibc 2.43

```
/usr/include/x86_64-linux-gnu/bits/mathcalls.h(206): error: exception
  specification is incompatible with that of previous function "rsqrt"
  (declared at line 629 of .../crt/math_functions.h)
```

The GPU and driver are fine — this fails during CMake's compiler
identification, before any SUNDIALS code is reached. glibc 2.41 added
`rsqrt` to `<math.h>`; CUDA 13.1's `crt/math_functions.h` declares it with
an incompatible exception specification. It needs a CUDA release that
knows about the newer glibc; no build flag avoids it.

### 3.6 MAGMA — blocked by 3.5

```
SUNDIALS_MAGMA_BACKENDS includes CUDA but CUDA is not enabled.
```

MAGMA is installed (in `/usr/lib`, not the multiarch directory) and would
be usable as soon as CUDA is.

## 4. Cannot be fixed with apt at all

| component | why | consequence |
|---|---|---|
| **SuperLU_MT** | not in the Ubuntu archive at any version; upstream ships source only | the 9 `*_sps` / `*_slu` examples cannot be built. They are also 9 of the 20 the Rust port does not translate, so no comparison is lost. |
| **Ginkgo, RAJA, XBraid, oneMKL** | not in the Ubuntu archive | 8 GPU / parallel-framework examples cannot be built. None has a serial Rust counterpart. |

## 5. Rust-side requirements

The Rust workspace deliberately has **no dependencies at all** — no
external crates, no build script, no system library beyond what `std`
itself links:

```bash
cargo build --workspace        # nothing is downloaded
cargo test  --workspace --lib
```

`cargo` was therefore never used to install a package, and no package name
needed to be added to this file on the Rust side. That is a design
constraint of the port (`CLAUDE.md` hard rule 2), not an accident.

Optional, and only for regenerating documentation rather than for building:

| tool | used by | needed? |
|---|---|---|
| `python3` (stdlib only) | `tools/gen_libm_constants.py`, `tools/compare_results.py`, `tools/make_reports.py` | for the libm tables and the report generation |
| `python3` + `mpmath` | independent cross-check of the libm tables | optional; `pip install mpmath` |
| `libquadmath` (ships with gcc) | `tools/libm_oracle.c` | without it the differential still runs, but reports agreement only, not ulp accuracy |

## 6. The one coverage gap

The 11 `*_klu` examples now **build and run on the C side** but have no
pure-Rust counterpart, because KLU is a third-party sparse-direct C library
and this port forbids FFI. Closing that gap means implementing a sparse
direct solver inside `sundials_core`. It is out of scope here and is
recorded as a gap rather than papered over — see
[`rust-results/README.md`](rust-results/README.md).
