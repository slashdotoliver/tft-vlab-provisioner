from typing import Any, Callable

from node_agent.domain.model.environment_models import Result


def attempt[T, E](
    func: Callable[[], T],
    exceptions: tuple[type[Exception], ...] | None = None,
    exception_mapper: Callable[[Exception], E] | None = None,
) -> Result[T, E]:
    """Executes a callable and safely wraps its execution in a Result object.
    It attempts to run the provided function. If successful, it returns a Success
    containing the value. If it raises one of the targeted exceptions, it catches it
    and returns a Failure. The exceptions to catch can be explicitly passed or
    inferred if the function is decorated with @raises.
    Args:
        func: The callable to execute. It must take no arguments.
        exceptions: A tuple of exception types to catch. If None, the function will
                    look for the `__raises__` attribute injected by the @raises decorator.
        exception_mapper: An optional callable to transform the caught Exception into
                          a specific error type (E) before wrapping it in a Failure.
    Returns:
        A Result[T, E] representing either a successful execution (Success) or
        a caught exception (Failure).
    Raises:
        TypeError: If no exceptions are explicitly provided and the target function
                   is not decorated with @raises.
    """
    target_exceptions: tuple[type[Exception], ...] = exceptions or getattr(func, "__raises__", None)
    try:
        return Result.success(func())
    except target_exceptions as e:
        if exception_mapper is None:
            return Result.failure(e)
        return Result.failure(exception_mapper(e))


def raises(*exceptions: type[Exception]):
    """Decorator to register the exceptions a function is expected to raise.
    This stores the provided exception types in a `__raises__` attribute on the
    function, allowing utilities like `attempt` to dynamically know which
    exceptions to catch without requiring explicit arguments.
    Args:
        *exceptions: A variable number of exception classes that the function might raise.
    Returns:
        The decorated function with the `__raises__` metadata attached.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        func.__raises__ = exceptions
        return func

    return decorator
