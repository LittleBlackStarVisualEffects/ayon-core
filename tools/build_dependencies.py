# -*- coding: utf-8 -*-
"""Script to fix frozen dependencies.

Because Pype code needs to run under different versions of Python interpreter
(yes, even Python 2) we need to include all dependencies as source code
without Python's system stuff. Cx-freeze puts everything into lib and compile
it as .pyc/.pyo files and that doesn't work for hosts like Maya 2020 with
their own Python interpreter and libraries.

This script will take ``site-packages`` and copy them to built Pype under
``dependencies`` directory. It will then compare stuff inside with ``lib``
folder in  frozen Pype, removing duplicities from there.

This must be executed after build finished and it is done by build PowerShell
script.

Note: Speedcopy can be used for copying if server-side copy is important for
speed.

"""
import os
import sys
import site
from distutils.util import get_platform
import platform
from pathlib import Path
import shutil
import blessed
import enlighten
import time


term = blessed.Terminal()
manager = enlighten.get_manager()


def _print(msg: str, type: int = 0) -> None:
    """Print message to console.

    Args:
        msg (str): message to print
        type (int): type of message (0 info, 1 error, 2 note)

    """
    if type == 0:
        header = term.aquamarine3(">>> ")
    elif type == 1:
        header = term.orangered2("!!! ")
    elif type == 2:
        header = term.tan1("... ")
    else:
        header = term.darkolivegreen3("--- ")

    print("{}{}".format(header, msg))


def count_folders(path: Path) -> int:
    """Recursively count items inside given Path.

    Args:
        path (Path): Path to count.

    Returns:
        int: number of items.

    """
    cnt = 0
    for child in path.iterdir():
        if child.is_dir():
            cnt += 1
            cnt += count_folders(child)
    return cnt


_print("Starting dependency cleanup ...")
start_time = time.time_ns()

# path to venv site packages
sites = site.getsitepackages()

# WARNING: this assumes that all we've got is path to venv itself and
# another path ending with 'site-packages' as is default. But because
# this must run under different platform, we cannot easily check if this path
# is the one, because under Linux and macOS site-packages are in different
# location.
site_pkg = None
for s in sites:
    site_pkg = Path(s)
    if site_pkg.name == "site-packages":
        break

_print("Getting venv site-packages ...")
assert site_pkg, "No venv site-packages are found."
_print(f"Working with: {site_pkg}", 2)


build_dir = "exe.{}-{}".format(get_platform(), sys.version[0:3])

# create full path
if platform.system().lower() == "darwin":
    build_dir = Path(os.path.dirname(__file__)).parent.joinpath(
        "build",
        "OpenPype.app",
        "Contents",
        "MacOS")
else:
    build_dir = Path(os.path.dirname(__file__)).parent / "build" / build_dir

_print(f"Using build at {build_dir}", 2)
if not build_dir.exists():
    _print("Build directory doesn't exist", 1)
    _print("Probably freezing of code failed. Check ./build/build.log", 3)
    sys.exit(1)

deps_dir = build_dir / "dependencies"

# copy all files
_print("Copying dependencies ...")

total_files = count_folders(site_pkg)
progress_bar = enlighten.Counter(
    total=total_files, desc="Processing Dependencies",
    units="%", color=(53, 178, 202))


def _progress(_base, _names):
    progress_bar.update()
    return []


shutil.copytree(site_pkg.as_posix(),
                deps_dir.as_posix(),
                ignore=_progress)
progress_bar.close()
# iterate over frozen libs and create list to delete
libs_dir = build_dir / "lib"

to_delete = []
# _print("Finding duplicates ...")
deps_items = list(deps_dir.iterdir())
item_count = len(list(libs_dir.iterdir()))
find_progress_bar = enlighten.Counter(
    total=item_count, desc="Finding duplicates", units="%",
    color=(56, 211, 159))

for d in libs_dir.iterdir():
    if (deps_dir / d.name) in deps_items:
        to_delete.append(d)
        # _print(f"found {d}", 3)
    find_progress_bar.update()

find_progress_bar.close()
# add openpype and igniter in libs too
to_delete.append(libs_dir / "openpype")
to_delete.append(libs_dir / "igniter")
to_delete.append(libs_dir / "openpype.pth")
to_delete.append(deps_dir / "openpype.pth")

# delete duplicates
# _print(f"Deleting {len(to_delete)} duplicates ...")
delete_progress_bar = enlighten.Counter(
    total=len(to_delete), desc="Deleting duplicates", units="%",
    color=(251, 192, 32))
for d in to_delete:
    if d.is_dir():
        shutil.rmtree(d)
    else:
        try:
            d.unlink()
        except FileNotFoundError:
            # skip non-existent silently
            pass
    delete_progress_bar.update()

delete_progress_bar.close()

end_time = time.time_ns()
total_time = (end_time - start_time) / 1000000000
_print(f"Dependency cleanup done in {total_time} secs.")
