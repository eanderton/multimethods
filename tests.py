import unittest
from multimethods import (MultiMethod, Default, type_dispatch, DispatchException, Anything,
                          multimethod, singledispatch, multidispatch, is_a)
from collections import Iterable
identity = lambda x: x


class Basic(unittest.TestCase):
    def test_basics(self):
        speaksum = MultiMethod('speaksum', lambda *a: sum(a))

        @speaksum.method(2)
        def _speaksum2(x, y, z):
            return "Two"

        @speaksum.method(5)
        def _speaksum5(x, y):
            return "Five"

        @speaksum.method(0)
        def _speaksum0(x, y):
            return "Zero"

        @speaksum.method(Default)
        def _speaksum_d(x, y, z):
            return "Another"

        self.assertEqual(speaksum(1, 1, 0), "Two")
        self.assertEqual(speaksum(3, 2), "Five")
        self.assertEqual(speaksum(9, 8, 2), "Another")
        self.assertEqual(speaksum(3, 5, 6), "Another")
        self.assertEqual(speaksum(-1, 1), "Zero")

        # Too many arguments to method
        self.assertRaises(TypeError, lambda: speaksum(2, 3, 0, 0, 0))

    def test_addmethod(self):
        foomethod = MultiMethod('foomethod', identity)

        foomethod.add_method(42, lambda x: "The Answer")
        foomethod.add_method(1024, lambda x: "2^10")
        foomethod.add_method(Default, lambda x: "Nothing")

        self.assertEqual(foomethod(42), "The Answer")
        self.assertEqual(foomethod(1024), "2^10")
        self.assertEqual(foomethod(Default), "Nothing")

    def test_removemethod(self):
        barmethod = MultiMethod('barmethod', identity)

        @barmethod.method(1)
        def barmethod1(x):
            return 123

        self.assertEqual(barmethod(1), 123)

        barmethod.remove_method(1)
        self.assertRaises(Exception, lambda: barmethod(1))

        @barmethod.method(Default)
        def barmethod_d(x):
            return 42

        self.assertEqual(barmethod("whatever"), 42)
        self.assertEqual(barmethod("something"), 42)

        barmethod.remove_method(Default)
        self.assertRaises(Exception, lambda: barmethod("whatever"))
        self.assertRaises(Exception, lambda: barmethod(1))

    def test_name_conflict(self):
        # Shouldn't cause any problems
        foobar1 = MultiMethod('foobar', identity)
        foobar2 = MultiMethod('foobar', identity)

        @foobar1.method(1)
        def foobar1(x):
            return "foobar1"

        @foobar2.method(2)
        def foobar2(selfx):
            return "foobar2"

        self.assertEqual(foobar1(1), "foobar1")
        self.assertEqual(foobar2(2), "foobar2")

    def test_falsey_values(self):
        foobar3 = MultiMethod('foobar3', identity)

        @foobar3.method(0)
        def foobar30(x):
            return "zero"

        @foobar3.method(None)
        def foobar3n(x):
            return "none"

        self.assertEqual(foobar3(0), "zero")
        self.assertEqual(foobar3(False), "zero")  # in python False == 0
        self.assertEqual(foobar3(None), "none")


class Item(object):
    pass


class BoxedItem(Item):
    pass


class FragileItem(BoxedItem):
    pass


class ExpensiveItem(Item):
    pass


class Dispatch(unittest.TestCase):

    discount = MultiMethod('tests.Dispatch.discount', lambda name, item: (len(name), type(item)))

    @discount.method((5, ExpensiveItem))
    def dis_25(name, item):
        return 25

    @discount.method((10, ExpensiveItem))
    def dis_30(name, item):
        return 30

    @discount.method((Anything, ExpensiveItem))
    def dis_15(name, item):
        return 15

    @discount.method((5, Item))
    def dis_5(name, item):
        return 5

    discount.prefer((Anything, ExpensiveItem), (5, Item))

    @discount.method(Default)
    def default(name, item):
        return 0

    myitem = BoxedItem()

    def test_hierarchy(self):
        self.assertEqual(self.discount("steve", ExpensiveItem()), 25)
        self.assertEqual(self.discount("chrisjones", ExpensiveItem()), 30)
        self.assertEqual(self.discount("steve", BoxedItem()), 5)
        self.assertEqual(self.discount("joe", Item()), 0)

    def test_anything(self):
        self.assertEqual(self.discount("joe", ExpensiveItem()), 15)

    def test_cache(self):
        self.assertEqual(self.discount("steve", self.myitem), 5)
        #self.assertEqual(self.discount("myverylongname", self.myitem), 30)
        self.assertIn((5, BoxedItem), self.discount.cache)


