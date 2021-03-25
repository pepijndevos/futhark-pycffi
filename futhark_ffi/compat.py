from functools import partial, wraps

from futhark_ffi import Futhark


class Gettable(object):
    def __init__(self, fh, futdata):
        self.fh = fh
        self.futdata = futdata

    def get(self):
        return self.fh.from_futhark(self.futdata)

class FutharkCompat(Futhark):
    """
    A subclass that wraps all arrays in
    a class with a `get` method.
    For compatibility with PyOpenCL
    """

    def make_wrapper(self, ff):
        wrapper = Futhark.make_wrapper(self,ff)

        @wraps(wrapper)
        def subwrapper(*args):
            uwargs = []
            for arg in args:
                if hasattr(arg, 'futdata'):
                    uwargs.append(arg.futdata)
                else:
                    uwargs.append(arg)
            res = wrapper(*uwargs)
            wrres = []
            try:
                for r in res:
                    if isinstance(r, self.ffi.CData):
                        wrres.append(Gettable(self, r))
                    else:
                        wrres.append(r)
                return tuple(wrres)
            except TypeError:
                if isinstance(res, self.ffi.CData):
                    return Gettable(self, res)
                else:
                    return res

        return subwrapper
