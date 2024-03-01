"""Random bits of usefulness."""


__copyright__ = "Copyright (C) 2009 Andreas Kloeckner"


def join_continued_lines(lines):
    result = []
    it = iter(lines)
    append_line = False
    try:
        while True:
            try:
                line = it.next().rstrip("\n")
            except AttributeError:
                # py3
                line = next(it).rstrip("\n")
            append_next_line = line.endswith("\\")
            if append_next_line:
                line = line[:-1]

            if append_line:
                result[-1] += line
            else:
                result.append(line)
            append_line = append_next_line
    except StopIteration:
        if append_line:
            from warnings import warn
            warn("line continuation at end of file")

    return result


def load_dynamic(name: str, path: str):
    """Implementation of ``imp.load_dynamic`` based on :mod:`importlib`."""
    # https://github.com/python/cpython/pull/105951

    from importlib.machinery import ExtensionFileLoader

    loader = ExtensionFileLoader(name, path)

    from importlib.util import module_from_spec, spec_from_loader

    spec = spec_from_loader(name, loader)
    module = module_from_spec(spec)

    # The module is always executed and not cached in sys.modules.
    # Uncomment the following line to cache the module.
    # sys.modules[module.__name__] = module

    loader.exec_module(module)
    return module
