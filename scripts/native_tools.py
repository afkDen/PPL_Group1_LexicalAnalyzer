"""Discover C compilers or install a pinned portable Windows Clang locally.

Downloads are optional bootstrap operations, never compiler/runtime dependencies.
Official asset and SHA-256: mstorsjo/llvm-mingw release 20261020.
"""

import hashlib
import platform
import shutil
import stat
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

RELEASE = "llvm-mingw-20261020-ucrt-x86_64"
ASSET = RELEASE + ".zip"
URL = f"https://github.com/mstorsjo/llvm-mingw/releases/download/20261020/{ASSET}"
SHA256 = "fd5462b7f5d93b2ff981fcd3f9c7e427e47f3203c64ea91c27bcc444eebd74cd"


def cached_compiler(root: Path) -> Path:
    return root / ".uv-cache" / "native-toolchains" / RELEASE / "bin" / "clang.exe"


def discover_compiler(root: Path, requested: str | None = None) -> str | None:
    """Explicit --cc wins; otherwise prefer this pinned cache, then PATH tools."""
    if requested is not None:
        return shutil.which(requested)
    local = cached_compiler(root)
    if platform.system() == "Windows" and local.is_file():
        return str(local.resolve())
    return shutil.which("gcc") or shutil.which("clang")


def verify_archive(archive: Path) -> None:
    with archive.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != SHA256:
        raise ValueError(f"native archive SHA-256 mismatch: {actual}")


def validate_members(archive: zipfile.ZipFile) -> None:
    """Reject traversal, drive paths and link entries before extracting anything."""
    for item in archive.infolist():
        # ZipInfo normalizes Windows backslashes and truncates NULs in filename.
        # Validate the original archive spelling before those normalizations.
        name = item.orig_filename
        parts = name.split("/")
        if (
            not name
            or "\\" in name
            or ":" in name
            or "\0" in name
            or PurePosixPath(name).is_absolute()
            or PureWindowsPath(name).drive
            or ".." in parts
            or parts[0] != RELEASE
            or stat.S_ISLNK(item.external_attr >> 16)
        ):
            raise ValueError(f"unsafe native archive member: {name!r}")


def install_native(root: Path, *, offline: bool = False) -> Path:
    """Install the pinned complete Windows x64 toolchain without admin or PATH edits."""
    if platform.system() != "Windows" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise ValueError("portable setup supports Windows x64; use --cc for another host")
    root = root.resolve()
    compiler = cached_compiler(root)
    if compiler.is_file():
        return compiler
    downloads = root / ".uv-cache" / "native-downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    archive = downloads / ASSET
    if not archive.is_file():
        if offline:
            raise FileNotFoundError(f"offline native archive not cached: {archive}")
        with tempfile.TemporaryDirectory(prefix="native-download-", dir=downloads) as temporary:
            staged = Path(temporary) / ASSET
            request = urllib.request.Request(URL, headers={"User-Agent": "Ternfold-bootstrap"})
            with (
                urllib.request.urlopen(request, timeout=60) as response,
                staged.open("wb") as stream,
            ):
                shutil.copyfileobj(response, stream)
            verify_archive(staged)
            staged.replace(archive)
    verify_archive(archive)
    toolchains = root / ".uv-cache" / "native-toolchains"
    toolchains.mkdir(parents=True, exist_ok=True)
    destination = toolchains / RELEASE
    if destination.exists():
        raise ValueError(f"incomplete native installation retained for inspection: {destination}")
    with tempfile.TemporaryDirectory(prefix="native-extract-", dir=toolchains) as temporary:
        staging = Path(temporary)
        with zipfile.ZipFile(archive) as contents:
            validate_members(contents)
            contents.extractall(staging)
        extracted = staging / RELEASE
        if not (extracted / "bin" / "clang.exe").is_file():
            raise ValueError("native archive does not contain the expected Clang executable")
        extracted.rename(destination)
    return compiler
