from cgen import *
from codepy.bpl import BoostPythonModule
mod = BoostPythonModule()

mod.add_function(
        FunctionBody(
            FunctionDeclaration(Const(Pointer(Value("char", "greet"))), []),
            Block([Statement('return "hello world"')])
            ))

from codepy.toolchain import guess_toolchain
cmod = mod.compile(guess_toolchain())

print cmod.greet()

