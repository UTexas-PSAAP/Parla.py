"""
Parla supports simple task parallelism.

.. testsetup::

    T0 = None
    code = None

"""

from numba import cfunc, jit
import threading
from contextlib import contextmanager
from collections import namedtuple

class TaskID:
    def __init__(self, id):
        self._id = id
        self.task = None

    @property
    def id(self):
        return self._id

class TaskSpace:
    """A collection of tasks with IDs.

    A `TaskSpace` can be indexed using any hashable values and any
    number of "dimensions" (indicies). If a dimension is indexed with
    numbers then that dimension can be sliced.

    >>> T = TaskSpace()
    ... for i in range(10):
    ...     @spawn(T[i])(T[0:i-1])
    ...     def t():
    ...         code

    This will produce a series of tasks where each depends on all previous tasks.
    """

    def __init__(self):
        self._data = {}

    def __getitem__(self, index):
        if not hasattr(index, "__iter__") and not isinstance(index, slice):
            index = (index,)
        ret = []
        def traverse(prefix, index):
            if len(index) > 0:
                i, *rest = index
                if hasattr(i, "__iter__"):
                    for v in i:
                        traverse(prefix + (v,), rest)
                else:
                    traverse(prefix + (i,), rest)
            else:
                ret.append(self._data.setdefault(prefix, TaskID(prefix)))
        traverse((), index)
        return ret


class _TaskLocals(threading.local):
    @property
    def ctx(self):
        return getattr(self, "_ctx", None)
    @ctx.setter
    def ctx(self, v):
        self._ctx = v

_task_locals = _TaskLocals()


def spawn(taskid, **kwds):
    """@spawn(taskid)(\*dependencies)

    Execute the body of the function as a new task. The task may start
    executing immediately, so it may execute in parallel with any
    following code.

    >>> @spawn(T1)(T0) # Create task with ID T1 and dependency on T0
    ... def t():
    ...     code

    :param taskid: the ID of the task in a `TaskSpace` or None if the task does not have an ID.
    :param dependencies: any number of dependency arguments which may be tasks, ids, or iterables of tasks or ids.

    The declared task (`t` above) can be used as a dependency for later tasks (in place of the tasks ID).
    This same value is conceptually stored into the task space used in `taskid`.

    :see: `Blocked Cholesky Example <https://github.com/UTexas-PSAAP/Parla.py/blob/master/examples/blocked_cholesky.py#L37>`_

    """
    def deps(*dependencies):
        def decorator(body):
            # Apply numba to the body function
            body = jit("void()", **kwds)(body)

            # Build the callback to be called directly from the Parla runtime
            @cfunc("void(voidptr, pyobject)")
            def callback(ctx, body):
                old_ctx = _tasks_local.ctx
                _tasks_local.ctx = ctx
                body()
                _tasks_local.ctx = old_ctx

            # Compute the flat dependency set (including unwrapping TaskID objects)
            deps = []
            for ds in dependencies:
                if not hasattr(ds, "__iter__"):
                    ds = (ds,)
                for d in ds:
                    if hasattr(d, "task"):
                        d = d.task
                    assert isinstance(d, Task)
                    deps.append(d)

            # Spawn the task via the Parla runtime API
            if _tasks_local.ctx:
                task = create_task(_tasks_local.ctx, callback, body, deps)
            else:
                # BUG: This function MUST take deps and must return a task
                run_generation_task(callback, body)

            # Store the task object in it's ID object
            taskid.task = task

            # Return the task object
            return task
        return decorator
    return deps


# @contextmanager
# def finish():
#     """
#     Execute the body of the `with` normally and then perform a barrier applying to all tasks created.
#     This block has the similar semantics to the ``sync`` in Cilk.

#     >>> with finish():
#     ...     code

#     """
#     yield
