# Evidence — Linux / x86-64 / glibc 2.39

Raw artefacts from the verification run behind every claim in
[`../../current_status.md`](../../current_status.md) and Part A of
[`../../VERIFICATION.md`](../../VERIFICATION.md). Committed because
`logs/` is gitignored and a result nobody can inspect is not a result.

| file | produced by | contents |
|---|---|---|
| `host.txt` | — | kernel, glibc, gcc, rustc and CPU of the measuring host |
| `pow_differential.log` | `tools/pow_differential.sh all` | deterministic `pow` vs the native glibc `pow`: 0 mismatches over 5,900,000 domain inputs and 0 over 20,000,000 unrestricted finite inputs |
| `summary.txt` | `tools/verify_examples.sh all` | one line per reference variant: 153 IDENTICAL / 26 DIFF / 20 EXCLUDED |
| `classify_diffs.txt` | `tools/classify_diffs.sh` | second pass over the non-IDENTICAL variants — `EXACT` / `SQUEEZE` (`tr -s ' '`) / `WS` (`diff -w`). A `SQUEEZE same` row means every printed value is byte-identical and only column spacing differs |

Regenerate all four with `tools/wsl_sync_build.sh evidence` from Windows, or
by running the three scripts directly on a Linux host with the upstream
SUNDIALS 7.8.0 C tree as this workspace's parent directory.

`classify_diffs.txt` carries one row the gate does not count as a
divergence: `kinLaplace_picard_kry`, which is `WS same` and is handled by
`verify_examples.sh`'s symmetric noise filter, so it reports IDENTICAL in
`summary.txt`.
