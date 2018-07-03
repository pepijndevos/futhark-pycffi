from functools import partial
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

class Futhark(object):
    def __init__(self, mod):
        self.lib = mod.lib
        self.ffi = mod.ffi
        self.conf = mod.ffi.gc(mod.lib.futhark_context_config_new(), mod.lib.futhark_context_config_free)
        self.ctx = mod.ffi.gc(mod.lib.futhark_context_new(self.conf), mod.lib.futhark_context_free)
        
        self.types = {}
        for fn in dir(mod.lib):
            ff = getattr(mod.lib, fn)
            ff_t = mod.ffi.typeof(ff)
            if fn.startswith('futhark_new'):
                ret_t = ff_t.result
                arg_t = ff_t.args[1]
                dim = len(ff_t.args[2:])
                self.types.setdefault(ret_t, {})['new'] = ff
                self.types.setdefault(ret_t, {})['itemtype'] = arg_t
                self.types.setdefault(ret_t, {})['dimension'] = dim
            elif fn.startswith('futhark_free'):
                arg_t = ff_t.args[1]
                self.types.setdefault(arg_t, {})['free'] = ff
            elif fn.startswith('futhark_values'):
                arg_t = ff_t.args[1]
                self.types.setdefault(arg_t, {})['values'] = ff
            elif fn.startswith('futhark_shape'):
                arg_t = ff_t.args[1]
                self.types.setdefault(arg_t, {})['shape'] = ff

    def to_futhark(self, cname, data):
        if isinstance(data, self.ffi.CData):
            return data # opaque type
        else:
            fut_type = self.types[cname]
            datat = data.astype(np_types[fut_type['itemtype'].item.cname], copy=False)
            ptr = self.ffi.cast(fut_type['itemtype'], self.ffi.from_buffer(datat))
            constr = fut_type['new']
            destr = fut_type['free']
            return self.ffi.gc(constr(self.ctx, ptr, *data.shape), partial(destr, self.ctx))

    def _from_futhark(self, data):
        cname = self.ffi.typeof(data)
        fut_type = self.types[cname]
        cshape = fut_type['shape'](self.ctx, data)
        shape = [cshape[i] for i in range(fut_type['dimension'])]
        dtype = np_types[fut_type['itemtype'].item.cname]
        result = np.zeros(shape, dtype=dtype)
        cresult = self.ffi.cast(fut_type['itemtype'], result.ctypes.data)
        fut_type['values'](self.ctx, data, cresult)
        return result

    def from_futhark(self, *dargs):
        out = []
        for d in dargs:
            out.append(self._from_futhark(d))
        self.lib.futhark_context_sync(self.ctx)
        if len(out) == 1:
            return out[0]
        else:
            return tuple(out)

    def call(self, name, *args):
        name = 'futhark_' + name
        ff = getattr(self.lib, name)
        ff_t = self.ffi.typeof(ff)
        fut_args = []
        out_args = []
        arg_idx = 0
        for arg_t in ff_t.args[1:]:
            if arg_t.kind == 'pointer' and (arg_t.item.kind == 'primitive' or arg_t.item.kind == 'pointer'):
                # output arguments
                out_t = arg_t.cname
                out_args.append(self.ffi.new(out_t))
            else:
                # input arguments
                if arg_t in self.types:
                    fut_args.append(self.to_futhark(arg_t, args[arg_idx]))
                else:
                    fut_args.append(args[arg_idx])
                arg_idx += 1
        ff(self.ctx, *out_args, *fut_args)
        results = []
        for out in out_args:
            out_t = self.ffi.typeof(out).item
            if out_t in self.types:
                ptr = self.ffi.gc(out[0], partial(self.types[out_t]['free'], self.ctx))
                results.append(ptr)
            else:
                results.append(out[0])
        if len(results) == 1:
            return results[0]
        else:
            return tuple(results)


    def __getattr__(self, attr):
        return partial(self.call, attr)
