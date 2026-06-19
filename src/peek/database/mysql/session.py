#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MySQL Session 管理

提供同步 Session 工厂创建和 FastAPI 依赖注入支持。
上层服务只需调用 create_session_factory() 即可获得 session 工厂，
使用 get_db_session() 作为 FastAPI Depends 自动管理 session 生命周期。
"""

import logging
from contextlib import contextmanager
from typing import Any, Callable, Dict, Generator, Optional, Type, TypeVar, Union

from peek.database.mysql.config import MySQLConfig

logger = logging.getLogger(__name__)

T = TypeVar("T")


def create_session_factory(
    config: Union[MySQLConfig, Dict[str, Any]],
    engine: Optional[Any] = None,
) -> Optional[Callable]:
    """
    创建 SQLAlchemy 同步 Session 工厂

    如果未传入 engine，会自动调用 create_sync_mysql_engine 创建。
    返回的 session_factory 可直接调用生成 Session 实例。

    Args:
        config: MySQLConfig 实例或 dict 配置
        engine: 可选，已创建的 SQLAlchemy sync Engine。
                如果为 None，则自动创建。

    Returns:
        sessionmaker 实例，未启用时返回 None

    使用示例：
        session_factory = create_session_factory(config)
        if session_factory:
            session = session_factory()
            try:
                # 使用 session 进行数据库操作
                ...
            finally:
                session.close()
    """
    from sqlalchemy.orm import sessionmaker

    # 支持 dict 或 MySQLConfig
    if isinstance(config, dict):
        config = MySQLConfig.model_validate(config)

    if not config.enabled:
        logger.debug("MySQL is disabled, skipping session factory creation")
        return None

    if engine is None:
        from peek.database.mysql.engine import create_sync_mysql_engine

        engine = create_sync_mysql_engine(config)
        if engine is None:
            return None

    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info(
        "Session factory created (pool_size=%d, max_overflow=%d)",
        config.max_idle_connections,
        max(config.max_connections - config.max_idle_connections, 0),
    )
    return factory


def get_db_session(
    session_factory: Callable,
) -> Generator:
    """
    FastAPI 依赖注入：自动管理 DB session 生命周期。

    用作 FastAPI 的 Depends 依赖，自动创建 session 并在请求结束后关闭。

    Args:
        session_factory: sessionmaker 实例

    Yields:
        SQLAlchemy Session 实例

    使用示例（在 FastAPI handler 中）：
        from functools import partial
        from fastapi import Depends

        def get_session():
            return get_db_session(session_factory)

        @router.get("/items")
        def list_items(db=Depends(get_session)):
            ...
    """
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def create_repo_dependency(
    session_factory: Callable,
    repo_class: Type[T],
) -> Callable[[], Generator[T, None, None]]:
    """
    创建 Repository 的 FastAPI 依赖注入函数。

    封装了 session 创建 → repo 实例化 → session 关闭 的完整生命周期。
    上层只需一行代码即可获得可用的 Depends 依赖。

    Args:
        session_factory: sessionmaker 实例
        repo_class: Repository 类，构造函数接受 session 参数

    Returns:
        可直接用于 FastAPI Depends() 的生成器函数

    使用示例：
        from fastapi import Depends

        get_eval_repo = create_repo_dependency(session_factory, EvalRepository)

        @router.get("/evaluations")
        def list_evaluations(repo=Depends(get_eval_repo)):
            return repo.list_runs()
    """

    def _dependency() -> Generator[T, None, None]:
        session = session_factory()
        try:
            yield repo_class(session)
        finally:
            session.close()

    return _dependency


@contextmanager
def session_scope(
    session_factory: Callable,
    commit: bool = False,
) -> Generator:
    """短事务上下文管理器：每次进入打开新 session，退出自动 commit/rollback/close。

    适用场景：长耗时后台任务（如评测/批处理）中需要在不同时间点零散写库的回调，
    每个回调用一个独立的短事务 session，避免长期持有同一条连接被 MySQL 服务端
    主动断开（典型表现：``ValueError: read of closed file``）。

    与 :func:`get_db_session` 的区别：
    - ``get_db_session`` 是 FastAPI Depends 生成器，仅负责 close。
    - ``session_scope`` 是普通 ``with`` 上下文，发生异常会自动 rollback；
      ``commit=True`` 时无异常退出会自动 commit，方便业务侧少写一行。

    Args:
        session_factory: sessionmaker 实例
        commit: 退出时是否自动 commit（默认 False，由调用方在内部显式 commit）

    Yields:
        SQLAlchemy Session 实例

    使用示例（业务回调里使用短事务）::

        from peek.database.mysql.session import session_scope

        def on_progress(...):
            with session_scope(session_factory, commit=True) as db:
                repo = EvalRepository(db)
                repo.update_run_progress(run_id, progress, message)
    """
    session = session_factory()
    try:
        yield session
        if commit:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
