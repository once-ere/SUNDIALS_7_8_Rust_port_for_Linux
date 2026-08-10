//! `sundials_core` — shared library of
//! **SUNDIALS_7_8_Rust_port_for_AppleSilicon_macos**, a pure-Rust
//! line-by-line port of SUNDIALS 7.8.0.
//!
//! # Platform scope
//!
//! The code is portable: `std` only, no `unsafe`, no FFI, no external crates
//! and no `cfg(target_os)`/`cfg(target_arch)` anywhere. It builds
//! warning-free and passes its unit tests on any target Rust supports.
//!
//! Its *verified* behaviour is not portable. The acceptance criterion of this
//! project — byte-identical printed output against the upstream C reference
//! examples — was established only on **macOS running on Apple Silicon
//! (arm64)**, against Apple's libm.
//!
//! The split is exact, and worth knowing precisely:
//!
//! * **Host-dependent** — [`sundials_math::SUNRexp`], `arkode_lsrkstep`'s
//!   `SUNRlog`/`SUNRsinh`/`SUNRcosh`/`SUNRacosh`, and every `sin`, `cos`,
//!   `asin`, `acos`, `atan`, `exp` and `ln` in the examples. These are `f64`
//!   methods of *unspecified precision*: Rust `std` documents them as varying
//!   by platform, and forwards them to the host libm. One ulp of disagreement
//!   forks an adaptive integrator's step-size trajectory, and with it the
//!   printed output.
//! * **Host-independent** — [`sundials_math::SUNRpowerR`], which runs a
//!   ported ARM optimized-routines/musl algorithm and never calls the host
//!   libm; and [`sundials_math::SUNRsqrt`], [`sundials_math::SUNRceil`],
//!   [`sundials_math::SUNRround`], [`sundials_math::SUNRabs`],
//!   [`sundials_math::SUNRcopysign`] and `f64::mul_add`, which are IEEE-754
//!   specified, correctly rounded, and identical on every target.
//!
//! See `README.md` § "Platform scope" and `sundials.md` §9.

#![allow(non_snake_case, non_camel_case_types, non_upper_case_globals)]

pub mod sunadjointcheckpointscheme_fixed;
pub mod sundatanode_inmem;
pub mod sundials_adjointcheckpointscheme;
pub mod sundials_adjointstepper;
pub mod sundials_context;
pub mod sundials_datanode;
pub mod sundials_domeigestimator;
pub mod sundials_errors;
pub mod sundials_futils;
pub mod sundials_hashmap;
pub mod sundials_iterative;
pub mod sundials_linearsolver;
pub mod sundials_logger;
pub mod nvector_manyvector;
pub mod nvector_serial;
pub mod sunadaptcontroller_imexgus;
pub mod sunadaptcontroller_mrihtol;
pub mod sunadaptcontroller_soderlind;
pub mod sundials_adaptcontroller;
pub mod sundials_band;
pub mod sundials_cli;
pub mod sundials_dense;
pub mod sundials_direct;
pub mod sundials_math;
pub mod sundials_stepper;
pub mod sundomeigest_arnoldi;
pub mod sundomeigest_power;
pub mod sunlinsol_band;
pub mod sunlinsol_dense;
pub mod sunlinsol_pcg;
pub mod sunlinsol_spbcgs;
pub mod sunlinsol_spfgmr;
pub mod sunlinsol_spgmr;
pub mod sunlinsol_sptfqmr;
pub mod sundials_matrix;
pub mod sundials_memory;
pub mod sundials_nonlinearsolver;
pub mod sundials_nvector;
pub mod sundials_nvector_senswrapper;
pub mod sundials_profiler;
pub mod sundials_system_memory;
pub mod sundials_types;
pub mod sundials_utils;
pub mod sundials_version;
pub mod sunmatrix_band;
pub mod sunnonlinsol_auto;
pub mod sunnonlinsol_fixedpoint;
pub mod sunnonlinsol_newton;
pub mod sunmatrix_dense;
pub mod sunmatrix_sparse;
pub mod sunstl_vector;
