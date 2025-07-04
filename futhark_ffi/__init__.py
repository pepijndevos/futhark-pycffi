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
    def __init__(self, mod, interactive=False, device=None, platform=None, profiling=False, tuning=None, cache_file_path=None):
        self.lib = mod.lib
        self.ffi = mod.ffi
        conf = mod.lib.futhark_context_config_new()
        self.conf = conf

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
                mod.lib.futhark_context_config_set_tuning_param(self.conf, k.encode("ascii"), v)

        if cache_file_path:
            mod.lib.futhark_context_config_set_cache_file(self.conf, cache_file_path.encode("ascii"))

        def free_ctx(ctx):
            mod.lib.futhark_context_free(ctx)
            mod.lib.futhark_context_config_free(conf)

        self.ctx = mod.ffi.gc(mod.lib.futhark_context_new(self.conf), free_ctx)

        errptr = self.lib.futhark_context_get_error(self.ctx)
        if errptr:
            raise ValueError(self._get_string(errptr))

        self.make_types()
        self.make_entrypoints()
        self.make_stores()
        self.make_restores()

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

    def make_stores(self):
        for fn in dir(self.lib):
            if fn.startswith('futhark_store'):
                ff = getattr(self.lib, fn)
                setattr(self, 'store' + fn[20:], self.make_store_wrapper(ff))

    def make_restores(self):
        for fn in dir(self.lib):
            if fn.startswith('futhark_restore'):
                ff = getattr(self.lib, fn)
                setattr(self, 'restore' + fn[22:], self.make_restore_wrapper(ff))

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

    def make_store_wrapper(self, ff):

        @wraps(ff)
        def wrapper(opaque):
            bytes_ptr_ptr = self.ffi.new('void **', self.ffi.NULL)
            size_ptr = self.ffi.new('size_t *')
            err = ff(self.ctx, opaque, bytes_ptr_ptr, size_ptr)
            self._errorcheck(err)
            bytes_ptr = self.ffi.gc(bytes_ptr_ptr[0], self.lib.free)
            return self.ffi.buffer(bytes_ptr, size_ptr[0])

        return wrapper

    def make_restore_wrapper(self, ff):
        fut_type = self.ffi.typeof(ff).result

        @wraps(ff)
        def wrapper(buffer):
            bytes_ptr = self.ffi.from_buffer(buffer)
            res = ff(self.ctx, bytes_ptr)
            #handle NULL pointer
            if res:
                return self.ffi.gc(res, partial(self.types[fut_type].free, self.ctx))
            else:
                raise ValueError("failed to restore value from buffer")

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
