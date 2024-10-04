from __future__ import annotations

import ctypes
import winreg
from typing import Any, Generator


def list_keys(key: winreg.HKEYType | int) -> Generator[str, None, None]:
    """Yields all subkeys of ``key``."""
    subkeys, _, _ = winreg.QueryInfoKey(key)
    for idx in range(subkeys):
        yield winreg.EnumKey(key, idx)


def get_value(key: winreg.HKEYType | int, name: str) -> tuple[Any, int]:
    """Gets the value and type corresponding to ``key`` and ``name``."""
    try:
        return winreg.QueryValueEx(key, name)
    except FileNotFoundError:
        # the registry key does not exist
        return (None, -1)


def get_path_from_hkey(handle: int) -> str:
    """Returns the object name of the registry key open at ``handle``."""
    # Invoke the dark arts of ntdll
    ntdll = ctypes.windll.LoadLibrary("ntdll.dll")

    # Docs for ZwQueryKey (NtQueryKey is the user-mode equivalent used here):
    # https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-zwquerykey
    #
    # HANDLE  KeyHandle,
    # int     KeyInformationClass,
    # PVOID   KeyInformation,
    # ULONG   Length,
    # PULONG  ResultLength
    ntdll.NtQueryKey.argtypes = (
        ctypes.c_void_p,
        ctypes.c_byte,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_void_p,
    )
    ntdll.NtQueryKey.restype = ctypes.c_ulong

    # First request should fail with a BUFFER_TOO_SMALL status.
    # This allows us to get the length of the key.
    result_length = ctypes.c_void_p()
    status = ntdll.NtQueryKey(handle, 0x3, 0, 0, ctypes.byref(result_length))
    assert status == 0xC0000023

    # The buffer size is tne result length + 2 bytes for the key length
    buffer_size = (result_length.value + 2) // ctypes.sizeof(ctypes.c_wchar)
    buffer = ctypes.create_unicode_buffer(buffer_size)

    # This request should not fail (0x3 is KEY_NAME_INFORMATION)
    status = ntdll.NtQueryKey(
        handle, 0x3, buffer, result_length.value + 2, ctypes.byref(result_length)
    )
    assert status == 0x0

    # First two chars are for length, the next chars are the actual key
    # (the string is null-terminated hence the -1 at the end)
    return buffer[2:-1]


def get_friendly_hkey_path(path: str) -> str:
    """Converts an object-name path from the kernel to a user mode HKEY registry path."""
    path_parts = list(filter(None, path.split("\\")))
    if path_parts[1] == "MACHINE":
        return "\\".join(part for part in ["HKEY_LOCAL_MACHINE"] + path_parts[2:])
    elif path_parts[1] == "USER":
        return "\\".join(part for part in ["HKEY_USERS"] + path_parts[2:])

    raise ValueError(f"Cannot parse object name: {path!r}")
