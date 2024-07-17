from importlib import metadata
from urllib.request import urlopen


_conf_url = \
        "https://raw.githubusercontent.com/inducer/sphinxconfig/main/sphinxconfig.py"
with urlopen(_conf_url) as _inf:
    exec(compile(_inf.read(), _conf_url, "exec"), globals())

copyright = "2009-2024, Andreas Kloeckner"
release = metadata.version("codepy")
version = ".".join(release.split(".")[:2])

intersphinx_mapping = {
        "python": ("https://docs.python.org/dev", None),
        "numpy": ("https://numpy.org/doc/stable", None),
        "cgen": ("https://documen.tician.de/cgen", None),
        }
