import winreg
import os
import pathlib
from typing import Literal, Generator
import xml.etree.ElementTree as ElementTree
from pywintrbl.registry_helpers import (
    list_keys,
    get_path_from_hkey,
    get_friendly_hkey_path,
    get_value,
)
from pywintrbl.version import __version__

from rich.console import Console
from rich.terminal_theme import DIMMED_MONOKAI


def hkey_users_to_hkcu(hkey: str) -> str:
    """Converts an HKEY_USERS entry to HKEY_CURRENT_USER removing the user's SID.

    This function assumes the SID is for the current user. In pywintrbl's case,
    it's always for the current user."""
    parts = hkey.split("\\")
    if parts[0] != "HKEY_USERS":
        return hkey

    return "\\".join(["HKEY_CURRENT_USER", *parts[2:]])


def format_exists(path: str | None) -> str:
    """Returns a string indicating whether ``path`` exists."""
    if path and os.path.exists(path):
        return "([green]path exists[/green])"
    elif path:
        return "([red]path does not exist[/red])"
    else:
        return ""


def get_psf_uninstall_entries(
    key: Literal["HKLM", "HKCU"], wow64: Literal["32bit", "64bit"] = "64bit"
) -> Generator[tuple[str, str | None, str], None, None]:
    """Retrieves all uninstall entries with 'Python Software Foundation' as their publisher.

    ``key`` must be either 'HKLM' (HKEY_LOCAL_MACHINE) or 'HKCU' (HKEY_CURRENT_USER).
    ``wow64`` may be either '32bit' or '64bit' (default). This option is only important
    if ``key`` is ``'HKLM'``.

    Returns a tuple of 3 entries: the entry's display name, where it is installed, and the
    entry's corresponding registry key location."""
    if key == "HKCU":
        root_key, wow64_flag = winreg.HKEY_CURRENT_USER, 0
    else:
        root_key = winreg.HKEY_LOCAL_MACHINE
        wow64_flag = (
            winreg.KEY_WOW64_64KEY if wow64 == "64bit" else winreg.KEY_WOW64_32KEY
        )

    with winreg.OpenKey(
        root_key,
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        access=winreg.KEY_READ | wow64_flag,
    ) as uninstall_key:
        for app in list_keys(uninstall_key):
            with winreg.OpenKey(uninstall_key, app) as app_key:
                publisher, _ = get_value(app_key, "Publisher")
                display_name, _ = get_value(app_key, "DisplayName")
                install_source, _ = get_value(app_key, "InstallSource")
                if publisher == "Python Software Foundation":
                    obj_key = get_path_from_hkey(app_key.handle)
                    yield (
                        display_name,
                        install_source,
                        hkey_users_to_hkcu(get_friendly_hkey_path(obj_key)),
                    )


def read_psf_win_apps() -> Generator[tuple[str, str, str], None, None]:
    """Gets all installations of PythonCore runtimes (whose publisher is 'Python Software
    Foundation') from the Microsoft Store.

    **Warning:** This function retrieves data from the WindowsApps directory and hence
    requires administrator privileges.

    Returns a tuple of 3 entries: the display name, the package identifier, and the
    package version.
    """
    apps_path = pathlib.Path(os.path.expandvars(r"%ProgramFiles%\WindowsApps"))

    for entry in apps_path.iterdir():
        if not entry.name.startswith("PythonSoftwareFoundation"):
            continue

        contents = (entry / "AppxManifest.xml").read_text(encoding="utf-8-sig")

        appx_ns = "{http://schemas.microsoft.com/appx/manifest/foundation/windows10}"
        manifest = ElementTree.fromstring(contents)

        text = manifest.findtext(f"{appx_ns}Properties/{appx_ns}DisplayName")
        identity = manifest.find(f"{appx_ns}Identity")

        if text and identity is not None:
            yield (text, identity.attrib["Name"], identity.attrib["Version"])


def get_pep514_entries(
    key: Literal["HKLM", "HKCU"], wow64: Literal["32bit", "64bit"] = "64bit"
) -> Generator[tuple[str, str, str], None, None]:
    """Gets all PythonCore installations registered via PEP 514:

    ``key`` must be either 'HKLM' (HKEY_LOCAL_MACHINE) or 'HKCU' (HKEY_CURRENT_USER).
    ``wow64`` may be either '32bit' or '64bit' (default). This option is only important
    if ``key`` is ``'HKLM'``.

    Returns a tuple of 3 entries: the entry's display name, where it is installed, and the
    entry's corresponding registry key location."""
    if key == "HKCU":
        root_key, wow64_flag = winreg.HKEY_CURRENT_USER, 0
    else:
        root_key = winreg.HKEY_LOCAL_MACHINE
        wow64_flag = (
            winreg.KEY_WOW64_64KEY if wow64 == "64bit" else winreg.KEY_WOW64_32KEY
        )

    with winreg.OpenKey(
        root_key,
        r"SOFTWARE\Python",
        access=winreg.KEY_READ | wow64_flag,
    ) as python_key:
        for company in list_keys(python_key):
            if company != "PythonCore":
                continue

            with winreg.OpenKey(python_key, company) as company_key:
                for tag in list_keys(company_key):
                    with winreg.OpenKey(company_key, tag) as tag_key:
                        display_name = get_value(tag_key, "DisplayName")[0]
                        try:
                            with winreg.OpenKey(tag_key, "InstallPath") as inst_key:
                                install_path = get_value(inst_key, "")[0]
                        except FileNotFoundError:
                            install_path = ""

                        obj_key = get_path_from_hkey(tag_key.handle)
                        yield (
                            display_name,
                            install_path,
                            hkey_users_to_hkcu(get_friendly_hkey_path(obj_key)),
                        )


def get_path_entries() -> list[tuple[pathlib.Path, bool]]:
    """Gets Python-named entries in PATH returning their path and whether they exist."""

    paths = []

    for path_string in os.environ["PATH"].split(os.pathsep):
        if "python" not in path_string.lower():
            continue

        path = pathlib.Path(path_string)
        if not path.exists():
            paths.append((path, False))
            continue

        if path.name == "Scripts":
            for executable in path.glob("*"):
                if executable.name.startswith("pip"):
                    paths.append((executable.parent, True))
        else:
            if (path / "python.exe").exists():
                paths.append((path, True))

    unique_paths = []
    already_seen = []
    for path, exists in paths:
        if path.name in already_seen:
            continue

        unique_paths.append((path, exists))
        already_seen.append(path.name)

    return unique_paths


def main() -> None:
    console = Console(record=True)
    console.print(
        f"[cyan]Python on Windows Troubleshooter v{__version__}[/cyan]",
        justify="center",
    )

    console.print(
        "[yellow]Install Entries from 'Python Software Foundation'[/yellow]",
        justify="center",
    )

    user_entries = get_psf_uninstall_entries("HKCU")
    local_32bit_entries = get_psf_uninstall_entries("HKLM", "32bit")
    local_64bit_entries = get_psf_uninstall_entries("HKLM", "64bit")

    for hive, entries in (
        ("User", user_entries),
        ("Machine (x86)", local_32bit_entries),
        ("Machine (x64)", local_64bit_entries),
    ):
        for display_name, source, regkey in entries:
            source_exists = format_exists(source)

            console.print(f"[magenta]{hive}[/magenta]: [cyan]{display_name}[/cyan]")
            console.print(f"[bold]Installed at[/bold]: {source} {source_exists}")
            console.print(f"[bold]Registry Key[/bold]: {regkey}")
            console.print()

    console.print(
        "[yellow]Microsoft Store installations from 'Python Software Foundation'[/yellow]",
        justify="center",
    )

    try:
        for display_name, identifier, version in read_psf_win_apps():
            console.print(
                f"{display_name} ([bold]id:[/bold] {identifier}, [bold]version:[/bold] {version})"
            )
    except PermissionError:
        console.print(
            "[red]Access to WindowsApps directory requires admin privileges[/red]"
        )
    console.print()

    console.print(
        "[yellow]PythonCore entries via PEP 514 registry[/yellow]", justify="center"
    )

    user_entries = get_pep514_entries("HKCU")
    local_32bit_entries = get_pep514_entries("HKLM", "32bit")
    local_64bit_entries = get_pep514_entries("HKLM", "64bit")

    for hive, entries in (
        ("User", user_entries),
        ("Machine (x86)", local_32bit_entries),
        ("Machine (x64)", local_64bit_entries),
    ):
        try:
            for display_name, install_location, regkey in entries:
                fmt_display_name = display_name or "[red]Unspecified[/red]"
                fmt_install_location = install_location or "[red]Unspecified[/red]"
                location_exists = format_exists(install_location)

                console.print(f"[magenta]{hive}[/magenta]: {fmt_display_name}")
                console.print(
                    f"[bold]Installed At[/bold]: {fmt_install_location} {location_exists}"
                )
                console.print(f"[bold]Registry Key[/bold]: {regkey}")
                console.print()
        except FileNotFoundError:
            continue

    console.print(
        "[yellow]PATH entries with Python-named executables[/yellow]", justify="center"
    )

    for path, exists in get_path_entries():
        if exists:
            fmt_exists = "[green]path exists[/green]"
        else:
            fmt_exists = "[red]path does not exist[/red]"

        console.print(f"{path} ({fmt_exists})")

    console.print()
    console.print("[green]Log file output to pywintrbl.html[/green]")

    with open("pywintrbl.html", "w") as fp:
        fp.write(console.export_html(theme=DIMMED_MONOKAI))


if __name__ == "__main__":
    main()
