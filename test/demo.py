import cgen as c
from codepy.bpl import BoostPythonModule
mod = BoostPythonModule()

mod.add_function(
        c.FunctionBody(
            c.FunctionDeclaration(c.Const(c.Pointer(c.Value("char", "greet"))), []),
            c.Block([c.Statement('return "hello world"')])
            ))

from codepy.toolchain import guess_toolchain
cmod = mod.compile(guess_toolchain())

print(cmod.greet())
