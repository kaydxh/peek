#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BaseApp - 应用程序基类

提供通用的应用程序生命周期管理：
- 信号处理（SIGINT/SIGTERM）
- 插件安装/卸载编排
- 钩子函数执行
- 优雅关闭
- CLI 命令注册

上层框架（如 tide 的 TideApp）继承此类添加特定配置和命令。
"""

import asyncio
import logging
import signal
import sys
from typing import Any, Callable, Dict, List, Optional

import click

from peek.app.command import Command, CommandContext
from peek.app.hooks import HookManager, HookType
from peek.app.plugin import Plugin, PluginManager
from peek.app.provider import Provider, get_provider

logger = logging.getLogger(__name__)


class BaseApp:
    """
    应用程序基类

    提供：
    - 应用程序生命周期管理
    - 命令行支持 (基于 click)
    - 插件加载机制
    - 钩子函数 (PostStart, PreShutdown)
    - 优雅关闭

    使用示例：
        class MyApp(BaseApp):
            def run_with_config(self, config_path: str) -> None:
                config = load_my_config(config_path)
                self.run(config)

        app = MyApp(name="my-service")
        app.cli()
    """

    def __init__(
        self,
        name: str,
        version: str = "0.1.0",
        description: str = "",
    ):
        """
        初始化应用程序

        Args:
            name: 应用名称
            version: 版本号
            description: 应用描述
        """
        self.name = name
        self.version = version
        self.description = description

        # 组件
        self._config: Optional[Any] = None
        self._provider: Provider = get_provider()
        self._plugin_manager = PluginManager()
        self._hook_manager = HookManager()

        # 命令
        self._commands: Dict[str, Command] = {}
        self._cli_group: Optional[click.Group] = None

        # 状态
        self._running = False
        self._shutdown_event: Optional[asyncio.Event] = None

        # 初始化 CLI
        self._init_cli()

    def _init_cli(self) -> None:
        """初始化 CLI"""

        @click.group(invoke_without_command=True)
        @click.version_option(version=self.version, prog_name=self.name)
        @click.pass_context
        def cli(ctx: click.Context) -> None:
            """Application CLI"""
            ctx.ensure_object(dict)
            ctx.obj["app"] = self
            if ctx.invoked_subcommand is None:
                click.echo(ctx.get_help())

        self._cli_group = cli

        # 添加默认命令
        self._add_default_commands()

    def _add_default_commands(self) -> None:
        """
        添加默认命令

        子类可以覆盖此方法添加自定义的默认命令。
        """

        @self._cli_group.command()
        @click.option(
            "--config", "-c", default="conf/config.yaml", help="配置文件路径"
        )
        @click.pass_context
        def serve(ctx: click.Context, config: str) -> None:
            """启动服务"""
            app: BaseApp = ctx.obj["app"]
            app.run_with_config(config)

        @self._cli_group.command()
        @click.pass_context
        def info(ctx: click.Context) -> None:
            """显示应用信息"""
            app: BaseApp = ctx.obj["app"]
            click.echo(f"Name: {app.name}")
            click.echo(f"Version: {app.version}")
            click.echo(f"Description: {app.description}")
            click.echo(f"Plugins: {list(app._plugin_manager._plugins.keys())}")

    def command(
        self,
        name: Optional[str] = None,
        **kwargs: Any,
    ) -> Callable:
        """
        命令装饰器

        Args:
            name: 命令名称
            **kwargs: 传递给 click.command 的参数

        Returns:
            装饰器函数
        """

        def decorator(func: Callable) -> Callable:
            cmd_name = name or func.__name__
            cmd = self._cli_group.command(name=cmd_name, **kwargs)(func)
            self._commands[cmd_name] = Command(
                name=cmd_name,
                func=func,
                description=func.__doc__ or "",
            )
            return cmd

        return decorator

    def register_plugin(self, plugin: Plugin) -> "BaseApp":
        """
        注册插件

        Args:
            plugin: 插件实例

        Returns:
            self，支持链式调用
        """
        self._plugin_manager.register(plugin)
        return self

    def register_post_start_hook(
        self,
        name: str,
        func: Callable,
        priority: int = 0,
    ) -> "BaseApp":
        """
        注册启动后钩子

        Args:
            name: 钩子名称
            func: 钩子函数
            priority: 优先级（越大越先执行）

        Returns:
            self
        """
        self._hook_manager.register(HookType.POST_START, name, func, priority)
        return self

    def register_pre_shutdown_hook(
        self,
        name: str,
        func: Callable,
        priority: int = 0,
    ) -> "BaseApp":
        """
        注册关闭前钩子

        Args:
            name: 钩子名称
            func: 钩子函数
            priority: 优先级

        Returns:
            self
        """
        self._hook_manager.register(HookType.PRE_SHUTDOWN, name, func, priority)
        return self

    def run_with_config(self, config_path: str) -> None:
        """
        使用配置文件启动应用

        子类必须覆盖此方法以实现具体的配置加载逻辑。

        Args:
            config_path: 配置文件路径
        """
        raise NotImplementedError("Subclass must implement run_with_config()")

    def run(self, config: Any) -> None:
        """
        启动应用

        Args:
            config: 应用配置
        """
        self._config = config
        self._provider.set_config(config)

        # 运行异步主循环
        try:
            asyncio.run(self._run_async())
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error("Application error: %s", e, exc_info=True)
            sys.exit(1)

    async def _run_async(self) -> None:
        """异步运行主循环"""
        self._running = True
        self._shutdown_event = asyncio.Event()

        # 设置信号处理
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(self._handle_signal(s)),
            )

        try:
            # 安装插件
            logger.info("Starting %s v%s", self.name, self.version)
            await self._install_plugins()

            # 执行启动后钩子
            await self._hook_manager.run_hooks(HookType.POST_START)

            # 等待关闭信号
            logger.info("%s is running...", self.name)
            await self._shutdown_event.wait()

        finally:
            # 执行关闭前钩子
            logger.info("Shutting down...")
            await self._hook_manager.run_hooks(HookType.PRE_SHUTDOWN)

            # 卸载插件
            await self._uninstall_plugins()

            self._running = False
            logger.info("%s stopped", self.name)

    async def _handle_signal(self, sig: signal.Signals) -> None:
        """处理系统信号"""
        logger.info("Received signal %s", sig.name)
        if self._shutdown_event:
            self._shutdown_event.set()

    def _create_command_context(self) -> CommandContext:
        """
        创建命令上下文

        子类可以覆盖此方法返回自定义的 CommandContext 子类。

        Returns:
            CommandContext 实例
        """
        return CommandContext(
            app=self,
            config=self._config,
            provider=self._provider,
        )

    async def _install_plugins(self) -> None:
        """安装所有插件"""
        ctx = self._create_command_context()
        await self._plugin_manager.install_all(ctx)

    async def _uninstall_plugins(self) -> None:
        """卸载所有插件"""
        ctx = self._create_command_context()
        await self._plugin_manager.uninstall_all(ctx)

    def cli(self) -> None:
        """运行 CLI"""
        self._cli_group()

    @property
    def config(self) -> Optional[Any]:
        """获取配置"""
        return self._config

    @property
    def provider(self) -> Provider:
        """获取 Provider"""
        return self._provider

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running
