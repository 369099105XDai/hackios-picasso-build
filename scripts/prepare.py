#!/usr/bin/env python3
"""Stage only pinned public patches in a fresh cloud build directory."""
import hashlib
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_SHA = "fdad0de8dc0e75c5ea84762adc03f7232dc91f19"
DXB_SHA = "663906528d1cd5ea8fde7de6f16de73db9511549"
PATCH_SHA = "206eeb417e2cfa5ad9134a36fcadac71bd2d95469590aba375562da02fc530de"
DIAG_PATCH_SHA = "ba2662f0216983a47edcc09a129fb8bf3f1f0f2c1c40b386d9555d0f5602a67c"
VARIANT = "picasso-gcc-diag-v1"
PATCHES = (
    ("9999-picasso-early-framebuffer.patch", "9999-picasso-early-framebuffer.patch", PATCH_SHA),
    # DXB applies patches in lexical order: 10000 would sort before 9999.
    ("10000-picasso-ram-gcc-diag.patch", "zz-picasso-ram-gcc-diag.patch", DIAG_PATCH_SHA),
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def verify_revision(directory, expected):
    actual = subprocess.check_output(
        ["git", "-C", str(directory), "rev-parse", "HEAD"], text=True
    ).strip()
    require(actual == expected, f"unexpected source revision in {directory.name}")


def verify_patches():
    records = []
    for filename, staged_name, expected in PATCHES:
        patch = ROOT / "patches" / filename
        require(patch.is_file() and not patch.is_symlink(), f"invalid patch: {filename}")
        require(hashlib.sha256(patch.read_bytes()).hexdigest() == expected,
                f"patch hash mismatch: {filename}")
        records.append({"filename": filename, "sha256": expected})
    return records


def main():
    upstream, dxb = ROOT / "upstream-sweet", ROOT / "dxb"
    verify_revision(upstream, UPSTREAM_SHA)
    verify_revision(dxb, DXB_SHA)
    verify_patches()
    files = sorted((upstream / "xnu/patches").glob("*.patch"))
    files += sorted((upstream / "xnu/patches").glob("*.sh"))
    require(files and any(p.suffix == ".sh" for p in files), "missing upstream patches")
    files = [(source, source.name) for source in files]
    files.extend((ROOT / "patches" / name, staged_name) for name, staged_name, _ in PATCHES)
    for source, staged_name in files:
        require(source.is_file() and not source.is_symlink(), "unexpected patch source")
        target = dxb / "patches" / staged_name
        require(not target.exists(), f"refusing to replace existing patch {staged_name}")
        shutil.copyfile(source, target)
    script = dxb / "build.sh"
    content = script.read_text()
    before = 'ARCHS="x86_64 arm64e" VALID_ARCHS="x86_64 arm64e"'
    after = 'ARCHS="x86_64 arm64e arm64" VALID_ARCHS="x86_64 arm64e arm64"'
    require(content.count(before) == 1 and after not in content,
            "unexpected libfirehose architecture configuration")
    script.write_text(content.replace(before, after), newline="\n")
    print(f"Prepared {len(files)} public patches for {VARIANT}; enabled arm64 libfirehose.")


if __name__ == "__main__":
    main()
