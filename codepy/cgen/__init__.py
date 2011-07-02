from cgen import *
import cgen.cuda as cuda
import cgen.opencl as opencl

from warnings import warn as _warn
_warn("codepy.cgen is deprecated. Use the separate 'cgen' module instead, see "
        "the Python package index.", DeprecationWarning,
        stacklevel=2)

