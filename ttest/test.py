from marketplace import Marketplace
import os
import sqlite3
from logbook import NullHandler, Logger
from six import with_metaclass, iteritems
from abc import ABCMeta, abstractmethod
from unittest import TestCase

def bases_mro(bases):
    """
    Yield classes in the order that methods should be looked up from the
    base classes of an object.
    """
    for base in bases:
        for class_ in base.__mro__:
            yield class_


def is_final(name, mro):
    """
    Checks if `name` is a `final` object in the given `mro`.
    We need to check the mro because we need to directly go into the __dict__
    of the classes. Because `final` objects are descriptor, we need to grab
    them _BEFORE_ the `__call__` is invoked.
    """
    return any(isinstance(getattr(c, '__dict__', {}).get(name), final)
               for c in bases_mro(mro))


class FinalMeta(type):
    """A metaclass template for classes the want to prevent subclassess from
    overriding a some methods or attributes.
    """
    def __new__(mcls, name, bases, dict_):
        for k, v in iteritems(dict_):
            if is_final(k, bases):
                raise _type_error

        setattr_ = dict_.get('__setattr__')
        if setattr_ is None:
            # No `__setattr__` was explicitly defined, look up the super
            # class's. `bases[0]` will have a `__setattr__` because
            # `object` does so we don't need to worry about the mro.
            setattr_ = bases[0].__setattr__

        if not is_final('__setattr__', bases) \
           and not isinstance(setattr_, final):
            # implicitly make the `__setattr__` a `final` object so that
            # users cannot just avoid the descriptor protocol.
            dict_['__setattr__'] = final(setattr_)

        return super(FinalMeta, mcls).__new__(mcls, name, bases, dict_)

    def __setattr__(self, name, value):
        """This stops the `final` attributes from being reassigned on the
        class object.
        """
        if is_final(name, self.__mro__):
            raise _type_error

        super(FinalMeta, self).__setattr__(name, value)


class final(with_metaclass(ABCMeta)):
    """
    An attribute that cannot be overridden.
    This is like the final modifier in Java.
    Example usage:
    >>> from six import with_metaclass
    >>> class C(with_metaclass(FinalMeta, object)):
    ...    @final
    ...    def f(self):
    ...        return 'value'
    ...
    This constructs a class with final method `f`. This cannot be overridden
    on the class object or on any instance. You cannot override this by
    subclassing `C`; attempting to do so will raise a `TypeError` at class
    construction time.
    """
    def __new__(cls, attr):
        # Decide if this is a method wrapper or an attribute wrapper.
        # We are going to cache the `callable` check by creating a
        # method or attribute wrapper.
        if hasattr(attr, '__get__'):
            return object.__new__(finaldescriptor)
        else:
            return object.__new__(finalvalue)

    def __init__(self, attr):
        self._attr = attr

    def __set__(self, instance, value):
        """
        `final` objects cannot be reassigned. This is the most import concept
        about `final`s.
        Unlike a `property` object, this will raise a `TypeError` when you
        attempt to reassign it.
        """
        raise _type_error

    @abstractmethod
    def __get__(self, instance, owner):
        raise NotImplementedError('__get__')

class finaldescriptor(final):
    """
    A final wrapper around a descriptor.
    """
    def __get__(self, instance, owner):
        return self._attr.__get__(instance, owner)

class WithLogger(object):
    """
    CatalystTestCase mixin providing cls.log_handler as an instance-level
    fixture.
    After init_instance_fixtures has been called `self.log_handler` will be a
    new ``logbook.NullHandler``.
    Methods
    -------
    make_log_handler() -> logbook.LogHandler
        A class method which constructs the new log handler object. By default
        this will construct a ``NullHandler``.
    """
    make_log_handler = NullHandler

    @classmethod
    def init_class_fixtures(cls):
        super(WithLogger, cls).init_class_fixtures()
        cls.log = Logger()
        cls.log_handler = cls.enter_class_context(
            cls.make_log_handler().applicationbound(),
        )


