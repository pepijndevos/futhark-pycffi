import sys
from cffi import FFI

def strip_includes(lines):
    return '\n'.join(line for line in lines if not line.startswith('#'))

name = sys.argv[1]

ffibuilder = FFI()

with open(name+'.c') as source:
    ffibuilder.set_source('_'+name, source.read(), libraries=['OpenCL'])

with open(name+'.h') as header:
    cdef = strip_includes(header)
    ffibuilder.cdef(cdef)

ffibuilder.compile()
