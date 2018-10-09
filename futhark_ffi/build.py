import sys
from cffi import FFI

def strip_includes(lines):
    return '\n'.join(line for line in lines if not line.startswith('#'))

def build(name):
    ffibuilder = FFI()

    with open(name+'.c') as source:
        ffibuilder.set_source('_'+name, source.read(), libraries=['OpenCL'],
                              extra_compile_args=["-std=c99"])

    with open(name+'.h') as header:
        cdef = 'typedef void* cl_command_queue;'
        cdef += '\ntypedef void* cl_mem;'
        cdef += strip_includes(header)
        cdef += "\nvoid free(void *ptr);"
        ffibuilder.cdef(cdef)

    return ffibuilder

def main():
    name = sys.argv[1]
    ffi = build(name)
    ffi.compile()
