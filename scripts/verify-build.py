#!/usr/bin/env python3
"""Fail closed on a skipped framebuffer patch; export only three public files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess

from prepare import DXB_SHA, PATCH_SHA, ROOT, UPSTREAM_SHA, require, verify_revision

SOURCE_HASHES = {
    "osfmk/arm64/start.s": "9ac117c33f1acfe863cb87884665c7b2e9bb19cf36b679d091663808d1719080",
    "osfmk/arm64/arm_vm_init.c": "73f1960ed7afbcdb2e692343a4097009549e958e70f9c8fc4a24fba2de033617",
    "osfmk/arm64/sweet_early.c": "672fdfc7a01ade2844e68deb177180768d24491044ab94370c82f556f4c91f80",
}
CONFIGURATION = {
    "macos_version": "13.5", "kernel_config": "DEVELOPMENT",
    "machine_config": "SWEET", "arch_config": "ARM64",
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def verify_sources(source_root):
    actual = {}
    for name, expected in SOURCE_HASHES.items():
        source = source_root / name
        require(source.is_file() and not source.is_symlink(), f"missing source {name}")
        actual[name] = sha256(source.read_bytes())
        require(actual[name] == expected, f"source patch verification failed: {name}")
    return actual


def inspect_kernel(data):
    require(1024 * 1024 <= len(data) < 90 * 1024 * 1024, "unexpected kernel size")
    magic, cpu, subtype, kind, ncmds, sizeofcmds, flags, reserved = struct.unpack_from("<8I", data)
    require((magic, cpu, subtype, kind) == (0xFEEDFACF, 0x0100000C, 0, 2),
            "kernel is not a plain ARM64 Mach-O executable")
    require(0 < ncmds < 128 and 32 + sizeofcmds <= len(data), "invalid command table")
    segments, symtab, entry, cursor = [], None, None, 32
    for _ in range(ncmds):
        require(cursor + 8 <= 32 + sizeofcmds, "truncated load command")
        cmd, size = struct.unpack_from("<2I", data, cursor)
        require(size >= 8 and cursor + size <= 32 + sizeofcmds, "invalid command size")
        if cmd == 0x19:
            require(size >= 72, "truncated segment")
            name = data[cursor + 8:cursor + 24].split(b"\0", 1)[0].decode("ascii")
            va, vsize, offset, length = struct.unpack_from("<4Q", data, cursor + 24)
            # XNU's __CTF is file-only debug data and deliberately has vmsize 0.
            require(offset + length <= len(data), "segment outside kernel")
            require(length <= vsize or (name == "__CTF" and vsize == 0),
                    "loadable segment exceeds virtual size")
            segments.append((name, va, vsize, offset, length))
        elif cmd == 2:
            require(size == 24 and symtab is None, "invalid or duplicate symbol table")
            symtab = struct.unpack_from("<4I", data, cursor + 8)
        elif cmd == 5:
            require(size >= 288 and entry is None, "invalid or duplicate ARM64 thread state")
            flavor, count = struct.unpack_from("<2I", data, cursor + 8)
            require((flavor, count) == (6, 68), "unexpected ARM64 thread flavor")
            entry = struct.unpack_from("<Q", data, cursor + 272)[0]
        cursor += size
    require(cursor == 32 + sizeofcmds, "load command count mismatch")
    require(symtab is not None and entry is not None, "missing entry or symbols")
    require(any(s[0] == "__TEXT_EXEC" and s[1] <= entry < s[1] + s[4]
                for s in segments), "entry not in executable kernel segment")
    symoff, nsyms, stroff, strsize = symtab
    require(symoff + nsyms * 16 <= len(data) and stroff + strsize <= len(data),
            "symbol table outside kernel")
    strings, early_fb = data[stroff:stroff + strsize], []
    for i in range(nsyms):
        strx, kind, section, desc, value = struct.unpack_from("<IBBHQ", data, symoff + i * 16)
        require(strx < strsize, "symbol name outside string table")
        end = strings.find(b"\0", strx)
        require(end >= 0, "unterminated symbol name")
        if strings[strx:end] == b"_early_fb":
            require(kind & 0x0E == 0x0E, "framebuffer symbol is not section-defined")
            early_fb.append(value)
    require(len(early_fb) == 1, "missing or duplicate early framebuffer symbol")
    matches = [s for s in segments if s[0] == "__DATA"
               and s[1] <= early_fb[0] and early_fb[0] + 8 <= s[1] + s[4]]
    require(len(matches) == 1, "framebuffer pointer outside file-backed data")
    segment = matches[0]
    pointer = struct.unpack_from("<Q", data, segment[3] + early_fb[0] - segment[1])[0]
    require(pointer == 0xA0000000, "kernel still has the wrong early framebuffer base")
    return {"entry_va": hex(entry), "early_fb_va": hex(early_fb[0])}


def output(*args):
    return subprocess.check_output(args, text=True).strip()


def collect():
    verify_revision(ROOT / "upstream-sweet", UPSTREAM_SHA)
    verify_revision(ROOT / "dxb", DXB_SHA)
    for key, value in CONFIGURATION.items():
        require(os.environ.get(key.upper()) == value, f"unexpected configuration: {key}")
    source_hashes = verify_sources(ROOT / "dxb/xnu")
    require(sha256((ROOT / "patches/9999-picasso-early-framebuffer.patch").read_bytes())
            == PATCH_SHA, "patch content changed")
    kernel = ROOT / "dxb/fakeroot/System/Library/Kernels/kernel.development.sweet"
    require(kernel.is_file() and not kernel.is_symlink(), "expected kernel artifact absent")
    data = kernel.read_bytes()
    kernel_info = inspect_kernel(data)
    xcode_version = output("xcodebuild", "-version")
    sdk_version = output("xcrun", "--sdk", "macosx", "--show-sdk-version")
    require(xcode_version == "Xcode 15.0.1\nBuild version 15A507", "Xcode changed during build")
    require(sdk_version == "14.0", "unexpected Xcode SDK version")
    repo = os.environ["GITHUB_REPOSITORY"]
    run_id = os.environ["GITHUB_RUN_ID"]
    dependencies = {}
    for name in ("xnu", "bootstrap_cmds", "dtrace", "AvailabilityVersions", "Libsystem",
                 "libplatform", "libdispatch"):
        dependencies[name] = output("git", "-C", str(ROOT / "dxb" / name), "rev-parse", "HEAD")
    kernel_info.update(filename=kernel.name, size=len(data), sha256=sha256(data))
    manifest = {
        "version": 1,
        "purpose": "Full XNU compilation baseline with picasso early framebuffer; not flashable",
        "upstream": {"repository": "dipa-studio/ios-sweet", "commit": UPSTREAM_SHA},
        "build_script": {"repository": "blacktop/darwin-xnu-build", "commit": DXB_SHA},
        "configuration": CONFIGURATION, "source_files": source_hashes,
        "framebuffer_patch_sha256": PATCH_SHA,
        "kernel": kernel_info, "dependencies": dependencies,
        "toolchain": {"xcode_version": xcode_version, "sdk_version": sdk_version,
                      "kdk": "13.5_22G74"},
        "github": {"repository": repo, "sha": os.environ["GITHUB_SHA"],
                   "run_id": run_id, "run_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
                   "run_url": f"https://github.com/{repo}/actions/runs/{run_id}"},
        "runner": {"os": os.environ.get("RUNNER_OS"), "arch": os.environ.get("RUNNER_ARCH"),
                   "image_os": os.environ.get("ImageOS"), "image_version": os.environ.get("ImageVersion")},
    }
    target = ROOT / "out"
    target.mkdir(exist_ok=False)
    shutil.copyfile(kernel, target / kernel.name)
    (target / "SHA256SUMS").write_text(f"{sha256(data)}  {kernel.name}\n", newline="\n")
    (target / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", newline="\n")
    require(sum(p.stat().st_size for p in target.iterdir()) < 100 * 1024 * 1024,
            "artifact bundle exceeds 100 MiB")
    print(json.dumps(manifest, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-sources-only", type=Path,
                        help="only verify the three final source hashes in this XNU tree")
    args = parser.parse_args()
    if args.check_sources_only is not None:
        print(json.dumps(verify_sources(args.check_sources_only), indent=2))
    else:
        collect()


if __name__ == "__main__":
    main()
