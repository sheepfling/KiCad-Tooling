"""Shared host-platform probes."""

from kicad_tooling import platforms


def test_platform_probes_distinguish_windows_and_posix(monkeypatch) -> None:
    monkeypatch.setattr(platforms.sys, "platform", "win32")
    assert platforms.is_windows_host()
    assert not platforms.is_posix_host()

    monkeypatch.setattr(platforms.sys, "platform", "linux")
    assert not platforms.is_windows_host()
    assert platforms.is_posix_host()

    monkeypatch.setattr(platforms.sys, "platform", "wasi")
    assert not platforms.is_windows_host()
    assert not platforms.is_posix_host()
