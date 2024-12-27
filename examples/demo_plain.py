from codepy.jit import extension_from_string
from codepy.libraries import add_boost_python
from codepy.toolchain import guess_toolchain


MODULE_CODE = """
#include <boost/python.hpp>

namespace
{
  char const *greet()
  {
    return "hello world";
  }
}

BOOST_PYTHON_MODULE(module)
{
  boost::python::def("greet", &greet);
}
"""

toolchain = guess_toolchain()
add_boost_python(toolchain)

cmod = extension_from_string(toolchain, "module", MODULE_CODE)
print(cmod.greet())
