from urllib.request import urlopen

_conf_url = \
        "https://raw.githubusercontent.com/inducer/sphinxconfig/main/sphinxconfig.py"
with urlopen(_conf_url) as _inf:
    exec(compile(_inf.read(), _conf_url, "exec"), globals())

copyright = "2009-21, Andreas Kloeckner"

# The short X.Y version.
import re
ver_re = re.compile(r'version\s*=\s*"([0-9a-z.]+)"')
version = [ver_re.search(line).group(1)
        for line in open("../setup.py").readlines()
        if ver_re.search(line)][0]
# The full version, including alpha/beta/rc tags.
release = version

intersphinx_mapping = {
        "http://docs.python.org/dev": None,
        "http://docs.scipy.org/doc/numpy/": None,
        "http://documen.tician.de/cgen": None,
        }
