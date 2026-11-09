#!/usr/bin/env python3
"""Build/test driver cho firmware MCU (không cần make/cmake).

Cach dung:
    python firmware/mcu/tests/build.py test    # build + chay test host
    python firmware/mcu/tests/build.py lib     # build shared library cho sim
    python firmware/mcu/tests/build.py port    # chi compile port STM32L0 (syntax)
    python firmware/mcu/tests/build.py clean   # xoa thu muc build

Tat ca output la ASCII de console Windows khong loi encoding.
"""

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

MCU_DIR = Path(__file__).resolve().parent.parent
BUILD_DIR = MCU_DIR / "build"
INCLUDE_DIR = MCU_DIR / "include"
TESTS_DIR = MCU_DIR / "tests"
SRC_DIR = MCU_DIR / "src"
HAL_HOST_DIR = MCU_DIR / "hal" / "host"
SIM_DIR = MCU_DIR / "sim"

CFLAGS = ["-std=c99", "-Wall", "-Wextra", "-Werror", "-O1", "-g"]


def find_compiler():
    """Thu tu: $CC, roi cc, gcc, clang."""
    candidates = []
    env_cc = os.environ.get("CC", "").strip()
    if env_cc:
        candidates.append(env_cc)
    candidates.extend(["cc", "gcc", "clang"])

    for cand in candidates:
        parts = shlex.split(cand)
        if not parts:
            continue
        exe = parts[0]
        found = shutil.which(exe)
        if found:
            return [found] + parts[1:]
        if os.path.isfile(exe):
            return [exe] + parts[1:]
    return None


def source_files(include_ffi):
    files = sorted(str(p) for p in SRC_DIR.glob("*.c"))
    files += sorted(str(p) for p in HAL_HOST_DIR.glob("*.c"))
    if include_ffi:
        files.append(str(SIM_DIR / "ffi.c"))
    return files


def test_sources():
    return sorted(str(p) for p in TESTS_DIR.glob("test_*.c"))


def run(cmd):
    print("RUN " + " ".join(cmd))
    sys.stdout.flush()
    return subprocess.call(cmd)


def build_test(cc):
    out = BUILD_DIR / ("test_mcu.exe" if os.name == "nt" else "test_mcu")
    cmd = list(cc) + CFLAGS
    cmd += ["-I" + str(INCLUDE_DIR), "-I" + str(TESTS_DIR)]
    cmd += source_files(include_ffi=True)
    cmd += test_sources()
    cmd += ["-o", str(out)]
    if run(cmd) != 0:
        print("BUILD FAILED (test)")
        return 1
    rc = run([str(out)])
    if rc != 0:
        print("TESTS FAILED")
        return 1
    print("TESTS OK")
    return 0


def build_lib(cc):
    if os.name == "nt":
        out = BUILD_DIR / "flytexmcu.dll"
        extra = ["-shared", "-DFSIM_BUILD_DLL"]
    else:
        out = BUILD_DIR / "libflytexmcu.so"
        extra = ["-shared", "-fPIC"]
    cmd = list(cc) + CFLAGS + extra
    cmd += ["-I" + str(INCLUDE_DIR), "-I" + str(TESTS_DIR)]
    cmd += source_files(include_ffi=True)
    cmd += ["-o", str(out)]
    if run(cmd) != 0:
        print("BUILD FAILED (lib)")
        return 1
    print("LIB OK " + str(out))
    return 0


def build_port(cc):
    port = MCU_DIR / "hal" / "stm32l0" / "port_stm32l0.c"
    out = BUILD_DIR / "port_stm32l0.o"
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    cmd = list(cc) + CFLAGS
    cmd += ["-DFLYTEX_TARGET_STM32L0", "-I" + str(INCLUDE_DIR), "-c", str(port), "-o", str(out)]
    if run(cmd) != 0:
        print("BUILD FAILED (port)")
        return 1
    print("PORT OK " + str(out))
    return 0


def clean():
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
        print("CLEAN OK " + str(BUILD_DIR))
    else:
        print("CLEAN OK (nothing to remove)")
    return 0


def main(argv):
    if len(argv) != 2 or argv[1] not in ("test", "lib", "port", "clean"):
        print("usage: build.py {test|lib|port|clean}")
        return 1

    action = argv[1]
    if action == "clean":
        return clean()

    cc = find_compiler()
    if not cc:
        print("FAILED: no C compiler found (set CC or install cc/gcc/clang)")
        return 1
    print("CC " + " ".join(cc))

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    if action == "port":
        return build_port(cc)
    if action == "test":
        return build_test(cc)
    return build_lib(cc)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
