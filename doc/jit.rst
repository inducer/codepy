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

For lack of better installation documentation at this moment, please see `this
wiki page <http://wiki.tiker.net/Hedge/HowTo/InstallingFromGit>`_.

.. automodule:: codepy
