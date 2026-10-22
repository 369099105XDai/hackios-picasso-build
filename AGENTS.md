# Picasso XNU cloud build

Read README.md and the workflow before making changes. This repository contains
only a public build recipe and the reviewed early-framebuffer source patch.

- Keep upstream revisions and the Xcode version explicit. Do not silently move
  to a newer toolchain when the required runner or Xcode is unavailable.
- The only trigger is workflow_dispatch. Do not add push, schedule, pull-request,
  release, deployment, device operations, or paid runner triggers.
- Preserve contents: read and disabled checkout credential persistence.
- Do not upload device identifiers, partition backups, DTBs, calibration,
  credentials, SDK/KDK archives, build trees, support libraries, or iOS images.
- The artifact allowlist is the compiled kernel, SHA256SUMS and build-manifest.json.
  Keep its total size below 100 MiB and retention at one day.
- A successful build is not a bootable phone image or proof of driver support.
  Hardware testing and Android packaging belong to a separate local project.
- Do not force-push or rewrite history. Remote changes follow the user's scope.

Local source validation: `python3 scripts/verify-build.py --help`.
The complete build requires the pinned macOS/Xcode environment in the workflow.