class Prefer(unittest.TestCase):

    pref = MultiMethod('pref', type_dispatch)

    class MyList(list):
        pass

    @pref.method(Default)
    def pd(x, y):
        return "default"

    @pref.method((Iterable, object))
    def pio(x, y):
        return "io"

    @pref.method((object, Iterable))
    def poi(x, y):
        return "oi"

    @pref.method((list, object))
    def plo(x, y):
        return "lo"

    @pref.method((object, list))
    def pol(x, y):
        return "ol"

    @pref.method((Iterable, list))
    def pil(x, y):
        return "il"

    @pref.method((list, Iterable))
    def pli(x, y):
        return "li"

    @pref.method((str, object))
    def pso(x, y):
        return "so"

    @pref.method((object, str))
    def pos(x, y):
        return "os"

    #pref.prefer((str, object), (object, str))
    pref.prefer((object, Iterable), (Iterable, object))

    def test_ambiguous(self):
        self.assertEqual(self.pref(5, 6), "default")
        self.assertRaises(DispatchException, self.pref, "sdf", "dgf")

    # def test_prefer(self):
    #     self.assertEqual(self.pref(Prefer.MyList(), Prefer.MyList()), "lo")

    def test_prefer_not_needed_on_same_method(self):
        bar = MultiMethod('bar', type_dispatch)

        @bar.method((object, str))
        @bar.method((str, object))
        def barstr(x, y):
            return "os " + str(x) + str(y)

        @bar.method((int, int))
        def other(x, y):
            return 5

        self.assertEqual(bar("sdf", "dgf"), "os sdfdgf")
        self.assertEqual(bar(3, 6), 5)


def mylen(x):
    return len(x)


class Decorators(unittest.TestCase):

    @multimethod(mylen)
    def mm(x):
        '''docstring'''
        return "default"

    def test_multimethod(self):
        self.assertEqual(self.mm.methods[Default].__name__, "mm")
        self.assertEqual(self.mm.dispatchfn, mylen)
        self.assertEqual(self.mm.__doc__, "docstring")
        self.assertEqual(self.mm.__name__, "mm")


class IsA(unittest.TestCase):
    class Version(object):
        def __init__(self, version):
            self.version = version

        def __str__(self):
            return "<Version %s>" % str(self.version)

    something = MultiMethod('tests.isA.something', lambda v: IsA.Version(v))

    @something.method(Version(25))
    def something_25(foo):
        return 25

    @something.method(Version(30))
    def something_30(foo):
        return 30

    @something.method(Version(15))
    def something_15(foo):
        return 15

    @something.method(Version(5))
    def something_5(foo):
        return 5

    @something.method(Default)
    def default(foo):
        return 0

    @is_a.method((Version, Version))
    def _is_a_version(x, y):
        return x.version >= y.version

    def test_is_a(self):
        self.assertEqual(self.something(31), 30)
        self.assertEqual(self.something(6), 5)
        self.assertEqual(self.something(-10), 0)
        self.assertEqual(self.something(25), 25)


class Decorators(unittest.TestCase):

    def test_singledispatch(self):
        @singledispatch
        def mm(value):
            return 'default', value

        @mm.method(dict)
        def mm_int(value):
            return 'dict', value

        @mm.method(str)
        def mm_str(value):
            return 'str', value

        @mm.method(float)
        def mm_str(value):
            return 'float', value

        self.assertEqual(mm({}), ('dict', {}))
        self.assertEqual(mm(12345), ('default', 12345))
        self.assertEqual(mm(123.45), ('float', 123.45))
        self.assertEqual(mm('foo'), ('str', 'foo'))

    def test_multiispatch(self):
        @multidispatch
        def mm(*args):
            return 'default', args

        @mm.method((dict, list))
        def mm_int(a, b):
            return 'dict+list', a, b

        @mm.method((str, float))
        def mm_str(a, b):
            return 'str+float', a, b

        self.assertEqual(mm({}, []), ('dict+list', {}, []))
        self.assertEqual(mm(12345), ('default', (12345,)))
        self.assertEqual(mm('foo', 123.45), ('str+float', 'foo', 123.45))
