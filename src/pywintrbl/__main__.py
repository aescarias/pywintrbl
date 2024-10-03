import winreg
import os
import pathlib
from typing import Literal, Generator
from pywintrbl.registry_helpers import list_keys, get_path_from_hkey, get_friendly_hkey_path, get_value

from rich.console import Console
from rich.terminal_theme import DIMMED_MONOKAI


def get_uninstall_entries(
    key: Literal["HKLM", "HKCU"], wow64: Literal["32bit", "64bit"] = "64bit"
) -> Generator[tuple[str, str, str], None, None]:
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
                    yield (display_name, install_source, get_friendly_hkey_path(obj_key))


def get_pep514_entries(
    key: Literal["HKLM", "HKCU"], wow64: Literal["32bit", "64bit"] = "64bit"
) -> Generator[tuple[str, str, str], None, None]:
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
                        yield (display_name, install_path, get_friendly_hkey_path(obj_key))


def get_path_entries() -> list[tuple[pathlib.Path, bool]]:
    """Gets Python-named entries in PATH returning the path and whether it exists."""

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
    for (path, exists) in paths:
        if path.name in already_seen:
            continue

        unique_paths.append((path, exists))
        already_seen.append(path.name)

    return unique_paths


def main() -> None:
    console = Console(record=True)
    console.print("[cyan]Python on Windows Troubleshooter v0.1[/cyan]", justify="center")

    console.print("[yellow]Install Entries from 'Python Software Foundation'[/yellow]", justify="center")

    user_entries = get_uninstall_entries("HKCU")
    local_32bit_entries = get_uninstall_entries("HKLM", "32bit")
    local_64bit_entries = get_uninstall_entries("HKLM", "64bit")

    for hive, entries in (
        ("User", user_entries),
        ("Machine (x86)", local_32bit_entries),
        ("Machine (x64)", local_64bit_entries),
    ):
        for display_name, source, regkey in entries:
            console.print(f"[magenta]{hive}[/magenta]: [cyan]{display_name}[/cyan]")
            console.print(f"[bold]Installed at[/bold]: {source}")
            console.print(f"[bold]Registry Key[/bold]: {regkey}")
            console.print()

    console.print("[yellow]PythonCore entries via PEP 514 registry[/yellow]", justify="center")

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

                console.print(f"[magenta]{hive}[/magenta]: {fmt_display_name}")
                console.print(f"[bold]Installed At[/bold]: {fmt_install_location}")
                console.print(f"[bold]Registry Key[/bold]: {regkey}")
                console.print()
        except FileNotFoundError:
            continue

    console.print("[yellow]PATH entries with Python-named executables[/yellow]", justify="center")

    for (path, exists) in get_path_entries():
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
