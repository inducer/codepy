"""
:mod:`codepy.jit` -- Compilation and Linking of C Source Code
-------------------------------------------------------------

.. autofunction:: extension_file_from_string
.. autofunction:: extension_from_string
"""


__copyright__ = """
Copyright (C) 2009-17 Andreas Kloeckner
Copyright (C) 2017 Nick Curtis
"""

__license__ = """
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from types import ModuleType
from typing import Any, NamedTuple

from typing_extensions import override

from codepy.toolchain import GCCLikeToolchain, Toolchain


logger = logging.getLogger(__name__)


def _erase_dir(dir: str) -> None:
    for name in os.listdir(dir):
        os.unlink(os.path.join(dir, name))

    os.rmdir(dir)


def extension_file_from_string(
        toolchain: Toolchain,
        ext_file: str,
        source_string: str,
        source_name: str = "module.cpp",
        debug: bool = False) -> None:
    """Using *toolchain*, build the extension file named *ext_file*
    from the source code in *source_string*, which is saved to a
    temporary file named *source_name*. Raise :exc:`~codepy.CompileError` in
    case of error.

    If *debug* is True, show commands involved in the build.
    """
    from tempfile import mkdtemp
    src_dir = mkdtemp()

    source_file = os.path.join(src_dir, source_name)
    with open(source_file, "w") as outf:
        _ = outf.write(str(source_string))

    try:
        toolchain.build_extension(ext_file, [source_file], debug=debug)
    finally:
        _erase_dir(src_dir)


class CleanupBase(ABC):
    @abstractmethod
    def clean_up(self) -> None:
        pass

    @abstractmethod
    def error_clean_up(self) -> None:
        pass


class CleanupManager(CleanupBase):
    def __init__(self) -> None:
        self.cleanups: list[CleanupBase] = []

    def register(self, c: CleanupBase) -> None:
        self.cleanups.insert(0, c)

    @override
    def clean_up(self) -> None:
        for c in self.cleanups:
            c.clean_up()

    @override
    def error_clean_up(self) -> None:
        for c in self.cleanups:
            c.error_clean_up()


class TempDirManager(CleanupBase):
    def __init__(self, cleanup_m: CleanupManager) -> None:
        from tempfile import mkdtemp

        self.path: str = mkdtemp()
        cleanup_m.register(self)

    def sub(self, n: str) -> str:
        return os.path.join(self.path, n)

    @override
    def clean_up(self) -> None:
        _erase_dir(self.path)

    @override
    def error_clean_up(self) -> None:
        pass


class CacheLockManager(CleanupBase):
    def __init__(self,
                 cleanup_m: CleanupManager,
                 cache_dir: str | None = None,
                 sleep_delay: int = 1) -> None:
        if cache_dir is not None:
            self.lock_file: str = os.path.join(cache_dir, "lock")

            attempts = 0
            while True:
                try:
                    self.fd: int = os.open(
                            self.lock_file,
                            os.O_CREAT | os.O_WRONLY | os.O_EXCL)
                    break
                except OSError:
                    pass

                from time import sleep
                sleep(sleep_delay)

                attempts += 1

                if attempts > 10:
                    from warnings import warn
                    warn(f"could not obtain lock -- delete '{self.lock_file}' "
                         "if necessary", stacklevel=2)

            cleanup_m.register(self)

    @override
    def clean_up(self) -> None:
        os.close(self.fd)
        os.unlink(self.lock_file)

    @override
    def error_clean_up(self) -> None:
        pass


class ModuleCacheDirManager(CleanupBase):
    def __init__(self, cleanup_m: CleanupManager, path: str) -> None:
        try:
            os.mkdir(path)
            cleanup_m.register(self)
            existed = False
        except OSError:
            existed = True

        self.path: str = path
        self.existed: bool = existed

    def sub(self, n: str) -> str:
        return os.path.join(self.path, n)

    def reset(self) -> None:
        _erase_dir(self.path)
        os.mkdir(self.path)

    @override
    def clean_up(self) -> None:
        pass

    @override
    def error_clean_up(self) -> None:
        _erase_dir(self.path)


def extension_from_string(
        toolchain: Toolchain,
        name: str,
        source_string: str | list[str],
        source_name: str | list[str] = "module.cpp",
        cache_dir: str | None = None,
        debug: bool = False,
        debug_recompile: bool = True,
        sleep_delay: int = 1) -> ModuleType:
    """Return a reference to the extension module *name*, which can be built
    from the source code in *source_string* if necessary. Raise
    :exc:`codepy.CompileError` in case of error.

    Compiled code is cached in *cache_dir* and available immediately if it has
    been compiled at some point in the past. Compiler and Python API versions
    as well as versions of include files are taken into account when examining
    the cache. If *cache_dir* is ``None``, a default location is assumed.  If
    it is ``False``, no caching is performed. Proper locking is performed on
    the cache directory. Simultaneous use of the cache by multiple processes
    works as expected, but may lead to delays because of locking.  By default,
    a process waits for 1 second before reattempting to acquire the *cache_dir*
    lock. A different waiting time can be specified through *sleep_delay*.

    The code in *source_string* will be saved to a temporary file named
    *source_name* if it needs to be compiled.

    If *debug* is ``True``, commands involved in the build are printed.

    If *debug_recompile*, messages are printed indicating whether a
    recompilation is taking place.
    """
    _checksum, mod_name, ext_file, _recompiled = (
        compile_from_string(toolchain, name, source_string, source_name=source_name,
                            cache_dir=cache_dir, debug=debug,
                            debug_recompile=debug_recompile,
                            object=False, sleep_delay=sleep_delay))

    # try loading it
    from codepy.tools import load_dynamic
    return load_dynamic(mod_name, ext_file)


class _InvalidInfoFileError(RuntimeError):
    pass


class _Dependency(NamedTuple):
    name: str
    mtime: float
    md5: str


@dataclass(frozen=True)
class _SourceInfo:
    dependencies: list[_Dependency]
    source_name: list[str]


def compile_from_string(
        toolchain: Toolchain,
        name: str,
        source_string: str | bytes | list[str] | list[bytes],
        *,
        source_name: str | list[str] | None = None,
        cache_dir: str | None = None,
        debug: bool = False,
        debug_recompile: bool = True,
        object: bool = False,
        source_is_binary: bool = False,
        sleep_delay: int = 1) -> tuple[str, str, str, bool]:
    """Returns a tuple: ``(checksum, mod_name, file_name, recompiled)``.
    *mod_name* is the name of the module represented by a compiled object,
    *file_name* is the name of the compiled object, which can be built from the
    source code(s) in *source_strings* if necessary,
    *recompiled* is *True* if the object had to be recompiled, *False* if the cache
    is hit.

    Raises :exc:`~codepy.CompileError` in case of error.  The *mod_name* and *file_name*
    are designed to be used with ``load_dynamic`` to load a Python module from
    this object, if desired.

    Compiled code is cached in *cache_dir* and available immediately if it has
    been compiled at some point in the past.  Compiler and Python API versions
    as well as versions of include files are taken into account when examining
    the cache. If *cache_dir* is ``None``, a default location is assumed. If it
    is ``False``, no caching is performed.  Proper locking is performed on the
    cache directory.  Simultaneous use of the cache by multiple processes works
    as expected, but may lead to delays because of locking. By default, a
    process waits for 1 second before reattempting to acquire the *cache_dir*
    lock. A different waiting time can be specified through *sleep_delay*.

    The code in *source_string* will be saved to a temporary file named
    *source_name* if it needs to be compiled.

    If *debug* is ``True``, commands involved in the build are printed.

    If *debug_recompile*, messages are printed indicating whether a
    recompilation is taking place.

    If *source_is_binary*, the source string is a compile object file and
    should be treated as binary for read/write purposes
    """
    if not isinstance(toolchain, GCCLikeToolchain):
        raise TypeError(f"Unsupported toolchain type: {type(toolchain)}")

    if source_name is None:
        source_name = ["module.cpp"]

    # first ensure that source strings and names are lists
    if isinstance(source_string, str):
        source_string = [source_string]

    if source_is_binary and isinstance(source_string, bytes):
        source_string = [source_string]

    if isinstance(source_name, str):
        source_name = [source_name]

    if cache_dir is None:
        import sys

        import platformdirs

        cache_dir = os.path.join(
                platformdirs.user_cache_dir("codepy", "codepy"),
                "codepy-compiler-cache-v5-py{}".format(
                    ".".join(str(i) for i in sys.version_info)))

        try:
            os.makedirs(cache_dir)
        except OSError as e:
            from errno import EEXIST
            if e.errno != EEXIST:
                raise

    def get_file_md5sum(fname: str) -> str:
        import hashlib
        checksum = hashlib.md5()

        with open(fname, "rb") as inf:
            checksum.update(inf.read())

        return checksum.hexdigest()

    def get_dep_structure(source_paths: list[str]) -> list[_Dependency]:
        deps = toolchain.get_dependencies(source_paths)
        return [_Dependency(dep, os.stat(dep).st_mtime, get_file_md5sum(dep))
                for dep in sorted(deps) if dep not in source_paths]

    def write_source(name: list[str]) -> None:
        for i, source in enumerate(source_string):
            with open(name[i], "w" if not source_is_binary else "wb") as outf:
                _ = outf.write(source)

    def calculate_hex_checksum() -> str:
        import hashlib
        checksum = hashlib.md5()

        for source in source_string:
            if source_is_binary:
                assert isinstance(source, bytes)
                checksum.update(source)
            else:
                assert isinstance(source, str)
                checksum.update(source.encode("utf-8"))
        checksum.update(str(toolchain.abi_id()).encode("utf-8"))
        return checksum.hexdigest()

    def load_info(info_path: str) -> Any:
        import pickle

        try:
            with open(info_path, "rb") as info_file:
                return pickle.load(info_file)
        except (OSError, EOFError) as exc:
            raise _InvalidInfoFileError() from exc

    def check_deps(deps: list[_Dependency]) -> bool:
        for dep_name, date, md5sum in deps:
            try:
                possibly_updated = os.stat(dep_name).st_mtime != date
            except OSError as e:
                if debug_recompile:
                    logger.info(
                            "recompiling because dependency %s is "
                            "inaccessible (%s).", dep_name, e)
                return False
            else:
                if possibly_updated and md5sum != get_file_md5sum(dep_name):
                    if debug_recompile:
                        logger.info(
                                "recompiling because dependency %s was "
                                "updated.", dep_name)
                    return False

        return True

    def check_source(source_path: list[str]) -> bool:
        valid = True
        for i, path in enumerate(source_path):
            source = source_string[i]

            try:
                with open(path, "r" if not source_is_binary else "rb") as src_f:
                    valid = valid and src_f.read() == source
            except OSError:
                if debug_recompile:
                    logger.info(
                            "recompiling because cache directory does "
                            "not contain source file '%s'.", path)
                return False

            if not valid:
                from warnings import warn
                warn("hash collision in compiler cache", stacklevel=2)
        return valid

    cleanup_m = CleanupManager()

    try:
        # Variable 'lock_m' is used for no other purpose than
        # to keep lock manager alive.
        lock_m = CacheLockManager(cleanup_m, cache_dir, sleep_delay)  # noqa: F841  # pyright: ignore[reportUnusedVariable]

        hex_checksum = calculate_hex_checksum()
        mod_name = f"codepy.temp.{hex_checksum}.{name}"
        if object:
            suffix = toolchain.o_ext
        else:
            suffix = toolchain.so_ext

        mod_cache_dir_m = ModuleCacheDirManager(cleanup_m,
                os.path.join(cache_dir, hex_checksum))
        info_path = mod_cache_dir_m.sub("info")
        ext_file = mod_cache_dir_m.sub(name + suffix)

        if mod_cache_dir_m.existed:
            try:
                info = load_info(info_path)
            except _InvalidInfoFileError:
                mod_cache_dir_m.reset()

                if debug_recompile:
                    logger.info("recompiling for invalid cache dir (%s).",
                            mod_cache_dir_m.path)
            else:
                if check_deps(info.dependencies) and check_source(
                        [mod_cache_dir_m.sub(x) for x in info.source_name]):
                    return hex_checksum, mod_name, ext_file, False
        else:
            if debug_recompile:
                logger.info("recompiling for non-existent cache dir (%s).",
                        mod_cache_dir_m.path)

        source_paths = [mod_cache_dir_m.sub(source) for source in source_name]

        write_source(source_paths)

        if object:
            toolchain.build_object(ext_file, source_paths, debug=debug)
        else:
            toolchain.build_extension(ext_file, source_paths, debug=debug)

        if info_path:
            import pickle

            with open(info_path, "wb") as info_file:
                pickle.dump(_SourceInfo(
                    dependencies=get_dep_structure(source_paths),
                    source_name=source_name), info_file)

        return hex_checksum, mod_name, ext_file, True  # noqa: TRY300
    except Exception:
        cleanup_m.error_clean_up()
        raise
    finally:
        cleanup_m.clean_up()


def link_extension(
        toolchain: Toolchain,
        objects: list[str],
        mod_name: str,
        cache_dir: str | None = None,
        debug: bool = False,
        ) -> ModuleType:
    if not isinstance(toolchain, GCCLikeToolchain):
        raise TypeError(f"Unsupported toolchain type: {type(toolchain)}")

    if cache_dir is not None:
        destination = os.path.join(cache_dir, mod_name + toolchain.so_ext)
    else:
        # put the linked object in the same directory as the first object
        destination_base, _ = os.path.split(objects[0])
        destination = os.path.join(
                destination_base,
                mod_name + toolchain.so_ext)

    toolchain.link_extension(destination, objects, debug=debug)

    # try loading it
    from codepy.tools import load_dynamic
    return load_dynamic(mod_name, destination)


from pytools import MovedFunctionDeprecationWrapper

from codepy.toolchain import guess_toolchain as _gtc


guess_toolchain = MovedFunctionDeprecationWrapper(_gtc)
