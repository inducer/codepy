from codepy.toolchain import guess_toolchain
from codepy.jit import compile_from_string
from ctypes import CDLL


def test():
    toolchain = guess_toolchain()

    module_code = """
    extern "C" {
        int const greet()
        {
            return 1;
        }
    }
    """
    # compile to object file
    _, _, obj_path, _ = compile_from_string(toolchain, 'module', module_code,
                                            object=True)
    # and then to shared lib
    with open(obj_path, 'rb') as file:
        obj = file.read()

    _, _, ext_file, _ = compile_from_string(
        toolchain, 'module', obj, source_name=['module.o'],
        object=False, source_is_binary=True)

    # test module
    dll = CDLL(ext_file)
    _fn = getattr(dll, 'greet')
    _fn.restype = int
    assert _fn() == 1
