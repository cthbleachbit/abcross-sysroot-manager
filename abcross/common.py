import logging
import os
import platform
import re
import subprocess
from enum import Enum
from pathlib import PosixPath
from typing import Optional, List

logger = logging.getLogger("common")


class Architecture(Enum):
    """Hardware architecture supported by AOSC OS"""
    AMD64 = "amd64"
    ARM64 = "arm64"
    LOONGSON3 = "loongson3"
    POWERPC = "powerpc"
    PPC64EL = "ppc64el"
    RISCV64 = "riscv64"
    MIPS64R6EL = "mips64r6el"
    ARMV4 = "armv4"  # retro
    ARMV6HF = "armv6hf"  # retro
    ARMV7HF = "armv7hf"  # retro
    M68K = "m68k"  # retro
    PPC64 = "ppc64"  # retro pre-power 8 big endian ppc 64
    I486 = "i486"

    def qemu_arch(self) -> str:
        """Return architecture name in qemu nomenclature"""
        match self:
            case Architecture.AMD64:
                return "amd64"
            case Architecture.ARM64:
                return "aarch64"
            case Architecture.LOONGSON3:
                return "mips64el"
            case Architecture.POWERPC:
                return "ppc"
            case Architecture.PPC64EL:
                return "ppc64le"
            case Architecture.RISCV64:
                return "riscv64"
            case Architecture.MIPS64R6EL:
                return "mips64el"
            case Architecture.ARMV4 | Architecture.ARMV6HF | Architecture.ARMV7HF:
                return "arm"
            case Architecture.M68K:
                return "m68k"
            case Architecture.PPC64:
                return "ppc64"
            case Architecture.I486:
                return "i386"
            case _:
                raise ValueError

    def qemu_bin(self) -> str:
        return f"qemu-{self.qemu_arch()}-static"

    @staticmethod
    def match_current_arch() -> Optional["Architecture"]:
        """Check whether current system architecture is any of the possible targets"""
        match platform.machine():
            case "x86_64":
                return Architecture.AMD64
            case "aarch64":
                return Architecture.ARM64
            case "riscv64":
                return Architecture.RISCV64
            case "ppc":
                return Architecture.POWERPC
            case "ppc64le":
                return Architecture.PPC64EL
            case "mips64":
                # FIXME: python can't tell apart loongson3 / other flavor of mips
                return None
            case _:  # Retro arches and other stuff is out of scope
                return None

    def have_qemu(self) -> str | None:
        """Return whether qemu static binary or none if this is not found on the system"""
        base_name = self.qemu_bin()
        binfmt_reg_name = f"/proc/sys/fs/binfmt_misc/qemu-{self.qemu_arch()}"
        try:
            with open(binfmt_reg_name, 'r') as binfmt_reg:
                binfmt_reg_content = binfmt_reg.readlines()
        except OSError as e:
            logger.critical(f"Architecture {self} is not registered with binfmt: {e.strerror}")
            return None
        if binfmt_reg_content[0].strip() != "enabled":
            logger.critical(f"Architecture {self} is not enabled with binfmt")
            logger.critical(f"Content of binfmt descriptor:\n{binfmt_reg_content}")
            return None
        match_interp = re.match(f"interpreter (?P<path>.+{base_name})", binfmt_reg_content[1])
        if not match_interp:
            logger.critical(f"Architecture {self} does not have valid interpreter")
            return None
        path_interp = match_interp.group("path")
        if PosixPath(path_interp).resolve().name != base_name:
            logger.critical(f"Architecture {self} has incorrect interpreter {path_interp} instead of {base_name}")
            return None
        return path_interp

    def standard_sysroot(self) -> PosixPath:
        """Returns standard sysroot location for AOSC OS"""
        return PosixPath(f"/var/ab/cross-root/{self.value}")


def privileged_call(argv: List[str], interactive: bool) -> (str, str, int):
    need_sudo = os.geteuid() != 0
    call_args = ["sudo"] if need_sudo else []
    call_args.extend(argv)
    if need_sudo:
        logger.info(f"!!! About to run {call_args}")
    result = subprocess.run(call_args, capture_output=not interactive, text=True)
    return result.stdout, result.stderr, result.returncode


def regular_call(argv: List[str], interactive: bool) -> (str, str, int):
    result = subprocess.run(argv, capture_output=not interactive, text=True)
    return result.stdout, result.stderr, result.returncode
