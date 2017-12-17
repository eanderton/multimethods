multimethods.py - Multimethods for Python
=========================================

This module adds multimethod support to the Python programming language. In
contrast to other multiple dispatch implementations, this one doesn't strictly
dispatch on argument types, but on a user-provided dispatch function that can
differ for each multimethod. This design is inspired the Clojure programming
language's multimethod implementation.


What are multimethods?
----------------------

Multimethods provide a mechanism to dispatch function execution to different
implementations of this function. It works similarly to the well-known concept
of "instance methods" in OO languages like Python, which in a call to
obj.method() would look up a member called "method" in obj's class.

However, multimethod methods are NOT necessarily associated with a
single class. Instead, they belong to a ``MultiMethod`` instance. Calls
on the MultiMethod will be dispatched to its corresponding methods
using a custom, user-defined dispatch function.  This is an important
benefit - you can make Alice's class fulfill Bob's contract, and
neither of them need to know about each other, or you. Extending a
class is simple, but it runs the risk of naming
collision. Multimethods are part of a module, so there is no chance of
collision.

The dispatch function can be any callable. Once a MultiMethod is called, the
dispatch function will receive the exact arguments the MultiMethod call
received, and is expected to return a value that will be dispatched on. This
return value is then used to select a 'method', which is basically just
a function that has been associated with this multimethod and dispatch value
using the multimethod's ``@method`` decorator.

Note that in the dispatch function lies the real power of this whole concept.
For example, you can use it to dispatch on the type of the arguments like in
Java/C, on their exact values, or whether they evaluate to True in a boolean
context. If the arguments are dictionaries, you can dispatch on whether they
contain certain keys. Or, if you want to go really wild, you could even send
these arguments over the network to a remote service and let that decide which
method to call.

Of course, not every possible application of multimethods is actually useful,
but your creativity is the only limit to what you can do.


How to use multimethods
-----------------------

To use multimethods, a ``MultiMethod`` instance must be created first. Each
MultiMethod instance takes a name and a dispatch function, as discussed above.

Methods are associated with MultiMethods by decorating a function using the
``@method`` decorator, which is an attribute of the multimethod itself. This
decorator registers the function for a dispatch value so that whenever the
MultiMethod is called and its dispatch function returns this value, the
decorated function will be selected.

Okay, that was dry enough. Let's put this concept to work with a small example:


Example: Dispatch on Argument Type
----------------------------------

Without multimethods, naively implementing a function that has two different
behaviours based on a the types of the arguments could look like this

.. code:: python

  def combine(x, y):
      if isinstance(x, int) and isinstance(y, int):
          return x * y
      elif isinstance(x, basestring) and isinstance(y, basestring):
          return x + '&' + y
      else:
          return '???'

However, this is ugly and becomes unwieldy fast as we add more elif cases for
additional types. Fortunately, implementing dispatch on function arguments'
types is easy using multimethodic. Let's implement a multimethod version of
``combine()`` with exactly the same signature.

First, we have to define a dispatch function. It will take the same arguments
as the multimethod, and return a value which is then used to select the correct
method implementation

.. code:: python

    def dispatch_combine(x, y):
        return (type(x), type(y))

Thus, we are going to dispatch on a tuple of types, namely the types of our
arguments. The next step is to instantiate the MultiMethod itself

.. code:: python

    from multimethods import MultiMethod, Default

    combine = MultiMethod('combine', dispatch_combine)

A multimethod by itself does almost nothing. It is dependent on being given
methods in order to implement its functionality for different dispatch values.
Let's define methods for all-integer and all-string cases as above

.. code:: python

    @combine.method((int, int))
    def _combine_int(x, y):
        return x * y

    @combine.method((str, str))
    def _combine_str(x, y):
        return x + '&' + y

    @combine.method(Default)
    def _combine(x, y):
        return '???'

The behaviour for ints and strings is straightforward

.. code:: python

    >>> combine(21, 2)
    42
    >>> combine('foo', 'bar')
    'foo&bar'

However, notice the last method definition above. Instead of specifying a tuple
of types, we have given it the special ``multimethods.Default`` object. This is
a marker which simply tells the multimethod: "In case we don't have a method
implementation for some dispatch value, just use this method instead." Let's
test it

.. code:: python

  >>> combine(21, 'bar')
  '???'

Default methods are completely optional, you are free not to provide one at
all. A ``DispatchException`` will be raised for unknown dispatch values instead.

Now would be a good time to show that the dispatch function's signature doesn't
have to match its methods' signature bit-by-bit. Let's make the dispatch
function more generic

.. code:: python

    def dispatch_on_arg_type(*args):
        return tuple(type(x) for x in args)

This version will support all possible (non-variadic, non-keyword) signatures
at no additional cost, and makes it easy to re-use the dispatch function for
other multimethods with different numbers of arguments.


Example: Poor man's pattern matching
------------------------------------

What follows is a horribly inefficient algorithm to determine a list's length.
It is often used as an example to teach basic recursion, and also shows how edge
cases can be modeled using simple pattern matching.

.. code:: python

    from multimethods import MultiMethod, Default

    identity = lambda x: x
    len2 = MultiMethod('len2', identity)

    @len2.method([])
    def _len2(l):
        return 0

    @len2.method(Default)
    def _len2d(l):
        return 1 + len2(l[1:])


Example: Special procedures for special customers
-------------------------------------------------

Here's a slightly more involved example. Let's say ACME Corporation has
standard billing procedures that apply to most of its customers, but some of
the bigger customers receive wildly different conditions. How do we express
this in code without resorting to heaps of ``if`` statements?

