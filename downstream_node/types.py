from sqlalchemy.ext.mutable import Mutable


class MutableTypeWrapper(Mutable):
    top_attributes = ['_underlying_object',
                      '_underlying_type',
                      '_last_state',
                      '_snapshot_update',
                      '_snapshot_changed',
                      '_notify_if_changed',
                      'changed',
                      '__getstate__',
                      '__setstate__',
                      'coerce']

    @classmethod
    def coerce(cls, key, value):
        if not isinstance(value, MutableTypeWrapper):
            return MutableTypeWrapper(value)
        else:
            return value

    def __getstate__(self):
        return self._underlying_object

    def __setstate__(self, state):
        self._underlying_type = type(state)
        self._underlying_object = state

    def __init__(self, underlying_object=None, underlying_type=None):
        if (underlying_object is None and underlying_type is None):
            raise RuntimeError(
                'Unable to create MutableTypeWrapper with no underlying object'
                ' or type.')

        if (underlying_object is not None):
            self._underlying_object = underlying_object
        else:
            self._underlying_object = underlying_type()

        if (underlying_type is not None):
            self._underlying_type = underlying_type
        else:
            self._underlying_type = type(underlying_object)

    def __getattr__(self, attr):
        if (attr in MutableTypeWrapper.top_attributes):
            return object.__getattribute__(self, attr)

        orig_attr = self._underlying_object.__getattribute__(attr)
        if callable(orig_attr):
            def hooked(*args, **kwargs):
                self._snapshot_update()
                result = orig_attr(*args, **kwargs)
                self._notify_if_changed()
                # prevent underlying from becoming unwrapped
                if result == self._underlying_object:
                    return self
                return result
            return hooked
        else:
            return orig_attr

    def __setattr__(self, attr, value):
        if (attr in MutableTypeWrapper.top_attributes):
            object.__setattr__(self, attr, value)
            return

        self._underlying_object.__setattr__(attr, value)

        self.changed()

    def _snapshot_update(self):
        try:
            self._last_state = self._underlying_object.__getstate__()
        except:
            self._last_state = dict(self._underlying_object.__dict__)

    def _snapshot_changed(self):
        try:
            return self._last_state != self._underlying_object.__getstate__()
        except:
            return self._last_state != self._underlying_object.__dict__

    def _notify_if_changed(self):
        if (self._snapshot_changed()):
            self.changed()
