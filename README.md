# Picasso XNU cloud build

Build the known XNU baseline for Redmi K30 5G / picasso on a GitHub-hosted Mac.
The recipe adds the four reviewed early-framebuffer address changes to the
existing SWEET kernel sources. It does not contain a phone installer, Android
boot image, device backup, Apple userland, or an adapted touch/USB driver.

The baseline uses [ios-sweet](https://github.com/dipa-studio/ios-sweet) commit
`fdad0de8dc0e75c5ea84762adc03f7232dc91f19` and
[darwin-xnu-build](https://github.com/blacktop/darwin-xnu-build) commit
`663906528d1cd5ea8fde7de6f16de73db9511549`. The configuration is
macOS source release 13.5 / XNU 8796.141.3, ARM64, DEVELOPMENT, SWEET.
The [upstream baseline run](https://github.com/dipa-studio/ios-sweet/actions/runs/39158169212)
completed on 2026-10-18 using Xcode 15.0.1 build 15A507 and KDK 13.5 build 22G74.
This repository's own build must still succeed before the cloud path is verified.

## Run

Open **Actions → Build picasso XNU baseline → Run workflow**. There is no automatic
push trigger. The job fetches pinned public sources, requires Xcode 15.0.1,
compiles the full kernel, and verifies the final hashes of the three patched
source files. Missing or silently skipped framebuffer patches fail the job.

On success, download **picasso-xnu-baseline** within one day. Its three files are:

- `kernel.development.sweet`: a compiled ARM64 Mach-O kernel, not a flashable image.
- `SHA256SUMS`: checksum of that kernel.
- `build-manifest.json`: source revisions, final source hashes, toolchain and run provenance.

The uploader accepts only these files, with a combined size below 100 MiB. It
does not upload the SDK, KDK, support archives, or complete build directory.
Build logs remain in GitHub Actions. The cloud job has no phone connection.

## Toolchain availability

As checked on 2026-10-22, the
[macos-14 image](https://github.com/actions/runner-images/blob/main/images/macos/macos-14-Readme.md)
includes Xcode 15.0.1. GitHub has announced that this image becomes unsupported
on **2026-11-02**. This is a short-term verified baseline, not a durable runner
guarantee. The workflow fails immediately if the exact Xcode is absent.

The current macos-15 image does not list Xcode 15. Xcode 16's IIG generates an
IORPC ABI that this XNU version does not accept without further changes. Merely
changing the runner label is not a validated migration; that work needs a
separate build experiment.

## Attribution

The workflow is derived from ios-sweet's MIT-licensed build recipe. Downloaded
Apple open-source projects, BearSSL and the KDK retain their own terms. This
repository's MIT license does not relicense those dependencies or Apple userland.
