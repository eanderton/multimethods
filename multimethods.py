# -*- coding: utf-8 -*-

''' Multimethods

An implementation of multimethods for Python, heavily influenced by
the Clojure programming language.

Copyright (C) 2010-2011 by Daniel Werner.

Improvements by Jeff Weiss and others.

See the README file for information on usage and redistribution.
'''

import sys
py_major_version = sys.version_info[0]
if py_major_version >= 3:
    _type_classes = (type,)
else:
    import types
    _type_classes = (type, types.ClassType)

# only if not already defined, prevents mismatch when reloading modules
if 'Default' not in globals():
    class DefaultMethod(object):
        def __repr__(self):
            return '<DefaultMethod>'

    Default = DefaultMethod()


if 'Anything' not in globals():
    class AnythingType(object):
        def __repr__(self):
            return '<Anything>'

    Anything = AnythingType()


class _FeatureFlag(object):
    '''
    Basic feature flag implementation. Used to turn on/off library features.

    As a bool wrapper, this may be safely used as a default value in library
    methods and functions for run-time evaluation of a default argument.
    '''
    def __init__(self, value=False):
        self.value = bool(value)

    def __bool__(self):
        return self.value
    
    def __nonzero__(self):
        return self.__bool__()


_descriptor_interface_feature = _FeatureFlag(False)


def enable_descriptor_interface():
    '''
    Enables feature flag for descriptor interface compatibility on mutlimethods.

    By default multimethods do not forward 'self' for class methods.  Enabling this
    feature will set the module default to enable this behavior.

    If backwards compatibility is desired, it is recommended that `pass_self=True`
    argument on MultiMethod and @multimethod are used instead.
    '''
    _descriptor_interface_feature.value = True


def disable_descriptor_interface():
    '''
    Disables feature flag for descriptor interface compatibility on mutlimethods (default).

    See documentation for enable_descriptor_interface() for more information.
    '''
    _descriptor_interface_feature.value = False


def _parents(x):
    return (hasattr(x, '__bases__') and x.__bases__) or ()


def type_dispatch(*args, **kwargs):
    return tuple(type(x) for x in args)


def single_type_dispatch(*args, **kwargs):
    return type(args[0])


class DispatchException(Exception):
    pass


class _MultiMethodProxy(object):
    '''
    Shim designed for use by MultiMethod.__get__, so MultiMethod may implement the 
    'descriptor' protocol.
    
    When a method is invoked, the class' __get__ method is called to return a 'bound function' 
    that is tied to the current object instance.  This proxy simulates a bound function 
    multimethod by forwarding all properties to the parent MultiMethod, and re-implementing 
    __call__ such that it provides the object instance as 'self' to the best-matched function.
    '''

    def __init__(self, instance, mm):
        self.__dict__['instance'] = instance
        self.__dict__['mm'] = mm

    def __getattr__(self, *args, **kwargs):
        return getattr(self.__dict__['mm'], *args, **kwargs)

    def __setattr__(self, *args):
        return setattr(self.__dict__['mm'], *args, **kwargs)

    def __call__(self, *args, **kwargs):
        mm = self.__dict__['mm']
        instance = self.__dict__['instance']
        dv = mm.dispatchfn(*args, **kwargs)
        best = mm.get_method(dv)
        return best(instance, *args, **kwargs)


