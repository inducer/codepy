"""Convenience interface for using CodePy with Boost.Python."""

from collections.abc import Callable, Iterable
from dataclasses import replace
from types import ModuleType
from typing import Any

from cgen import FunctionBody, Generable, Module, Struct

from codepy.toolchain import Toolchain


class BoostPythonModule:
    def __init__(self,
                 name: str = "module",
                 max_arity: int | str | None = None,
                 use_private_namespace: bool = True) -> None:
        self.name = name
        self.max_arity = max_arity
        self.use_private_namespace = use_private_namespace

        self.preamble: list[Generable] = []
        self.mod_body: list[Generable] = []
        self.init_body: list[Generable] = []
        self.has_codepy_include = False
        self.has_raw_function_include = False

    def add_to_init(self, body: Iterable[Generable]) -> None:
        """Add the blocks or statements contained in the iterable *body* to the
        module initialization function.
        """
        self.init_body.extend(body)

    def add_to_preamble(self, pa: Iterable[Generable]) -> None:
        self.preamble.extend(pa)

    def add_to_module(self, body: Iterable[Generable]) -> None:
        """Add the :class:`cgen.Generable` instances in the iterable
        *body* to the body of the module *self*.
        """

        self.mod_body.extend(body)

    def add_codepy_include(self) -> None:
        if self.has_codepy_include:
            return

        from cgen import Include

        self.add_to_preamble([
            Include("codepy/bpl.hpp")
            ])
        self.has_codepy_include = True

    def add_raw_function_include(self) -> None:
        if self.has_raw_function_include:
            return

        from cgen import Include

        self.add_to_preamble([
            Include("boost/python/raw_function.hpp")
            ])
        self.has_raw_function_include = True

    def expose_vector_type(self, name: str, py_name: str | None = None) -> None:
        self.add_codepy_include()

        if py_name is None:
            py_name = name

        from cgen import Block, Line, Statement, Typedef, Value

        self.init_body.append(
            Block([
                Typedef(Value(name, "cl")),
                Line(),
                Statement(
                    f'boost::python::class_<cl>("{py_name}")'
                    ".def(codepy::no_compare_indexing_suite<cl>())"),
                ]))

    def add_function(self, func: FunctionBody) -> None:
        """Add a function to be exposed. *func* is expected to be a
        :class:`cgen.FunctionBody`.
        """
        from cgen import Statement

        self.mod_body.append(func)
        self.init_body.append(
                Statement(
                    'boost::python::def("{}", &{})'.format(
                        func.fdecl.name, func.fdecl.name)))

    def add_raw_function(self, func: FunctionBody) -> None:
        """Add a function to be exposed using boost::python::raw_function.
        *func* is expected to be a :class:`cgen.FunctionBody`.
        """
        from cgen import Statement

        self.mod_body.append(func)
        self.add_raw_function_include()

        raw_function = f"boost::python::raw_function(&{func.fdecl.name})"
        self.init_body.append(
            Statement(
                'boost::python::def("{}", {})'.format(
                    func.fdecl.name, raw_function)))

    def add_struct(
            self,
            struct: Struct,
            py_name: str | None = None,
            py_member_name_transform: Callable[[str], str] = lambda x: x,
            by_value_members: set[str] | None = None) -> None:
        if by_value_members is None:
            by_value_members = set()

        from cgen import Block, Line, Statement, Typedef, Value

        if py_name is None:
            py_name = struct.tpname

        self.mod_body.append(struct)

        member_defs = []
        for f in struct.fields:
            if not hasattr(f, "name"):
                raise TypeError(
                    f"Invalid type {type(f)} of struct field. Only named fields "
                    "are supported for code generation")

            py_f_name = py_member_name_transform(f.name)
            tp_lines, _ = f.get_decl_pair()
            if f.name in by_value_members or tp_lines[0].startswith("numpy_"):
                member_defs.append(
                        ".def(pyublas::by_value_rw_member"
                        f'("{py_f_name}", &cl::{f.name}))')
            else:
                member_defs.append(
                        f'.def_readwrite("{py_f_name}", &cl::{f.name})'
                        )

        self.init_body.append(
            Block([
                Typedef(Value(struct.tpname, "cl")),
                Line(),
                Statement(
                    'boost::python::class_<cl>("{}"){}'.format(
                        py_name, "".join(member_defs))),
                ]))

    def generate(self) -> Module:
        """Generate (i.e. yield) the source code of the
        module line-by-line.
        """

        from cgen import Block, Define, Include, Line, PrivateNamespace

        body: list[Generable] = []

        if self.max_arity is not None:
            body.append(Define("BOOST_PYTHON_MAX_ARITY", str(self.max_arity)))

        if self.use_private_namespace:
            mod_body: list[Generable] = [PrivateNamespace(self.mod_body)]
        else:
            mod_body = self.mod_body

        body += [
            Include("boost/python.hpp"),
            *self.preamble,
            Line(),
            *mod_body,
            Line(),
            Line(f"BOOST_PYTHON_MODULE({self.name})"),
            Block(self.init_body),
        ]

        return Module(body)

    def compile(self, toolchain: Toolchain, **kwargs: Any) -> ModuleType:
        """Return the extension module generated from the code described
        by *self*. If necessary, build the code using *toolchain* with
        :func:`codepy.jit.extension_from_string`. Any keyword arguments
        accept by that latter function may be passed in *kwargs*.
        """

        from codepy.libraries import add_boost_python

        toolchain = replace(toolchain)
        add_boost_python(toolchain)

        from codepy.jit import extension_from_string

        return extension_from_string(
                toolchain,
                self.name,
                "{}\n".format(self.generate()), **kwargs)
