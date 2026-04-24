import logging
import structlog


def configure_logging(level: str | None = None) -> None:
    if level is None:
        try:
            from src.config import settings
            level = "DEBUG" if settings.debug else "INFO"
        except Exception:
            level = "INFO"

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
