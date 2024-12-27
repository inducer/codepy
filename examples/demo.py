import cgen as c

from codepy.bpl import BoostPythonModule
from codepy.toolchain import guess_toolchain


mod = BoostPythonModule()
mod.add_function(
        c.FunctionBody(
            c.FunctionDeclaration(c.Const(c.Pointer(c.Value("char", "greet"))), []),
            c.Block([c.Statement('return "hello world"')])
            ))

toolchain = guess_toolchain()
cmod = mod.compile(toolchain)

print(cmod.greet())
