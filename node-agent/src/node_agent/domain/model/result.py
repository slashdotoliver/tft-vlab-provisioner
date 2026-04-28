from typing import Any, Callable

from returns.result import Failure as ReturnsFailure
from returns.result import Result as ReturnsResult
from returns.result import Success as ReturnsSuccess


class Result[T, E]:
    """
    This class implements the Result pattern to handle operations that can either
    succeed or fail, preventing exceptions from being used for regular control flow.
    """

    def __init__(self, inner: ReturnsResult[T, E]):
        self._inner: ReturnsResult[T, E] = inner

    @classmethod
    def success(cls, value: T) -> Success[T]:
        """Creates a successful Result containing a value.
        Args:
            value: The data or object resulting from a successful operation.
        Returns:
            A Success instance encapsulating the provided value.
        """
        return Success(value)

    @classmethod
    def failure(cls, error: E) -> Failure[E]:
        """Creates a failed Result containing an error.
        Args:
            error: The exception, string, or domain error explaining the failure.
        Returns:
            A Failure instance encapsulating the provided error.
        """
        return Failure(error)

    def on_success(self, func: Callable[[T], Any]) -> Result[T, E]:
        """Executes a function if the result is a Success.
        The value and internal state remain unchanged.
        Args:
            func: A callable that takes the current value. Its return value is ignored.
        Returns:
            The same original Result instance.
        """
        if self.is_success():
            func(self._inner.unwrap())
        return self

    def on_failure(self, func: Callable[[E], Any]) -> Result[T, E]:
        """Executes a function if the result is a Failure.
        The error and internal state remain unchanged.
        Args:
            func: A callable that takes the current error. Its return value is ignored.
        Returns:
            The same original Result instance.
        """
        if self.is_failure():
            func(self._inner.failure())
        return self

    def map[U](self, func: Callable[[T], U]) -> Result[U, E]:
        """Applies a function to the encapsulated value if the result is a Success.
        If the result is a Failure, the error is passed through unchanged.
        Args:
            func: A callable that takes the current value type (T) and returns a new type (U).
        Returns:
            A new Result object containing either the mapped value or the original error.
        """
        return Result(self._inner.map(func))

    def flat_map[U](self, func: Callable[[T], Result[U, E]]) -> Result[U, E]:
        """Applies a function to the encapsulated value if the result is a Success,
        where the function itself returns a new Result.
        Args:
            func: A callable that takes the current value type (T) and returns
                  a new Result[U, E].
        Returns:
            A new Result object representing the chained operation's outcome.
        """
        return Result(self._inner.bind(lambda value: func(value)._inner))

    def map_error[X](self, func: Callable[[E], X]) -> Result[T, X]:
        """Applies a function to the encapsulated error if the result is a Failure.
        If the result is a Success, the value is passed through unchanged.
        Args:
            func: A callable that takes the current error type (E) and returns a new type (X).
        Returns:
            A new Result object containing either the mapped error or the original value.
        """
        return Result(self._inner.alt(func))

    def flat_map_error[X](self, func: Callable[[E], Result[T, X]]) -> Result[T, X]:
        """Applies a function to the encapsulated error if the result is a Failure.
        If the result is a Success, the value is passed through unchanged.
        Args:
            func: A callable that takes the current error type (E) and returns
                  a new Result (either recovering to Success or passing a Failure).
        Returns:
            A new Result object representing the outcome of the recovery attempt.
        """
        return Result(self._inner.lash(lambda error: func(error)._inner))

    def flat_tap(self, func: Callable[[T], Result[Any, E]]) -> Result[T, E]:
        """Executes a function returning a Result, ignoring its success value.
        If the function returns a Success, the original Success value is preserved.
        If it returns a Failure, the execution short-circuits and the error is returned.
        Args:
            func: A callable that takes the current value and returns a new Result.
        Returns:
            The original Result instance if the function succeeded, or a Failure
            if the function failed.
        """
        return self.flat_map(lambda val: func(val).map(lambda _: val))

    def value_or(self, default_value: T) -> T:
        """Unwraps the encapsulated value if successful, or returns a fallback value.
        Args:
            default_value: The value to return if this instance is a Failure.
        Returns:
            The encapsulated value (T) if Success, otherwise the default_value (T).
        """
        return self._inner.value_or(default_value)

    def is_success(self) -> bool:
        """Checks if the result represents a successful operation.
        Returns:
            True if the operation was successful, False otherwise.
        """
        return isinstance(self._inner, ReturnsSuccess)

    def is_failure(self) -> bool:
        """Checks if the result represents a failed operation.
        Returns:
            True if the operation failed, False otherwise.
        """
        return not self.is_success()

    def get_error(self) -> E | None:
        """Retrieves the underlying error if the operation failed.
        Returns:
            The encapsulated error (E) if this is a Failure, or None if it is a Success.
        """
        if not self.is_success():
            return self._inner.failure()
        return None


class Success[T](Result[T, Any]):
    """Represents a successful outcome."""

    def __init__(self, value: T):
        super().__init__(ReturnsSuccess(value))


class Failure[E](Result[Any, E]):
    """Represents a failure outcome."""

    def __init__(self, error: E):
        super().__init__(ReturnsFailure(error))
