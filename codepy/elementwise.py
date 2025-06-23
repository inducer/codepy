"""Elementwise functionality."""

__copyright__ = "Copyright (C) 2009 Andreas Kloeckner"

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from types import ModuleType
from typing import Any
from warnings import warn

import numpy as np
from typing_extensions import override

from cgen import POD, Declarator, Value, dtype_to_ctype
from pytools import memoize

from codepy.bpl import BoostPythonModule
from codepy.toolchain import Toolchain


warn("codepy.elementwise is deprecated and will be removed in 2026.",
     DeprecationWarning, stacklevel=2)


class Argument(ABC):
    def __init__(self, dtype: Any, name: str) -> None:
        self.dtype: np.dtype[Any] = np.dtype(dtype)
        self.name: str = name

    @abstractmethod
    def declarator(self) -> Declarator:
        pass

    @abstractmethod
    def arg_name(self) -> str:
        pass

    @property
    @abstractmethod
    def struct_char(self) -> str:
        pass

    @override
    def __repr__(self) -> str:
        return "{}({!r}, {})".format(
                self.__class__.__name__,
                self.name,
                self.dtype)


class VectorArg(Argument):
    @override
    def declarator(self) -> Value:
        return Value(
                "numpy_array<{} >".format(dtype_to_ctype(self.dtype)),
                f"{self.name}_ary")

    @override
    def arg_name(self) -> str:
        return f"{self.name}_ary"

    @property
    @override
    def struct_char(self) -> str:
        return "P"


class ScalarArg(Argument):
    @override
    def declarator(self) -> POD:
        return POD(self.dtype, self.name)

    @override
    def arg_name(self) -> str:
        return self.name

    @property
    @override
    def struct_char(self) -> str:
        return str(self.dtype.char)


def get_elwise_module_descriptor(
        arguments: Sequence[Argument],
        operation: str,
        name: str = "kernel") -> BoostPythonModule:
    from cgen import (
        Block,
        For,
        FunctionBody,
        FunctionDeclaration,
        Include,
        Initializer,
        Line,
        Statement,
        Struct,
    )

    mod = BoostPythonModule()
    mod.add_to_preamble([
        Include("pyublas/numpy.hpp"),
        ])

    mod.add_to_module([
        Statement("namespace ublas = boost::numeric::ublas"),
        Statement("using namespace pyublas"),
        Line(),
        ])

    body = Block([
        Initializer(
            Value(
                "numpy_array<{} >::iterator".format(dtype_to_ctype(varg.dtype)),
                varg.name),
            f"args.{varg.name}_ary.begin()")
        for varg in arguments if isinstance(varg, VectorArg)]
        + [
            Initializer(
                sarg.declarator(), f"args.{sarg.name}")
            for sarg in arguments if isinstance(sarg, ScalarArg)]
        )

    body.extend([
        Line(),
        For("unsigned i = 0",
            "i < codepy_length",
            "++i",
            Block([Statement(operation)])
            )
        ])

    arg_struct = Struct("arg_struct", [arg.declarator() for arg in arguments])
    mod.add_struct(arg_struct, "ArgStruct")
    mod.add_to_module([Line()])

    mod.add_function(
            FunctionBody(
                FunctionDeclaration(
                    Value("void", name),
                    [POD(np.uintp, "codepy_length"),
                        Value("arg_struct", "args")]),
                body))

    return mod


def get_elwise_module_binary(
        arguments: Sequence[Argument],
        operation: str,
        name: str = "kernel",
        toolchain: Toolchain | None = None) -> ModuleType:
    if toolchain is None:
        from codepy.toolchain import guess_toolchain
        toolchain = guess_toolchain()
    else:
        from dataclasses import replace
        toolchain = replace(toolchain)

    from codepy.libraries import add_pyublas

    add_pyublas(toolchain)
    return get_elwise_module_descriptor(arguments, operation, name).compile(toolchain)


def get_elwise_kernel(
        arguments: Sequence[Argument],
        operation: str,
        name: str = "kernel",
        toolchain: Toolchain | None = None) -> Callable[..., Any]:
    mod = get_elwise_module_binary(arguments, operation, name, toolchain)
    return getattr(mod, name)  # type: ignore[no-any-return]


class ElementwiseKernel:
    def __init__(self,
                 arguments: Sequence[Argument],
                 operation: str,
                 name: str = "kernel",
                 toolchain: Toolchain | None = None) -> None:
        self.arguments: tuple[Argument, ...] = tuple(arguments)
        self.module: ModuleType = (
            get_elwise_module_binary(arguments, operation, name, toolchain))
        self.func: Callable[..., Any] = getattr(self.module, name)

        self.vec_arg_indices: list[int] = [
            i for i, arg in enumerate(arguments)
            if isinstance(arg, VectorArg)]

        if not self.vec_arg_indices:
            raise ValueError(
                f"{type(self)} can only be used with functions that have at "
                f"least one vector argument: {arguments}")

    def __call__(self, *args: Any) -> None:
        from pytools import single_valued

        arguments = list(args)
        size = single_valued(
                arguments[i].size for i in self.vec_arg_indices
                if not (isinstance(arguments[i], int | float) and arguments[i] == 0))

        for i in self.vec_arg_indices:
            if isinstance(arguments[i], int | float) and arguments[i] == 0:
                arguments[i] = np.zeros(size, dtype=self.arguments[i].dtype)

        # no need to do type checking--pyublas does that for us
        arg_struct = self.module.ArgStruct()
        for arg_descr, arg in zip(self.arguments, arguments, strict=True):
            setattr(arg_struct, arg_descr.arg_name(), arg)

        assert not arg_struct.__dict__

        self.func(size, arg_struct)


@memoize
def make_linear_comb_kernel_with_result_dtype(
        result_dtype: Any,
        scalar_dtypes: tuple[Any, ...],
        vector_dtypes: tuple[Any, ...]) -> ElementwiseKernel:
    if len(scalar_dtypes) != len(vector_dtypes):
        raise ValueError(
            "'scalar_dtypes' and 'vector_dtypes' do not have the same length"
        )

    from itertools import chain

    comp_count = len(vector_dtypes)
    args = chain.from_iterable(
        (ScalarArg(scalar_dtypes[i], f"a{i}_fac"),
         VectorArg(vector_dtypes[i], f"a{i}"))
        for i in range(comp_count)
    )
    return ElementwiseKernel(
        [VectorArg(result_dtype, "result"), *args],
        "result[i] = " + " + ".join(
            f"a{i}_fac*a{i}[i]" for i in range(comp_count)
        ))


@memoize
def make_linear_comb_kernel(
        scalar_dtypes: tuple[Any, ...],
        vector_dtypes: tuple[Any, ...]) -> tuple[ElementwiseKernel, np.dtype[Any]]:
    result_dtype = np.result_type(*scalar_dtypes, *vector_dtypes)

    return make_linear_comb_kernel_with_result_dtype(
            result_dtype, scalar_dtypes, vector_dtypes), result_dtype
