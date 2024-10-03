# Python Install Tracer for Windows

This is a troubleshooting tool designed to look for traces of PythonCore (CPython/python.org) installations on Windows.

**Because this project is currently experimental, it provides no way of removing these traces. You will have to do this manually (or alternatively with third-party removal tools).**

## Why?

It is common for users to reinstall or modify their existing Python installations. Unfortunately, uninstallers in general do a pretty subpar job at removing all traces of what they installed. This can cause problems when installing Python again or adding newer versions, leading to some of the following issues:

- The installer complains about a "newer version of Python" being installed.
- The installer "cancels" the installation with no apparent reason.
- The installer fails with a "fatal error" with a reason only decipherable by reading the logs.

## How do I use it?

A precompiled binary for Windows is available for you to run in Releases. You will need to have the [Microsoft VC++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170#latest-microsoft-visual-c-redistributable-version) installed to be able to run the troubleshooter.

If you have a working copy of Python available, you can also use this project as a package.

```sh
# clone the repository
git clone https://github.com/aescarias/pywintrbl
# install the package
py -m pip install -e .
# run it
py -m pywintrbl
```

## How does this work?

Python Install Tracer scans multiple common locations where Python and its install files are created. It also checks the Windows registry for signs of an installation on your device.

### Locations scanned

- The PEP 514 registry at `HKLM\SOFTWARE\Python\PythonCore` (and its user equivalent at HKCU)
- The uninstall registry at `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall` (and its user equivalent at HKCU)
- The PATH environment variable.
