Wrapping and Linking
====================

Note that codepy accesses a file called :file:`.aksetup-defaults.py`
in your home directory (mind the dot!) and :file:`/etc/aksetup-defaults.py`
to determine a few configuration values, notably:

* `BOOST_INC_DIR`
* `BOOST_LIB_DIR`
* `BOOST_PYTHON_LIBNAME`
* `BOOST_COMPILER` (used in the default libnames)
* `CUDA_ROOT`

For lack of better documentation at this moment, please see `this wiki page
<http://wiki.tiker.net/Hedge/HowTo/InstallingFromGit>`_.

:mod:`codepy.jit` -- Compilation and Linking of C Source Code
-------------------------------------------------------------

.. module:: codepy.jit

.. autoclass:: Toolchain
    :members: copy, get_version, abi_id, add_library, build_extension
    :undoc-members:

.. autoclass:: GCCToolchain
    :show-inheritance:

.. autofunction:: guess_toolchain
.. autofunction:: extension_file_from_string
.. autofunction:: extension_from_string

Errors
^^^^^^

.. autoexception:: CompileError

.. autoexception:: ToolchainGuessError


:mod:`codepy.bpl` -- Support for Boost.Python
---------------------------------------------

.. automodule:: codepy.bpl

.. autoclass:: BoostPythonModule
    :members:
    :undoc-members:
