# futhark-pycffi
Python library using the Futhark C backend via CFFI

Futhark provides several compilers, `futhark-opencl` which is a C backend, and `futhark-pyopencl` which is a Python backend based on PyOpenCL. However, the host-side code of the Python backend is quite slow, leading to a lot of overhead when small, frequent kernels are used.

A solution to reduce this overhead is to use CFFI to used the C backend from Python, greatly reducing the calling overhead. The OpenCL code is the same, so this is not interesting for long-running kernels.

This library supports both `futhark-opencl` and `futhark-c`. Futhark arrays are mapped to and from Numpy arrays. Multiple outputs and multi-dimensional arrays are supported. Input arrays should be in contiguous C order.

## Usage

Generate a C library, and build a Python binding for it

```bash
futhark-opencl --library test.fut
python build_futhark_ffi.py test
```

Use the Python wrapper

```python
import numpy as np
import _test
from futhark_ffi import Futhark

test = Futhark(_test)
res = test.test3(np.arange(10))
test.from_futhark(res)
```
