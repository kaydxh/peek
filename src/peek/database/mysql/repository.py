#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Repository 基类 + 短事务装饰器

解决问题：
    业务侧 Repository 通常持有 ``self.session`` 字段（构造时注入），
    但在 **后台长任务** 场景下：
      - 评测、批处理、Celery worker 跑数分钟到数十分钟
      - 单一 session 持有的 MySQL 连接会被服务端 ``wait_timeout`` 静默关闭
      - 后续调用就报 ``ValueError: read of closed file``

短事务模式：
    每次 repo 方法调用都从 session_factory 申请一个新 session，
    依赖 SQLAlchemy 的 ``pool_pre_ping=True`` 在 checkout 时探活坏连接，
    自动重建后无副作用透明返回。

提供两种使用方式（业务可任选其一）：

1. **继承 BaseRepository**：构造时传 ``session_factory``，业务方法用
   ``self.session_scope()`` 包裹 DB 操作；适合新写的 repository
2. **使用 transactional 装饰器**：业务方法第一个参数仍是 ``self``，
   装饰器会自动建立短事务并把 session 注入 ``self.session``；适合
   对已有 ``self.session = session`` 模式做增量改造

典型用法（继承 BaseRepository）::

    class EvalRepository(BaseRepository):
        def get_run(self, run_id: int):
            with self.session_scope() as db:
                return db.query(EvalRun).filter(EvalRun.id == run_id).first()

典型用法（装饰器，渐进式改造）::

    class EvalRepository:
        def __init__(self, session_factory):
            self._session_factory = session_factory
            self.session = None  # 由装饰器在调用时注入

        @transactional()
        def update_run_status(self, run_id, status):
            run = self.session.query(EvalRun).filter(EvalRun.id == run_id).first()
            run.status = status

注意：
    - 装饰器 / context manager 退出时自动 commit（异常自动 rollback），
      调用方**不需要也不应该**再手动 ``self.session.commit()``
    - 短事务**不适合多个 repo 方法需要原子性**的复合场景，那种情况
      上层应自己开一个 ``session_scope`` 然后传同一个 session 进去
"""

from __future__ import annotations

import functools
import logging
from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional

logger = logging.getLogger(__name__)


# ============================================================
# BaseRepository
# ============================================================


class BaseRepository:
    """Repository 基类。

    构造时只接收 ``session_factory``（即 ``sessionmaker`` 实例），
    每次 DB 操作通过 :meth:`session_scope` 取得一个**短生命周期** session。
    """

    def __init__(self, session_factory: Callable[[], Any]) -> None:
        if session_factory is None:
            raise ValueError("session_factory must not be None")
        self._session_factory = session_factory

    @contextmanager
    def session_scope(self, commit: bool = True) -> Generator[Any, None, None]:
        """打开一个短生命周期 session 上下文。

        - 正常退出：若 ``commit=True`` 自动 commit
        - 抛异常：自动 rollback 后向外重抛
        - 退出时无条件 close 释放连接回连接池

        Args:
            commit: 上下文正常退出时是否自动 commit（默认 True）

        Yields:
            SQLAlchemy Session 实例
        """
        session = self._session_factory()
        try:
            yield session
            if commit:
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# ============================================================
# transactional 装饰器
# ============================================================


def transactional(
    commit: bool = True,
    session_attr: str = "session",
    factory_attr: str = "_session_factory",
) -> Callable:
    """把方法包装成短事务调用。

    被装饰方法执行前：
        - 从 ``self.<factory_attr>`` 取出 session_factory，建一个新 session
        - 把 session 临时赋值给 ``self.<session_attr>``，方法体内可直接使用
    方法返回 / 抛异常时：
        - 正常返回 → 自动 commit（除非 ``commit=False``）
        - 抛异常 → 自动 rollback
        - 无条件 close + 把 ``self.<session_attr>`` 还原为 None

    Args:
        commit: 正常返回时是否自动 commit（默认 True）
        session_attr: 注入到 self 上的 session 字段名（默认 ``session``）
        factory_attr: self 上 session factory 字段名（默认 ``_session_factory``）

    Returns:
        装饰器
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            factory: Optional[Callable[[], Any]] = getattr(self, factory_attr, None)
            if factory is None:
                raise RuntimeError(
                    f"@transactional requires self.{factory_attr} to be a session factory"
                )

            session = factory()
            old_session = getattr(self, session_attr, None)
            setattr(self, session_attr, session)
            try:
                result = func(self, *args, **kwargs)
                if commit:
                    session.commit()
                return result
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
                setattr(self, session_attr, old_session)

        return wrapper

    return decorator


__all__ = [
    "BaseRepository",
    "transactional",
]
