"""Native setup integrity and path boundaries, without downloading executables."""

import hashlib
import io
import platform
import shutil
import stat
import sys
import urllib.request
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import native_tools as native  # noqa: E402


@pytest.mark.parametrize(
    "name",
    [
        "../escape",
        "/absolute",
        "C:/drive",
        "root/../../escape",
        "wrong/bin/clang.exe",
        native.RELEASE + "/../escape",
        native.RELEASE + "\\escape",
        native.RELEASE + "/file:stream",
        native.RELEASE + "/bad\0name",
    ],
)
def test_archive_members_reject_escape_and_wrong_layout(name: str) -> None:
    buffer = io.BytesIO()
    entry = zipfile.ZipInfo("placeholder")
    entry.filename = name
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(entry, b"payload")
    buffer.seek(0)
    with zipfile.ZipFile(buffer) as archive:
        with pytest.raises(ValueError, match="unsafe"):
            native.validate_members(archive)


def test_archive_rejects_symlink_before_extraction() -> None:
    buffer = io.BytesIO()
    link = zipfile.ZipInfo(native.RELEASE + "/bin/clang.exe")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(link, "outside")
    buffer.seek(0)
    with zipfile.ZipFile(buffer) as archive:
        with pytest.raises(ValueError, match="unsafe"):
            native.validate_members(archive)


def test_hash_mismatch_rejects_archive(tmp_path: Path) -> None:
    archive = tmp_path / "archive.zip"
    archive.write_bytes(b"changed content")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        native.verify_archive(archive)


def test_offline_setup_validates_extracts_and_reuses_without_network(tmp_path: Path) -> None:
    archive = tmp_path / ".uv-cache" / "native-downloads" / native.ASSET
    archive.parent.mkdir(parents=True)
    with zipfile.ZipFile(archive, "w") as contents:
        contents.writestr(native.RELEASE + "/bin/clang.exe", b"test fixture; never executed")
        contents.writestr(native.RELEASE + "/include/stdio.h", b"fixture")
    expected = hashlib.sha256(archive.read_bytes()).hexdigest()
    with (
        patch.object(platform, "system", return_value="Windows"),
        patch.object(platform, "machine", return_value="AMD64"),
        patch.object(native, "SHA256", expected),
        patch.object(urllib.request, "urlopen", side_effect=AssertionError("network")),
    ):
        compiler = native.install_native(tmp_path, offline=True)
        assert compiler.read_bytes() == b"test fixture; never executed"
        assert native.install_native(tmp_path, offline=True) == compiler
        assert native.discover_compiler(tmp_path) == str(compiler.resolve())


def test_offline_missing_archive_and_partial_install_fail_without_mutation(tmp_path: Path) -> None:
    with (
        patch.object(platform, "system", return_value="Windows"),
        patch.object(platform, "machine", return_value="AMD64"),
        patch.object(urllib.request, "urlopen", side_effect=AssertionError("network")),
    ):
        with pytest.raises(FileNotFoundError, match="offline"):
            native.install_native(tmp_path, offline=True)
        destination = native.cached_compiler(tmp_path).parents[1]
        destination.mkdir(parents=True)
        marker = destination / "retained.txt"
        marker.write_bytes(b"user partial installation")
        archive = tmp_path / ".uv-cache" / "native-downloads" / native.ASSET
        archive.write_bytes(b"not a toolchain archive")
        with patch.object(native, "SHA256", hashlib.sha256(archive.read_bytes()).hexdigest()):
            with pytest.raises(ValueError, match="incomplete"):
                native.install_native(tmp_path, offline=True)
        assert marker.read_bytes() == b"user partial installation"


def test_explicit_compiler_request_never_silently_falls_back(tmp_path: Path) -> None:
    with patch.object(shutil, "which", return_value=None) as which:
        assert native.discover_compiler(tmp_path, "missing-compiler") is None
    which.assert_called_once_with("missing-compiler")


def test_unsupported_platform_does_not_attempt_install(tmp_path: Path) -> None:
    with patch.object(platform, "system", return_value="Darwin"):
        with pytest.raises(ValueError, match="Windows x64"):
            native.install_native(tmp_path)
    assert list(tmp_path.iterdir()) == []
