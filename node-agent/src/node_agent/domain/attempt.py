from typing import Callable

from node_agent.domain.model.environment_models import Result


def attempt[T, E](
    func: Callable[[], T],
    exceptions: tuple[type[Exception], ...],
    exception_mapper: Callable[[Exception], E] | None = None,
) -> Result[T, E]:
    try:
        return Result.success(func())
    except exceptions as e:
        if exception_mapper is None:
            return Result.failure(e)
        return Result.failure(exception_mapper(e))