.. code:: python

    from multimethods import MultiMethod, Default

    def sum_amounts(purchase):
        return sum(product.price for product in purchase)

    def get_customer(purchase):
        return purchase.customer.company_name

    calc_total = MultiMethod('calc_total', get_customer)
    method = calc_total.method

    @method(Default)
    def _calc_total(purchase):
        # Normal customer pricing
        return sum_amounts(purchase)

    @method("Wile E.")
    def _calc_total_we(purchase):
        # Always gets 20% off
        return sum_amounts(purchase) * 0.8

    @method("Wolfram & Hart")
    def _calc_total_wh(purchase):
        # Has already paid an annual flat fee in advance; also receives
        # a token of enduring friendship with every order
        purchase.append(champagne)
        return 0.0


'Is A' based matching
---------------------

The way multimethods determine if one dispatch value 'matches' another is through a function called ``is_a``.  For example, you are already familiar with how ``is_a`` works with types - str 'is a' object, list 'is a' Sequence, Ford 'is a' Automobile, etc.  For types, ``is_a`` just decides if one is a subclass of the other.

You can extend this behavior because ``is_a`` is itself a multimethod!  So if you want to create relationships for other values besides types, you can.

For example, if you want to dispatch on version numbers, you can define one Version ``is_a`` other Version if the former Version number is greater

.. code:: python

    from multimethods import is_a

    class Version(object):
        def __init__(self, ver):
             self.ver = ver

    @is_a.method((Version, Version))
    def _is_version(a, b):
        return a.ver > b.ver


Now your dispatch values can be instances of ``Version``.  So for example

.. code:: python

    from multimethods import MultiMethod

    v1 = Version(1)
    v5 = Version(5)

    foo = MultiMethod("foo", lambda x: get_current_version())

    @foo.method(v1)
    def _foo1(x):
       print "do this for v1 and greater"

    @foo.method(v5)
    def _foo5(x):
       print "do this for v5 and greater"

    foo("hi")  # if current version is 2, dispatches to v1.


Use with Classes
----------------

Multimethods may also be used as a class method, to dispatch to other methods within the same class.

.. code:: python
 
    class Adder(object):
        add = MultiMethod("adder", type_dispatch)

        @add.method((int, int))
        def add_integers(a, b):
            return a + b

        @add.method((float, float))
        def add_floats(a, b):
            return int(round(a + b))

    adder = Adder()
    result = adder.add(10, 20)
    result += adder.add(10.5, 17.3)
    assert(result == 58) 


As the above example illustrates, the multimethod will not forward ``self`` to the methods.  This behavior
can be changed by creating a multimethod with ``pass_self=True`` as an argument:

.. code:: python
    # explicit instance style
    mm = MultiMethod('mm', my_dispatch_function, pass_self=True)

    # decorator style
    @multimethod(my_dispatch_function, pass_self=True)
    def mm(...): ...


Now the class can be implemented with methods that can see the enclosing object:

.. code:: python
 
    class Adder(object):
        def __init__(self):
            self.result = 0

        add = MultiMethod("adder", type_dispatch, pass_self=True)

        @add.method((int, int))
        def add_integers(self, a, b):
            self.result += a + b

        @add.method((float, float))
        def add_floats(self, a, b):
            self.result += int(round(a + b))

    adder = Adder()
    adder.add(10, 20)
    adder.add(10.5, 17.3)
    assert(adder.result == 58)


This feature is made possible by the python descriptor protocol, which only applies to multimethods
that are invoked as members of a class.  Multimethods that are declared and used outside the context of
a class, won't have this property, even if ``pass_self`` is set to True.


Descriptor Interface Feature Flag
---------------------------------

By default all multimethods are constructed with ``pass_self=False``.  This default may be changed by using the
``descriptor_interface`` feature flag.  It may be enabled like so:

.. code:: python

    from multimethod import *
    enable_descriptor_interface()


After this feature is enabled, all subsequent instances of ``MultiMethod`` or invocations of ``@multimethod``,
``@singledispach``, and ``@multidispatch``. will pass ``self`` to dispatched methods when invoked as a member
of a class.

The feature may also be disabled, or future-proofed as disabled should it be enabled in a future release:

.. code:: python
 
    from multimethod import *
    disable_descriptor_interface()


Note
****

Tuples are treated specially as dispatch values.  All the individual items are compared using ``is_a``, and only matches if all the individual values match.  For example a dispatch value of

.. code:: python

    (int, int)

will match a method of

.. code:: python

    (object, object)


Author & License
----------------

This work has been created by and is copyrighted by Daniel Werner. All rights
reserved, and that kind of stuff. You may freely use this work under the terms
of the simplified (2-clause) version of the BSD license, a copy of which is
included in this distribution.


Credits & Thanks
----------------

While this Python module is new, the idea of multimethods is definitely not.
Common Lisp has its generic functions, which only dispatch on type (and eql).
There has also been a prior Python implementation by Guido van Rossum, which is
even more limited.

This module however is really a near-faithful implementation of multimethods as
found in the Clojure programming language (http://clojure.org), sans beautiful
macro-based syntax. I'd like to give credit to the principal author of
Clojure, Rich Hickey, for coming up with the idea to generalize multimethods to
use a custom dispatch function, and for publishing his implementation for the
world to use (and port to different languages). Thanks, Rich!

Thanks to Daniel Werner for the original implementation, tests, and
this document - modifications by Jeff Weiss.

Thanks to Matthew von Rocketstein for providing me with a setup.py, and to Eric
Shull for raising the issue of proper namespacing and implementing a solution.
