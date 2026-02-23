"""
Peek is a programming toolkit for building microservices in python.
It has very useful interface or service to develop application.

Modules:
- peek.app: Application core (BaseApp, Command, Plugin, HookManager, Provider)
- peek.config: Configuration loader (YAML + env + Pydantic)
- peek.database: Database connectors (MySQL, Redis)
- peek.logs: Logging framework with rotation support
- peek.net.webserver: Web server framework (FastAPI-based)
- peek.net.grpc: gRPC server and client
- peek.opentelemetry: OpenTelemetry integration (Tracer, Metric)
- peek.encoding: Encoding utilities
- peek.time: Time utilities (backoff, wait, parse_duration)
- peek.uuid: UUID utilities
"""

from peek.__version__ import __version__

__all__ = ["__version__"]
