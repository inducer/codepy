import cgen as c
from codepy.bpl import BoostPythonModule
from codepy.cuda import CudaModule
from cgen.cuda import CudaGlobal

# This file tests the ability to use compile and link CUDA code into the
# Python interpreter.  Running this test requires PyCUDA
# as well as CUDA 3.0beta (or greater)


# The host module should include a function which is callable from Python
host_mod = BoostPythonModule()

# Are we on a 32 or 64 bit platform?
import sys
import math
bitness = math.log(sys.maxsize) + 1
ptr_sz_uint_conv = 'K' if bitness > 32 else 'I'

# This host function extracts a pointer and shape information from a PyCUDA
# GPUArray, and then sends them to a CUDA function.  The CUDA function
# returns a pointer to an array of the same type and shape as the input array.
# The host function then constructs a GPUArray with the result.

statements = [
    # Extract information from incoming GPUArray
    'PyObject* shape = PyObject_GetAttrString(gpuArray, "shape")',
    'PyObject* type = PyObject_GetAttrString(gpuArray, "dtype")',
    'PyObject* pointer = PyObject_GetAttrString(gpuArray, "gpudata")',
    'CUdeviceptr cudaPointer = boost::python::extract<CUdeviceptr>(pointer)',
    'PyObject* length = PySequence_GetItem(shape, 0)',
    'int intLength = boost::python::extract<int>(length)',
    # Call CUDA function
    'CUdeviceptr diffResult = diffInstance(cudaPointer, intLength)',
    # Build resulting GPUArray
    'PyObject* args = Py_BuildValue("()")',
    'PyObject* newShape = Py_BuildValue("(i)", intLength)',

    'PyObject* kwargs = Py_BuildValue('
    '"{sOsOs%s}", "shape", newShape, "dtype", type, "gpudata", diffResult)'
    % ptr_sz_uint_conv,

    'PyObject* GPUArrayClass = PyObject_GetAttrString(gpuArray, "__class__")',
    'PyObject* remoteResult = PyObject_Call(GPUArrayClass, args, kwargs)',
    'return remoteResult']


host_mod.add_function(
    c.FunctionBody(
        c.FunctionDeclaration(c.Pointer(c.Value("PyObject", "adjacentDifference")),
                            [c.Pointer(c.Value("PyObject", "gpuArray"))]),
        c.Block([c.Statement(x) for x in statements])))
host_mod.add_to_preamble([c.Include('boost/python/extract.hpp')])


cuda_mod = CudaModule(host_mod)
cuda_mod.add_to_preamble([c.Include('cuda.h')])

globalIndex = 'int index = blockIdx.x * blockDim.x + threadIdx.x'
compute_diff = 'outputPtr[index] = inputPtr[index] - inputPtr[index-1]'
launch = ['CUdeviceptr output',
          'cuMemAlloc(&output, sizeof(T) * length)',
          'int bSize = 256',
          'int gSize = (length-1)/bSize + 1',
          'diffKernel<<<gSize, bSize>>>((T*)inputPtr, length, (T*)output)',
          'return output']

diff = [
    c.Template('typename T',
             CudaGlobal(c.FunctionDeclaration(c.Value('void', 'diffKernel'),
                [c.Value('T*', 'inputPtr'),
                 c.Value('int', 'length'),
                 c.Value('T*', 'outputPtr')]))),
    c.Block([c.Statement(globalIndex),
           c.If('index == 0',
              c.Statement('outputPtr[0] = inputPtr[0]'),
              c.If('index < length',
                 c.Statement(compute_diff),
                 c.Statement('')))]),

    c.Template('typename T',
                c.FunctionDeclaration(c.Value('CUdeviceptr', 'difference'),
                                          [c.Value('CUdeviceptr', 'inputPtr'),
                                           c.Value('int', 'length')])),
    c.Block([c.Statement(x) for x in launch])]

cuda_mod.add_to_module(diff)
diff_instance = c.FunctionBody(
    c.FunctionDeclaration(c.Value('CUdeviceptr', 'diffInstance'),
                        [c.Value('CUdeviceptr', 'inputPtr'),
                         c.Value('int', 'length')]),
    c.Block([c.Statement('return difference<int>(inputPtr, length)')]))

# CudaModule.add_function also adds a declaration of this
# function to the BoostPythonModule which
# is responsible for the host function.
cuda_mod.add_function(diff_instance)

import codepy.jit
import codepy.toolchain

gcc_toolchain = codepy.toolchain.guess_toolchain()
nvcc_toolchain = codepy.toolchain.guess_nvcc_toolchain()

module = cuda_mod.compile(gcc_toolchain, nvcc_toolchain, debug=True)
import pycuda.autoinit
import pycuda.driver


import pycuda.gpuarray
import numpy as np
length = 25
constantValue = 2
# This is a strange way to create a GPUArray, but is meant to illustrate
# how to construct a GPUArray if the GPU buffer it owns has been
# created by something else

pointer = pycuda.driver.mem_alloc(length * 4)
pycuda.driver.memset_d32(pointer, constantValue, length)
a = pycuda.gpuarray.GPUArray((length,), np.int32, gpudata=pointer)
b = module.adjacentDifference(a).get()

golden = [constantValue] + [0] * (length - 1)
difference = [(x-y)*(x-y) for x, y in zip(b, golden)]
error = sum(difference)
if error == 0:
    print("Test passed!")
else:
    print("Error should be 0, but is: %s" % error)
    print("Test failed")
