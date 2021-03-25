import re
import sys

from cffi import FFI


def strip_includes(header):
    return re.sub('^(#ifdef __cplusplus\n.*\n#endif|#.*)\n', '', header, flags=re.M)

def build(name):
    ffibuilder = FFI()

    header_file = name+'.h'
    source_file = name+'.c'

    search = re.search('#define FUTHARK_BACKEND_([a-z0-9_]*)', open(header_file).read())
    if not search:
        sys.exit('Cannot determine Futhark backend from {}'.format(header_file))

    backend=search.group(1)

    with open(source_file) as source:
        libraries = ['m']
        extra_compile_args = ['-std=c99']
        if backend == 'opencl':
            if sys.platform == 'darwin':
                extra_compile_args += ['-framework', 'OpenCL']
            libraries += ['OpenCL']
        elif backend == 'cuda':
            libraries += ['cuda', 'cudart', 'nvrtc']
        elif backend == 'multicore':
            extra_compile_args += ['-pthread']
        ffibuilder.set_source('_'+name, source.read(),
                              libraries=libraries,
                              extra_compile_args=extra_compile_args)

    with open(header_file) as header:
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