class CatalystTestCase(with_metaclass(FinalMeta, TestCase)):
    """
    Shared extensions to core unittest.TestCase.
    Overrides the default unittest setUp/tearDown functions with versions that
    use ExitStack to correctly clean up resources, even in the face of
    exceptions that occur during setUp/setUpClass.
    Subclasses **should not override setUp or setUpClass**!
    Instead, they should implement `init_instance_fixtures` for per-test-method
    resources, and `init_class_fixtures` for per-class resources.
    Resources that need to be cleaned up should be registered using
    either `enter_{class,instance}_context` or `add_{class,instance}_callback}.
    """
    _in_setup = False

    @final
    @classmethod
    def setUpClass(cls):
        # Hold a set of all the "static" attributes on the class. These are
        # things that are not populated after the class was created like
        # methods or other class level attributes.
        cls._static_class_attributes = set(vars(cls))
        cls._class_teardown_stack = ExitStack()
        try:
            cls._base_init_fixtures_was_called = False
            cls.init_class_fixtures()
            assert cls._base_init_fixtures_was_called, (
                "CatalystTestCase.init_class_fixtures() was not called.\n"
                "This probably means that you overrode init_class_fixtures"
                " without calling super()."
            )
        except:
            cls.tearDownClass()
            raise

    @classmethod
    def init_class_fixtures(cls):
        """
        Override and implement this classmethod to register resources that
        should be created and/or torn down on a per-class basis.
        Subclass implementations of this should always invoke this with super()
        to ensure that fixture mixins work properly.
        """
        if cls._in_setup:
            raise ValueError(
                'Called init_class_fixtures from init_instance_fixtures.'
                'Did you write super(..., self).init_class_fixtures() instead'
                ' of super(..., self).init_instance_fixtures()?',
            )
        cls._base_init_fixtures_was_called = True

    @final
    @classmethod
    def tearDownClass(cls):
        # We need to get this before it's deleted by the loop.
        stack = cls._class_teardown_stack
        for name in set(vars(cls)) - cls._static_class_attributes:
            # Remove all of the attributes that were added after the class was
            # constructed. This cleans up any large test data that is class
            # scoped while still allowing subclasses to access class level
            # attributes.
            delattr(cls, name)
        stack.close()

    @final
    @classmethod
    def enter_class_context(cls, context_manager):
        """
        Enter a context manager to be exited during the tearDownClass
        """
        if cls._in_setup:
            raise ValueError(
                'Attempted to enter a class context in init_instance_fixtures.'
                '\nDid you mean to call enter_instance_context?',
            )
        return cls._class_teardown_stack.enter_context(context_manager)

    @final
    @classmethod
    def add_class_callback(cls, callback, *args, **kwargs):
        """
        Register a callback to be executed during tearDownClass.
        Parameters
        ----------
        callback : callable
            The callback to invoke at the end of the test suite.
        """
        if cls._in_setup:
            raise ValueError(
                'Attempted to add a class callback in init_instance_fixtures.'
                '\nDid you mean to call add_instance_callback?',
            )
        return cls._class_teardown_stack.callback(callback, *args, **kwargs)

    @final
    def setUp(self):
        type(self)._in_setup = True
        self._pre_setup_attrs = set(vars(self))
        self._instance_teardown_stack = ExitStack()
        try:
            self._init_instance_fixtures_was_called = False
            self.init_instance_fixtures()
            assert self._init_instance_fixtures_was_called, (
                "CatalystTestCase.init_instance_fixtures() was not"
                " called.\n"
                "This probably means that you overrode"
                " init_instance_fixtures without calling super()."
            )
        except:
            self.tearDown()
            raise
        finally:
            type(self)._in_setup = False

    def init_instance_fixtures(self):
        self._init_instance_fixtures_was_called = True

    @final
    def tearDown(self):
        # We need to get this before it's deleted by the loop.
        stack = self._instance_teardown_stack
        for attr in set(vars(self)) - self._pre_setup_attrs:
            delattr(self, attr)
        stack.close()

    @final
    def enter_instance_context(self, context_manager):
        """
        Enter a context manager that should be exited during tearDown.
        """
        return self._instance_teardown_stack.enter_context(context_manager)

    @final
    def add_instance_callback(self, callback):
        """
        Register a callback to be executed during tearDown.
        Parameters
        ----------
        callback : callable
            The callback to invoke at the end of each test.
        """
        return self._instance_teardown_stack.callback(callback)


class TestMarketplace(WithLogger, CatalystTestCase):
    def _test_list(self):
        marketplace = Marketplace()
        marketplace.list()
        pass

    def _test_register(self):
        marketplace = Marketplace()
        marketplace.register()
        pass

    def _test_subscribe(self):
        marketplace = Marketplace()
        marketplace.subscribe('enigma_marketcap')
        pass

    def _test_ingest(self):
        marketplace = Marketplace()
        ds_def = marketplace.ingest('marketcap')
        print(ds_def)
        pass

    def _test_publish(self):
        marketplace = Marketplace()
        datadir = '/Users/fredfortier/Downloads/marketcap_test_single'
        marketplace.publish('marketcap1234', datadir, False)
        pass

    def _test_clean(self):
        marketplace = Marketplace()
        marketplace.clean('marketcap')
        pass

mar = TestMarketplace()
mar._test_subscribe()