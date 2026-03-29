"""
工作流相关杂项工具。
"""

import time
from collections.abc import Callable
from typing import Any, TypeVar

ASpecificRet = TypeVar("ASpecificRet")


def wait_retry(
    retry_n: int = 3, sleep_time: int = 1, transform_args_fn: Callable[[tuple, dict], tuple[tuple, dict]] | None = None
) -> Callable[[Callable[..., ASpecificRet]], Callable[..., ASpecificRet]]:
    """装饰器：失败时休眠后重试，最多 retry_n 次；可选在每轮前用 transform_args_fn 改写参数。"""

    assert retry_n > 0, "retry_n should be greater than 0"

    def decorator(f: Callable[..., ASpecificRet]) -> Callable[..., ASpecificRet]:
        def wrapper(*args: Any, **kwargs: Any) -> ASpecificRet:
            for i in range(retry_n + 1):
                try:
                    return f(*args, **kwargs)
                except Exception as e:
                    print(f"Error: {e}")
                    time.sleep(sleep_time)
                    if i == retry_n:
                        raise
                    if transform_args_fn is not None:
                        args, kwargs = transform_args_fn(args, kwargs)
            else:
                return f(*args, **kwargs)

        return wrapper

    return decorator
