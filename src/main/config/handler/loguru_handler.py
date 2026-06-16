import logging
import sys

from loguru import logger


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def configure_loguru_for_worker() -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO",
        backtrace=True,
        diagnose=False,
        colorize=False,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {process.name}:{thread.name} | {message}",
    )
    
    intercept_handler = InterceptHandler()
    logging.basicConfig(handlers=[intercept_handler], level=logging.INFO, force=True)

    for logger_name in ("celery", "celery.app.trace", "celery.worker", "kombu", "asyncio"):
        std_logger = logging.getLogger(logger_name)
        std_logger.handlers = [intercept_handler]
        std_logger.propagate = False
        std_logger.setLevel(logging.INFO)
