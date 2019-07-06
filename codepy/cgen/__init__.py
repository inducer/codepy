from cgen import *  # noqa
import cgen.cuda as cuda  # noqa: F401
import cgen.opencl as opencl  # noqa: F401

from warnings import warn as _warn
_warn("codepy.cgen is deprecated. Use the separate 'cgen' module instead, see "
        "the Python package index.", DeprecationWarning,
        stacklevel=2)
