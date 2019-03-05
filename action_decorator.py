import functools
import os

import attr
from backports import tempfile


@attr.s
class ActionDecorator(object):
    """
    Composable action decorators.

    A ActionDecorator instance is a decorator which can be applied to
    functions and methods. It performs its action *before* calling the
    decorated function. Each ActionDecorator instance has an associate
    action which is a function taking a single "context" argument.

    The intended use of ActionDecorators is for chaining together strings
    of actions needed to create a particular environment for the decorated
    function. This is particularly useful in setting up tests.

    Create and use ActionDecorators like this:

        @ActionDecorator
        def my_action(ctx):
            print("Doing my_action")

        @my_action
        def some_func(ctx):
            print("Doing some_func")

    Calling some_func() now would give the following output:

        Doing my action
        Doing some_func

    ActionDecorators have two features that make them useful over just
    chaining normal decorator functions. Firstly, they are neatly composable:
    ActionDecorator instances can be chained together using the | operator.
    This creates a new ActionDecorator which can also be used to decorate
    functions and methods: the actions for each ActionDecorator in the chain
    are performed left-to-right before calling the decorated function.

    e.g. if A, B, and C are ActionDecorator instances, then we can define
    a new ActionDecorator D with:

        D = A | B | C

        @D
        def some_func(ctx):
            # Do stuff here
            ...

    Now calling some_func() will perform A's action, then B's, then C's,
    before finally calling the original some_func().

    The second useful feature of ActionDecorators is the ability to easily
    manage state and pass it between the actions in an ActionDecorator chain.
    Each decorated action function must take a single "context" argument
    (it can be named whatever you want). This context argument is essentially
    just a placeholder: you can assign whatever you want to any attribute
    with any name. The key is that this same context object is passed along
    between each ActionDecorator in the chain, e.g.

        @ActionDecorator
        def init_x(ctx):
            ctx.x = 0

        @ActionDecorator
        def inc_x(ctx):
            ctx.x += 1

        @ActionDecorator
        def print_x(ctx):
            print(ctx.x)

        x_chain = init_x | inc_x | inc_x | print_x

        @x_chain
        def my_func():
            print "my_func"

    Calling my_func() now results in:

        1
        my_func

    Again, this *can* all be achieved with standard function decorators.
    Using ActionDecorators instead simply makes it a bit clearer to read
    and write.
    """

    action = attr.ib()
    # TODO: validate that attr is a function taking a single argument?
    post_action = attr.ib(init=False, default=None)

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            ctx = type(
                self.action.__name__ +
                '_ActionDecoratorContext',
                (),
                {})()
            self.action(ctx)
            try:
                return func(*args, **kwargs)
            finally:
                if self.post_action is not None:
                    self.post_action(ctx)

        return wrapper

    def after(self, func):
        self.post_action = func

    def __or__(self, other):
        """
        Compose two ActionDecorators.

        Takes two ActionDecorators and composes them to create a new
        ActionDecorator whose action is to call the action of the left-hand
        ActionDecorator and then call the action of the right-hand
        ActionDecorator.

        Arguments
        ---------
            other {ActionDecorator} -- The second ActionDecorator in the
                                       composition.

        Returns
        -------
            {ActionDecorator} -- A new ActionDecorator which is the
                                 left-to-right composition of these two
                                 ActionDecorators.

        """
        def then(ctx):
            self.action(ctx)
            other.action(ctx)
        then.__name__ = (
            self.action.__name__ +
            "_then_" +
            other.action.__name__)
        then = ActionDecorator(then)
        if other.post_action or self.post_action:
            def after(ctx):
                try:
                    if other.post_action is not None:
                        other.post_action(ctx)
                finally:
                    if self.post_action is not None:
                        self.post_action(ctx)
            if other.post_action is None:
                after_name = self.post_action.__name__
            else:
                after_name = other.post_action.__name__
                if self.post_action is not None:
                    after_name += ("_then_" + self.post_action.__name__)
            after.__name__ = after_name
            then.after(after)
        return then


@ActionDecorator
def mktempdir(ctx):
    ctx.orig_dir = os.getcwd()
    ctx.tmp_dir = tempfile.TemporaryDirectory()
    os.chdir(ctx.tmp_dir.name)


@mktempdir.after
def remove_tmp_dir(ctx):
    os.chdir(ctx.orig_dir)
    ctx.tmp_dir.cleanup()
