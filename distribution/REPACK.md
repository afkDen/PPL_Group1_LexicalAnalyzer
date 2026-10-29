# Documentation release packaging

Use `lexical-clean-repack.yml` to update the all-in-one documentation while
retaining the accepted executables. The workflow does not publish a release.
The existing executable-build workflow is for changes that require new binaries.

## Inputs

Prepare the clean source archive from the reviewed `SOURCE_FILES.txt` allowlist.
Every archive entry must match that list; private files, duplicate entries,
links and extra directory entries are rejected. Verify the exact source ZIP
with the source-build workflow and native Windows checks before release.

For a new release, leave both workflow inputs empty. The workflow creates the
source ZIP from the checked-out commit using explicit .NET ZIP entries from
`SOURCE_FILES.txt`, including dotfiles. No partial release is needed.
The source ZIP and its sidecar are uploaded as `clean-repack-source`.

For re-verifying an already downloadable clean source asset, the workflow also
accepts these optional inputs:

- `source_zip_url`: `https://github.com/afkDen/PPL_Group1_LexicalAnalyzer/releases/download/lexical-submission-clean-2026-10-30/Ternfold_Lexical_Source_2026-10-30_Clean.zip`
- `source_sha256`: the SHA-256 of those exact downloaded source ZIP bytes.

URL mode requires both inputs; its source asset must already be downloadable.
Do not substitute an older ZIP or invent a checksum. The empty-input mode is
the normal path for preparing both archives before publishing them together.

The prior all-in-one input is fixed in the workflow and preparation script:

- Release: `lexical-static-dfa-final-2026-10-30`.
- Asset: `Ternfold_Lexical_Static_DFA_All_In_One_2026-10-30.zip`.
- SHA-256: `a105a379d16a63dc51e423ee49a8d954f75daae3c2ec09344e03d10050ec34ae`.
- Embedded source ZIP SHA-256: `110cfff05ec8b72812f40e9da6fef68b437859d299320848db578ecb3fbbadf1`.

## Gates and artifacts

1. `prepare` downloads both inputs and checks their hashes. It runs the existing
   packaging rejection tests and the new repack tests. Production `.c`, `.h`
   and `.inc` path sets and bytes under `src/` and `include/` must match the
   accepted source. Changes to standalone test/audit tools require fresh source
   checks but do not change the production executable. The script copies all
   three executables and license notices unchanged. Build records retain their
   toolchain data with runner folders replaced by relative paths. New launchers,
   guides, source and root README are manifested. Output: `clean-repack-prepared`.
2. `assemble` validates the payload manifest and embedded source, restores Mac
   executable modes, and writes the final ZIP with a Unix ZIP writer. Output:
   `clean-repack-combined`. This is an intermediate artifact, not an accepted
   release download.
3. `verify` runs the existing fresh-extraction verifiers on `windows-2022`,
   `macos-15` (ARM64) and `macos-15-intel`. Each checks the exact combined ZIP
   checksum, manifest coverage, embedded source, native launcher, valid/invalid
   reports, diagnostic spans and actual DFA transitions. The Mac verifiers also
   check executable modes, architecture, system-library imports and macOS target.
4. `source-check` independently extracts the exact new source ZIP on Windows,
   both Mac architectures and Ubuntu. It checks the pinned source hash, all
   allowlisted entries and extracted bytes, then runs `environment`, `check`
   and `sanitize`. The Windows test compiler is downloaded with a pinned hash.
   These test builds never replace the distributed accepted executables.
5. `verified` runs only after every binary and source job passes. Download artifact
   **`clean-repack-verified`**, containing:
   - `Ternfold_Lexical_All_In_One_2026-10-30_Clean.zip`
   - `Ternfold_Lexical_All_In_One_2026-10-30_Clean.zip.sha256`
   - `Ternfold_Lexical_Source_2026-10-30_Clean.zip`
   - `Ternfold_Lexical_Source_2026-10-30_Clean.zip.sha256`

The artifact names above are exact. Downloading a workflow artifact through the
GitHub UI adds an outer transport ZIP; extract it to obtain the release ZIP and
checksum files. Download this artifact locally, verify both sidecars, and run
fresh source and native bundle verification before publishing both ZIPs together
in `lexical-submission-clean-2026-10-30`. Do not publish the transport ZIP as a
release asset.

The generated root README states the embedded clean source ZIP hash. The payload
manifest independently hashes `source-original.zip`, every extracted source
file, each executable, license and guide. Keep the archive checksum outside the
archive. Preserve historical release assets unchanged.

After publication, run `verify-published-bundle.yml` with the new combined URL,
its actual SHA-256, and the clean source SHA-256 to verify downloaded release
bytes on all three native platforms. Review the source-build and binary-job
results before describing the new release as verified. These procedures do not
claim signing, notarization or support for older macOS versions.

## Local packaging regression commands

Use new output directories for every invocation:

```powershell
./distribution/test-packaging.ps1 -SourceZip SOURCE.zip -SourceSha256 SOURCE_SHA256 -Destination packaging-tests
./distribution/test-repack.ps1 -SourceZip SOURCE.zip -SourceSha256 SOURCE_SHA256 -PriorBundle PRIOR.zip -Destination repack-tests
./distribution/prepare-repack.ps1 -SourceZip SOURCE.zip -SourceSha256 SOURCE_SHA256 -PriorBundle PRIOR.zip -Destination clean-payload
```

The prepared payload is not the final archive: the Unix finalization and all
three native verification jobs are still required.
