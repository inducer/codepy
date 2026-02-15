"""Configure JIT platforms to link with external libraries."""

__copyright__ = "Copyright (C) 2008 Andreas Kloeckner"

from collections.abc import Sequence
from typing import Any, TypeGuard

from pytools import memoize

from codepy.toolchain import Toolchain


def search_on_path(filenames: Sequence[str]) -> str | None:
    """Find file on system path."""
    # http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/52224

    from os import environ, pathsep
    from os.path import abspath, exists, join

    search_path = environ["PATH"]

    paths = search_path.split(pathsep)
    for path in paths:
        for filename in filenames:
            if exists(join(path, filename)):
                return abspath(join(path, filename))

    return None


# {{{ aksetup handling

Config = dict[str, Any]


def is_str_list(val: list[object]) -> TypeGuard[list[str]]:
    return all(isinstance(x, str) for x in val)


def getstring(options: Config, key: str, default: str | None = None) -> str | None:
    value = options.get(key)
    if value is None:
        return default

    assert isinstance(value, str)
    return value


def getlist(options: Config, key: str, default: list[str]) -> list[str]:
    value: list[object] | None = options.get(key)
    if value is None:
        return default

    assert isinstance(value, list)
    if is_str_list(value):
        return value

    raise ValueError(f"List has non-string elements: {value}")


def expand_str(s: str, options: Config) -> str:
    import re
    from os import environ

    def my_repl(match: re.Match[str]) -> str:
        sym = match.group(1)
        try:
            repl = options[sym]
        except KeyError:
            repl = environ[sym]

        assert isinstance(repl, str)
        return expand_str(repl, options)

    return re.subn(r"\$\{([a-zA-Z0-9_]+)\}", my_repl, s)[0]


def expand_value(v: Any, options: Config) -> Any:
    if isinstance(v, str):
        return expand_str(v, options)
    elif isinstance(v, list):
        return [expand_value(i, options) for i in v]  # pyright: ignore[reportUnknownVariableType]
    else:
        return v


def expand_options(options: Config) -> Config:
    for k in options:
        options[k] = expand_value(options[k], options)

    return options


@memoize
def get_aksetup_config() -> Config:
    def update_config(fname: str) -> None:
        import os
        if os.access(fname, os.R_OK):
            filevars: dict[str, str] = {}

            with open(fname) as cf_file:
                file_contents = cf_file.read()
            exec(compile(file_contents, fname, "exec"), filevars)

            for key, value in filevars.items():
                if key != "__builtins__":
                    config[key] = value

    import sys
    from os.path import expanduser

    config: Config = {}
    update_config(expanduser("~/.aksetup-defaults.py"))

    if not sys.platform.lower().startswith("win"):
        update_config(expanduser("/etc/aksetup-defaults.py"))

    return expand_options(config)

# }}}


# {{{ libraries

def get_boost_libname(basename: str, aksetup: Config) -> list[str]:
    varname = f"BOOST_{basename.upper()}_LIBNAME"
    default = f"boost_{basename}"
    if basename == "python":
        import sys
        version = sys.version_info[:2]
        default = "boost_python{}{}".format(*version)
    libs = getlist(aksetup, varname, [default])

    return libs


def add_boost_python(toolchain: Toolchain) -> None:
    import sys

    aksetup = get_aksetup_config()
    version = sys.version_info[:2]

    toolchain.add_library(
            "boost-python",
            getlist(aksetup, "BOOST_INC_DIR", []),
            getlist(aksetup, "BOOST_LIB_DIR", []),
            [
                *get_boost_libname("python", aksetup),
                "python{}.{}{}".format(*version, sys.abiflags),
            ])


def add_pybind11(toolchain: Toolchain) -> None:
    import pybind11

    toolchain.add_library(
            "pybind11",
            [pybind11.get_include(False)],
            [],
            [])


def add_boost_numeric_bindings(toolchain: Toolchain) -> None:
    aksetup = get_aksetup_config()
    toolchain.add_library(
            "boost-numeric-bindings",
            getlist(aksetup, "BOOST_BINDINGS_INC_DIR", []), [], [])


def add_numpy(toolchain: Toolchain) -> None:
    def get_numpy_incpath() -> str:
        from importlib.util import find_spec
        spec = find_spec("numpy")
        if spec is None:
            raise RuntimeError("Could not find 'numpy' module")

        libdir = spec.submodule_search_locations
        assert libdir is not None

        from os.path import join
        return join(libdir[0], "core", "include")

    toolchain.add_library("numpy", [get_numpy_incpath()], [], [])


def add_py_module(toolchain: Toolchain, name: str) -> None:
    def get_module_include_path(name: str) -> str:
        from importlib.util import find_spec
        spec = find_spec(name)
        if spec is None:
            raise RuntimeError(f"Could not find module '{name}'")
        libdir = spec.submodule_search_locations
        assert libdir is not None
        from os.path import join
        return join(libdir[0], "include")

    toolchain.add_library(name, [get_module_include_path(name)], [], [])


def add_codepy(toolchain: Toolchain) -> None:
    add_py_module(toolchain, "codepy")


def add_pyublas(toolchain: Toolchain) -> None:
    add_boost_python(toolchain)
    add_numpy(toolchain)
    add_py_module(toolchain, "pyublas")


def add_hedge(toolchain: Toolchain) -> None:
    add_pyublas(toolchain)
    add_boost_numeric_bindings(toolchain)
    add_py_module(toolchain, "hedge")


def add_cuda(toolchain: Toolchain) -> None:
    conf = get_aksetup_config()
    cuda_lib_path: list[str] = getlist(conf, "CUDADRV_LIB_DIR", [])
    cuda_library: list[str] = getlist(conf, "CUDADRV_LIBNAME", ["cuda"])
    cuda_include_path: list[str] = getlist(conf, "CUDA_INC_DIR", [])

    if not cuda_include_path or not cuda_lib_path:
        from os.path import dirname, join, normpath

        cuda_root = getstring(conf, "CUDA_ROOT")

        if cuda_root is None:
            nvcc_path = search_on_path(["nvcc", "nvcc.exe"])
            if nvcc_path is None:
                raise RuntimeError("Unable to guess CUDA configuration, "
                        "CUDA_ROOT not set in ~/.aksetup-defaults.py "
                        "and nvcc not on path.")

            cuda_root = normpath(join(dirname(nvcc_path), ".."))

        if not cuda_include_path:
            cuda_include_path = [join(cuda_root, "include")]
        if not cuda_lib_path:
            cuda_lib_path = [join(cuda_root, "lib"), join(cuda_root, "lib64")]

    cuda_rt_path: list[str] = getlist(conf, "CUDART_LIB_DIR", cuda_lib_path)
    cuda_rt_library: list[str] = getlist(conf, "CUDART_LIBNAME", ["cudart"])

    toolchain.add_library("cuda", cuda_include_path,
                          cuda_lib_path + cuda_rt_path,
                          cuda_library + cuda_rt_library)

# }}}

# vim:foldmethod=marker
