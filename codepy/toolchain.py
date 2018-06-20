"""Toolchains for Just-in-time Python extension compilation."""

from __future__ import division, print_function

__copyright__ = """
"Copyright (C) 2008,9 Andreas Kloeckner, Bryan Catanzaro
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


from codepy import CompileError
from pytools import Record


class Toolchain(Record):
    """Abstract base class for tools used to link dynamic Python modules."""

    def __init__(self, *args, **kwargs):
        if 'features' not in kwargs:
            kwargs['features'] = set()
        Record.__init__(self, *args, **kwargs)

    def get_version(self):
        """Return a string describing the exact version of the tools (compilers etc.)
        involved in this toolchain.

        Implemented by subclasses.
        """

        raise NotImplementedError

    def abi_id(self):
        """Return a picklable Python object that describes the ABI (Python version,
        compiler versions, etc.) against which a Python module is compiled.
        """

        import sys
        return [self.get_version(), sys.version]

    def add_library(self, feature, include_dirs, library_dirs, libraries):
        """Add *include_dirs*, *library_dirs* and *libraries* describing the
        library named *feature* to the toolchain.

        Future toolchain invocations will include compiler flags referencing
        the respective resources.

        Duplicate directories are ignored, as will be attempts to add the same
        *feature* twice.
        """
        if feature in self.features:
            return

        self.features.add(feature)

        for idir in include_dirs:
            if idir not in self.include_dirs:
                self.include_dirs.append(idir)

        for ldir in library_dirs:
            if ldir not in self.library_dirs:
                self.library_dirs.append(ldir)

        self.libraries = libraries + self.libraries

    def get_dependencies(self,  source_files):
        """Return a list of header files referred to by *source_files.

        Implemented by subclasses.
        """

        raise NotImplementedError

    def build_extension(self, ext_file, source_files, debug=False):
        """Create the extension file *ext_file* from *source_files*
        by invoking the toolchain. Raise :exc:`CompileError` in
        case of error.

        If *debug* is True, print the commands executed.

        Implemented by subclasses.
        """

        raise NotImplementedError

    def build_object(self, obj_file, source_files, debug=False):
        """Build a compiled object *obj_file* from *source_files*
        by invoking the toolchain. Raise :exc:`CompileError` in
        case of error.

        If *debug* is True, print the commands executed.

        Implemented by subclasses.
        """

        raise NotImplementedError

    def link_extension(self, ext_file, object_files, debug=False):
        """Create the extension file *ext_file* from *object_files*
        by invoking the toolchain. Raise :exc:`CompileError` in
        case of error.

        If *debug* is True, print the commands executed.

        Implemented by subclasses.
        """

        raise NotImplementedError

    def with_optimization_level(self, level, **extra):
        """Return a new Toolchain object with the optimization level
        set to `level` , on the scale defined by the gcc -O option.
        Levels greater than four may be defined to perform certain, expensive
        optimizations. Further, extra keyword arguments may be defined.
        If a subclass doesn't understand an "extra" argument, it should
        simply ignore it.

        Level may also be "debug" to specifiy a debug build.

        Implemented by subclasses.
        """

        raise NotImplementedError


# {{{ gcc-like tool chain

class GCCLikeToolchain(Toolchain):
    def get_version(self):
        result, stdout, stderr = call_capture_output([self.cc, "--version"])
        if result != 0:
            raise RuntimeError("version query failed: "+stderr)
        return stdout

    def enable_debugging(self):
        self.cflags = [f for f in self.cflags if not f.startswith("-O")] + ["-g"]

    def get_dependencies(self, source_files):
        from codepy.tools import join_continued_lines
        result, stdout, stderr = call_capture_output(
                [self.cc]
                + ["-M"]
                + ["-D%s" % define for define in self.defines]
                + ["-U%s" % undefine for undefine in self.undefines]
                + ["-I%s" % idir for idir in self.include_dirs]
                + self.cflags
                + source_files
                )

        if result != 0:
            raise CompileError("getting dependencies failed: "+stderr)

        lines = join_continued_lines(stdout.split("\n"))
        from pytools import flatten
        return set(flatten(
            line.split()[2:] for line in lines))

    def build_object(self, ext_file, source_files, debug=False):
        cc_cmdline = (
                self._cmdline(source_files, True)
                + ["-o", ext_file]
                )

        from pytools.prefork import call
        if debug:
            print(" ".join(cc_cmdline))

        result = call(cc_cmdline)

        if result != 0:
            import sys
            print("FAILED compiler invocation:" +
                  " ".join(cc_cmdline), file=sys.stderr)
            raise CompileError("module compilation failed")

    def build_extension(self, ext_file, source_files, debug=False):
        cc_cmdline = (
                self._cmdline(source_files, False)
                + ["-o", ext_file]
                )

        from pytools.prefork import call
        if debug:
            print(" ".join(cc_cmdline))

        result = call(cc_cmdline)

        if result != 0:
            import sys
            print("FAILED compiler invocation:" + " ".join(cc_cmdline),
                  file=sys.stderr)
            raise CompileError("module compilation failed")

    def link_extension(self, ext_file, object_files, debug=False):
        cc_cmdline = (
                self._cmdline(object_files, False)
                + ["-o", ext_file]
                )

        from pytools.prefork import call
        if debug:
            print(" ".join(cc_cmdline))

        result = call(cc_cmdline)

        if result != 0:
            import sys
            print("FAILED compiler invocation:" + " ".join(cc_cmdline),
                  file=sys.stderr)
            raise CompileError("module compilation failed")

# }}}


# {{{ gcc toolchain

class GCCToolchain(GCCLikeToolchain):
    def get_version_tuple(self):
        ver = self.get_version()
        lines = ver.split("\n")
        words = lines[0].split()
        numbers = words[2].split(".")

        result = []
        for n in numbers:
            try:
                result.append(int(n))
            except ValueError:
                # not an integer? too bad.
                break

        return tuple(result)

    def _cmdline(self, files, object=False):
        if object:
            ld_options = ['-c']
            link = []
        else:
            ld_options = self.ldflags
            link = ["-L%s" % ldir for ldir in self.library_dirs]
            link.extend(["-l%s" % lib for lib in self.libraries])
        return (
            [self.cc]
            + self.cflags
            + ld_options
            + ["-D%s" % define for define in self.defines]
            + ["-U%s" % undefine for undefine in self.undefines]
            + ["-I%s" % idir for idir in self.include_dirs]
            + files
            + link
            )

    def abi_id(self):
        return Toolchain.abi_id(self) + [self._cmdline([])]

    def with_optimization_level(self, level, debug=False, **extra):
        def remove_prefix(l, prefix):
            return [f for f in l if not f.startswith(prefix)]

        cflags = self.cflags
        for pfx in ["-O", "-g", "-march", "-mtune", "-DNDEBUG"]:
            cflags = remove_prefix(cflags, pfx)

        if level == "debug":
            oflags = ["-g"]
        else:
            oflags = ["-O%d" % level, "-DNDEBUG"]

            if level >= 2 and self.get_version_tuple() >= (4, 3):
                oflags.extend(["-march=native", "-mtune=native", ])

        return self.copy(cflags=cflags + oflags)

# }}}


# {{{ nvcc

class NVCCToolchain(GCCLikeToolchain):
    def get_version_tuple(self):
        ver = self.get_version()
        lines = ver.split("\n")
        words = lines[3].split()
        numbers = words[4].split('.') + words[5].split('.')

        result = []
        for n in numbers:
            try:
                result.append(int(n))
            except ValueError:
                # not an integer? too bad.
                break

        return tuple(result)

    def _cmdline(self, files, object=False):
        if object:
            ldflags = ['-c']
            load = []
        else:
            ldflags = self.ldflags
            load = ["-L%s" % ldir for ldir in self.library_dirs]
            load.extend(["-l%s" % lib for lib in self.libraries])
        return (
                [self.cc]
                + self.cflags
                + ldflags
                + ["-D%s" % define for define in self.defines]
                + ["-U%s" % undefine for undefine in self.undefines]
                + ["-I%s" % idir for idir in self.include_dirs]
                + files
                + load
                )

    def abi_id(self):
        return Toolchain.abi_id(self) + [self._cmdline([])]

    def build_object(self, ext_file, source_files, debug=False):
        cc_cmdline = (
                self._cmdline(source_files, True)
                + ["-o", ext_file]
                )

        if debug:
            print(" ".join(cc_cmdline))

        result, stdout, stderr = call_capture_output(cc_cmdline)
        print(stderr)
        print(stdout)

        if "error" in stderr:
            # work around a bug in nvcc, which doesn't provide a non-zero
            # return code even if it failed.
            result = 1

        if result != 0:
            import sys
            print("FAILED compiler invocation:" + " ".join(cc_cmdline),
                  file=sys.stderr)
            raise CompileError("module compilation failed")

# }}}


# {{{ configuration

class ToolchainGuessError(Exception):
    pass


def _guess_toolchain_kwargs_from_python_config():
    def strip_prefix(pfx, value):
        if value.startswith(pfx):
            return value[len(pfx):]
        else:
            return value

    from distutils.sysconfig import parse_makefile, get_makefile_filename
    make_vars = parse_makefile(get_makefile_filename())

    cc_cmdline = (make_vars["CXX"].split()
            + make_vars["CFLAGS"].split()
            + make_vars["CFLAGSFORSHARED"].split())
    object_names = [
            oname for oname in make_vars['OBJECT_OBJS'].split()
            if "(" not in oname and ")" not in oname]

    object_suffix = '.' + object_names[0].split('.')[1]

    cflags = []
    defines = []
    undefines = []

    for cflag in cc_cmdline[1:]:
        if cflag.startswith("-D"):
            defines.append(cflag[2:])
        elif cflag.startswith("-U"):
            undefines.append(cflag[2:])
        else:
            cflags.append(cflag)

    # on Mac OS X, "libraries" can also be "frameworks"
    libraries = []
    for lib in make_vars["LIBS"].split():
        if lib.startswith("-l"):
            libraries.append(strip_prefix("-l", lib))
        else:
            cflags.append(lib)

    return dict(
            cc=cc_cmdline[0],
            ld=make_vars["LDSHARED"].split()[0],
            cflags=cflags,
            ldflags=(
                make_vars["LDSHARED"].split()[1:]
                + make_vars["LINKFORSHARED"].split()
                ),
            libraries=libraries,
            include_dirs=[
                make_vars["INCLUDEPY"]
                ],
            library_dirs=[make_vars["LIBDIR"]],
            so_ext=make_vars["SO"] if 'SO' in make_vars else '.so',
            o_ext=object_suffix,
            defines=defines,
            undefines=undefines,
            )


def call_capture_output(*args):
    from pytools.prefork import call_capture_output
    import sys

    encoding = sys.getdefaultencoding()
    result, stdout, stderr = call_capture_output(*args)
    return result, stdout.decode(encoding), stderr.decode(encoding)


def guess_toolchain():
    """Guess and return a :class:`Toolchain` instance.

    Raise :exc:`ToolchainGuessError` if no toolchain could be found.
    """
    kwargs = _guess_toolchain_kwargs_from_python_config()
    result, version, stderr = call_capture_output([kwargs["cc"], "--version"])
    if result != 0:
        raise ToolchainGuessError("compiler version query failed: "+stderr)

    if "Free Software Foundation" in version:
        if "-Wstrict-prototypes" in kwargs["cflags"]:
            kwargs["cflags"].remove("-Wstrict-prototypes")
        if "darwin" in version:
            # Are we running in 32-bit mode?
            # The python interpreter may have been compiled as a Fat binary
            # So we need to check explicitly how we're running
            # And update the cflags accordingly
            import sys
            if sys.maxsize == 0x7fffffff:
                kwargs["cflags"].extend(['-arch', 'i386'])

        return GCCToolchain(**kwargs)
    elif "Apple LLVM" in version and "clang" in version:
        if "-Wstrict-prototypes" in kwargs["cflags"]:
            kwargs["cflags"].remove("-Wstrict-prototypes")
        if "darwin" in version:
            # Are we running in 32-bit mode?
            # The python interpreter may have been compiled as a Fat binary
            # So we need to check explicitly how we're running
            # And update the cflags accordingly
            import sys
            if sys.maxsize == 0x7fffffff:
                kwargs["cflags"].extend(['-arch', 'i386'])

        return GCCToolchain(**kwargs)
    else:
        raise ToolchainGuessError("unknown compiler")


def guess_nvcc_toolchain():
    gcc_kwargs = _guess_toolchain_kwargs_from_python_config()

    kwargs = dict(
            cc="nvcc",
            ldflags=[],
            libraries=gcc_kwargs["libraries"],
            cflags=["-Xcompiler", ",".join(gcc_kwargs["cflags"])],
            include_dirs=gcc_kwargs["include_dirs"],
            library_dirs=gcc_kwargs["library_dirs"],
            so_ext=gcc_kwargs["so_ext"],
            o_ext=gcc_kwargs["o_ext"],
            defines=gcc_kwargs["defines"],
            undefines=gcc_kwargs["undefines"],
            )
    kwargs.setdefault("undefines", []).append("__BLOCKS__")
    kwargs["cc"] = "nvcc"

    return NVCCToolchain(**kwargs)

# }}}

# vim: foldmethod=marker
