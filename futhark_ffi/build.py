import re
import sys
from cffi import FFI

def strip_includes(header):
    return re.sub('^(#ifdef __cplusplus\n.*\n#endif|#.*)\n', '', header, flags=re.M)

def build(name):
    ffibuilder = FFI()

    with open(name+'.c') as source:
        if sys.platform == 'darwin':
            libraries=['m']
            extra_compile_args = ['-std=c99', '-framework', 'OpenCL']
        else:
            libraries=['OpenCL']
            extra_compile_args = ['-std=c99']
        ffibuilder.set_source('_'+name, source.read(),
                              libraries=libraries,
                              extra_compile_args=extra_compile_args)

    with open(name+'.h') as header:
        cdef = 'typedef void* cl_command_queue;'
        cdef += '\ntypedef void* cl_mem;'
        cdef += strip_includes(header.read())
        cdef += "\nvoid free(void *ptr);"
        ffibuilder.cdef(cdef)

    return ffibuilder

def main():
    name = sys.argv[1]
    ffi = build(name)
    ffi.compile()
