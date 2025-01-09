from types import ModuleType

import pytest


def make_greet_mod(greeting: str) -> ModuleType:
    from cgen import (
        Block,
        Const,
        FunctionBody,
        FunctionDeclaration,
        Pointer,
        Statement,
        Value,
    )

    from codepy.bpl import BoostPythonModule

    mod = BoostPythonModule()

    mod.add_function(
            FunctionBody(
                FunctionDeclaration(Const(Pointer(Value("char", "greet"))), []),
                Block([Statement(f'return "{greeting}"')])
                ))

    from codepy.toolchain import guess_toolchain
    return mod.compile(guess_toolchain(), wait_on_error=True)


@pytest.mark.xfail(reason="You probably don't have "
        "Boost.Python installed where I am looking for it, "
        "and that's OK.")
def test_identical_symbols() -> None:
    us = make_greet_mod("Hi there")
    aussie = make_greet_mod("G'day")

    assert us.greet() != aussie.greet()
    print(us.greet(), aussie.greet())


if __name__ == "__main__":
    test_identical_symbols()