class MultiMethod(object):

    def __init__(self, name, dispatchfn, pass_self=_descriptor_interface_feature):
        if not callable(dispatchfn):
            raise TypeError('dispatch function must be a callable')

        self.dispatchfn = dispatchfn
        self.methods = {}
        self.preferences = {}
        self.cache = {}
        self.__name__ = name
        self.pass_self = bool(pass_self)  # force evaluation of feature flag
        # self.cache_hites

    def __call__(self, *args, **kwds):
        dv = self.dispatchfn(*args, **kwds)
        best = self.get_method(dv)
        return best(*args, **kwds)

    def __get__(self, instance, owner):
        '''
        Return a bound method if invoked on an object instance, and if pass_self is true.
        '''
        if instance is None or not self.pass_self:
            return self
        return _MultiMethodProxy(instance, self)

    def add_method(self, dispatchval, func):
        self.methods[dispatchval] = func
        self._reset_cache()

    def remove_method(self, dispatchval):
        del self.methods[dispatchval]
        self._reset_cache()

    def get_method(self, dv):
        target = self.cache.get(dv, None)
        if target:
            return target
        k = self.find_best_method(dv)
        if k is not Default or k in self.methods:
            target = self.methods[k]
            self.cache[dv] = target
            return target
        if target:
            return target
        else:
            raise DispatchException("No matching method on multimethod '%s' for '%s', and "
                                    "no default method defined" % (self.__name__, dv))

    def _reset_cache(self):
        self.cache = self.methods.copy()

    def _dominates(self, x, y):
        return self._prefers(x, y) or _is_a(x, y)

    def find_best_method(self, dv):
        best = Default
        for k in self.methods:
            if k is Default:
                continue  # don't bother comparing with Default
            if _is_a(dv, k):
                if best is Default or self._dominates(k, best):
                    best = k
                # raise if there's multiple matches and they don't point
                # to the exact same method
                if (not self._dominates(best, k)) and \
                   (self.methods[best] is not self.methods[k]):
                    raise DispatchException("Multiple methods in multimethod '%s'"
                                            " match dispatch value %s -> %s and %s, and neither is"
                                            " preferred" % (self.__name__, dv, k, best))
        # self.cache[dv] = best
        # print self.cache
        # print self.methods
        return best

    def _prefers(self, x, y):
        xprefs = self.preferences.get(x)
        if xprefs is not None and y in xprefs:
            return True
        for p in _parents(y):
            if self._prefers(x, p):
                return True
        for p in _parents(x):
            if self._prefers(p, y):
                return True
        return False

    def prefer(self, dispatchvalX, dispatchvalY):
        if self._prefers(dispatchvalY, dispatchvalX):
            raise Exception("Preference conflict in multimethod '%s':"
                            " %s is already preferred to %s" %
                            (self.__name__, dispatchvalY, dispatchvalX))
        else:
            cur = self.preferences.get(dispatchvalX, set())
            cur.add(dispatchvalY)
            self.preferences[dispatchvalX] = cur
            self._reset_cache()

    def method(self, dispatchval):
        def method_decorator(func):
            self.add_method(dispatchval, func)
            return func
        return method_decorator

    def __repr__(self):
        return "<MultiMethod '%s'>" % _name(self)


def _name(f):
    return "%s.%s" % (f.__module__, f.__name__)


def _copy_attrs(source, dest):
    dest.__doc__ = source.__doc__
    dest.__module__ = source.__module__


def multimethod(dispatch_func, pass_self=_descriptor_interface_feature):
    '''Create a multimethod that dispatches on the given dispatch_func,
    and uses the given default_func as the default dispatch.  The
    multimethod's descriptive name will also be taken from the
    default_func (its module and name).

    If pass_self is set to True, this multimethod will pass the enclosing
    object instance as `self` to all associated methods, as though they 
    were normal class methods (where applicable).
    '''
    def multi_decorator(default_func):
        m = MultiMethod(default_func.__name__, dispatch_func, pass_self)
        m.add_method(Default, default_func)
        _copy_attrs(default_func, m)
        return m
    return multi_decorator


def singledispatch(default_func):
    '''Like python 3.4's singledispatch. Create a multimethod that
    does single dispatch by the type of the first argument. The
    wrapped function will be the default dispatch.

    In order to use class methods that use 'self' passing with this decorator,
    see `enable_descriptor_interface()` for more information.
    '''
    m = MultiMethod(default_func.__name__, single_type_dispatch)
    m.add_method(Default, default_func)
    _copy_attrs(default_func, m)
    return m


def multidispatch(default_func):
    '''Create a multimethod that does multiple dispatch by the types of
    all the arguments. The wrapped function will be the default
    dispatch.
    
    In order to use class methods that use 'self' passing with this decorator,
    see `enable_descriptor_interface()` for more information.
    '''
    m = MultiMethod(default_func.__name__, type_dispatch)
    m.add_method(Default, default_func)
    _copy_attrs(default_func, m)
    return m


def _is_a(x, y):
    '''Returns true if x == y or x is a subclass of y. Works with tuples
       by calling _is_a on their corresponding elements.

    '''
    def both(a, b, typeslist):
        return isinstance(a, typeslist) and isinstance(b, typeslist)
    if both(x, y, (tuple)):
        return all(map(_is_a, x, y))
    else:
        if both(x, y, _type_classes):
            return issubclass(x, y)
        else:
            return is_a(x, y)


@multidispatch
def is_a(x, y):
    '''Returns true if x is a y.  By default, if x == y.

    Since is_a is used internally by multimethods, and is itself a
    multimethod, infinite recursion is possible *if* the dispatch
    values cycle among two or more non-default is_a dispatches.

    '''
    return x == y


@is_a.method((object, AnythingType))
def _is_a_anything(x, y):
    '''x is always an Anything'''
    return True


__all__ = ['enable_descriptor_interface', 'disable_descriptor_interface',
           'MultiMethod', 'type_dispatch', 'single_type_dispatch',
           'multimethod', 'Default', 'multidispatch', 'singledispatch',
           'Anything']
