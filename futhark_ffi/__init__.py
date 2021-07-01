from functools import partial, wraps

import numpy as np

np_types = {
    'int8_t': 'int8',
    'int16_t': 'int16',
    'int32_t': 'int32',
    'int64_t': 'int64',
    'uint8_t': 'uint8',
    'uint16_t': 'uint16',
    'uint32_t': 'uint32',
    'uint64_t': 'uint64',
    'float': 'float32',
    'double': 'float64',
}

c_types = {v: k for k, v in np_types.items()}

# SimpleNamespace does not exist in Python 2.7, unfortunately.
class Type: pass

class Futhark(object):
    """
    A CFFI wrapper for the Futhark C API.
    Takes a CFFI-generated module.
    Entrypoints return arrays as raw C types.
    Use `from_futhark` to convert to Numpy arrays.
    """
    def __init__(self, mod, interactive=False, device=None, platform=None, profiling=False, tuning=None):
        self.lib = mod.lib
        self.ffi = mod.ffi
        self.conf = mod.ffi.gc(mod.lib.futhark_context_config_new(), mod.lib.futhark_context_config_free)

        if device:
            mod.lib.futhark_context_config_set_device(self.conf, device)

        if platform:
            mod.lib.futhark_context_config_set_platform(self.conf, platform)

        if interactive:
            mod.lib.futhark_context_config_select_device_interactively(self.conf)

        if profiling:
            mod.lib.futhark_context_config_set_profiling(self.conf, 1)

        if tuning:
            for (k, v) in tuning.items():
                mod.lib.futhark_context_config_set_size(self.conf, k.encode("ascii"), v);

        self.ctx = mod.ffi.gc(mod.lib.futhark_context_new(self.conf), mod.lib.futhark_context_free)

        errptr = self.lib.futhark_context_get_error(self.ctx)
        if errptr:
            raise ValueError(self._get_string(errptr))

        self.make_types()
        self.make_entrypoints()

    def make_types(self):
        self.types = {}
        for fn in dir(self.lib):
            ff = getattr(self.lib, fn)
            ff_t = self.ffi.typeof(ff)
            if fn.startswith('futhark_new') and \
               not fn.startswith('futhark_new_raw'):
                ret_t = ff_t.result
                arg_t = ff_t.args[1]
                rank = len(ff_t.args[2:])
                self.types.setdefault(ret_t, Type()).new = ff
                self.types[ret_t].itemtype = arg_t
                self.types[ret_t].rank = rank
            elif fn.startswith('futhark_free'):
                arg_t = ff_t.args[1]
                self.types.setdefault(arg_t, Type()).free = ff
            elif fn.startswith('futhark_values') and \
                 not fn.startswith('futhark_values_raw'):
                arg_t = ff_t.args[1]
                self.types.setdefault(arg_t, Type()).values = ff
            elif fn.startswith('futhark_shape'):
                arg_t = ff_t.args[1]
                self.types.setdefault(arg_t, Type()).shape = ff

    def make_entrypoints(self):
        for fn in dir(self.lib):
            if fn.startswith('futhark_entry'):
                ff = getattr(self.lib, fn)
                setattr(self, fn[14:], self.make_wrapper(ff))

    def to_futhark(self, fut_type, data):
        "Convert a Numpy array to a Futhark C type"
        if isinstance(data, self.ffi.CData):
            return data # opaque type
        else:
            datat = data.astype(np_types[fut_type.itemtype.item.cname], copy=False, order='C')
            ptr = self.ffi.cast(fut_type.itemtype, self.ffi.from_buffer(datat))
            constr = fut_type.new
            destr = fut_type.free
            return self.ffi.gc(constr(self.ctx, ptr, *data.shape), partial(destr, self.ctx))

    def _errorcheck(self, err):
        if err != 0:
                raise ValueError(self._get_string(self.lib.futhark_context_get_error(self.ctx)))

    def _from_futhark(self, data):
        cname = self.ffi.typeof(data)
        fut_type = self.types[cname]
        cshape = fut_type.shape(self.ctx, data)
        shape = [cshape[i] for i in range(fut_type.rank)]
        dtype = np_types[fut_type.itemtype.item.cname]
        result = np.zeros(shape, dtype=dtype)
        cresult = self.ffi.cast(fut_type.itemtype, result.ctypes.data)
        fut_type.values(self.ctx, data, cresult)
        return result

    def from_futhark(self, *dargs):
        """
        Converts any number of Futhark C types to Numpy arrays.
        Syncs initially and again at the end.
        """
        self._errorcheck(self.lib.futhark_context_sync(self.ctx))
        out = []
        for d in dargs:
            out.append(self._from_futhark(d))
        self._errorcheck(self.lib.futhark_context_sync(self.ctx))
        if len(out) == 1:
            return out[0]
        else:
            return tuple(out)

    def make_wrapper(self, ff):
        ff_t = self.ffi.typeof(ff)
        converters = []
        out_types = []
        for arg_t in ff_t.args[1:]:
            if arg_t.kind == 'pointer' and (arg_t.item.kind == 'primitive' or arg_t.item.kind == 'pointer'):
                # output arguments
                out_types.append(arg_t)
            else:
                # input arguments
                if arg_t in self.types:
                    fut_type = self.types[arg_t]
                    converters.append(partial(self.to_futhark, fut_type))
                else:
                    converters.append(lambda x: x)

        @wraps(ff)
        def wrapper(*args):

            out_args = [self.ffi.new(t) for t in out_types]
            in_args = [f(a) for f, a in zip(converters, args)]
            err = ff(self.ctx, *(out_args+in_args))
            self._errorcheck(err)

            results = []
            for out_t, out in zip(out_types, out_args):
                if out_t.item in self.types:
                    ptr = self.ffi.gc(out[0], partial(self.types[out_t.item].free, self.ctx))
                    results.append(ptr)
                else:
                    results.append(out[0])
            if len(results) == 1:
                return results[0]
            else:
                return tuple(results)

        return wrapper

    def pause_profiling(self):
        self.lib.futhark_context_pause_profiling(self.ctx)

    def unpause_profiling(self):
        self.lib.futhark_context_unpause_profiling(self.ctx)

    def report(self):
        return self._get_string(self.lib.futhark_context_report(self.ctx))

    def _get_string(self, ptr):
        string = self.ffi.string(ptr).decode()
        self.lib.free(ptr)
        return string
