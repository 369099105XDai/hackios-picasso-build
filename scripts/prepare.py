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


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def verify_revision(directory, expected):
    actual = subprocess.check_output(
        ["git", "-C", str(directory), "rev-parse", "HEAD"], text=True
    ).strip()
    require(actual == expected, f"unexpected source revision in {directory.name}")


def main():
    upstream, dxb = ROOT / "upstream-sweet", ROOT / "dxb"
    verify_revision(upstream, UPSTREAM_SHA)
    verify_revision(dxb, DXB_SHA)
    patch = ROOT / "patches/9999-picasso-early-framebuffer.patch"
    require(hashlib.sha256(patch.read_bytes()).hexdigest() == PATCH_SHA,
            "framebuffer patch hash mismatch")
    files = sorted((upstream / "xnu/patches").glob("*.patch"))
    files += sorted((upstream / "xnu/patches").glob("*.sh"))
    require(files and any(p.suffix == ".sh" for p in files), "missing upstream patches")
    files.append(patch)
    for source in files:
        require(source.is_file() and not source.is_symlink(), "unexpected patch source")
        target = dxb / "patches" / source.name
        require(not target.exists(), f"refusing to replace existing patch {source.name}")
        shutil.copyfile(source, target)
    script = dxb / "build.sh"
    content = script.read_text()
    before = 'ARCHS="x86_64 arm64e" VALID_ARCHS="x86_64 arm64e"'
    after = 'ARCHS="x86_64 arm64e arm64" VALID_ARCHS="x86_64 arm64e arm64"'
    require(content.count(before) == 1 and after not in content,
            "unexpected libfirehose architecture configuration")
    script.write_text(content.replace(before, after), newline="\n")
    print(f"Prepared {len(files)} public patches; enabled arm64 libfirehose.")


if __name__ == "__main__":
    main()
