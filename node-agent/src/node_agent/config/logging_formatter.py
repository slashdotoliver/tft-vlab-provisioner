import logging
from logging import LogRecord


class LoggingColoredFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\x1b[0;90m",
        logging.INFO: "\x1b[0;37m",
        logging.WARNING: "\x1b[1;33m",
        logging.ERROR: "\x1b[1;31m",
        logging.CRITICAL: "\x1b[1;31m",
    }
    RESET = "\x1b[0m"

    def format(self, record: LogRecord) -> str:
        log_message = super().format(record)
        log_color = self.COLORS.get(record.levelno, self.RESET)
        return f"{log_color}{log_message}{self.RESET}"


def configure_logging(level: int, custom_format: str | None = None, datefmt: str | None = None) -> None:
    base_format = (
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(module)s:%(lineno)s: %(message)s"
        if custom_format is None
        else custom_format
    )
    datefmt = "%Y-%m-%d %H:%M:%S" if datefmt is None else datefmt

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(LoggingColoredFormatter(base_format, datefmt=datefmt))
    root_logger.addHandler(console_handler)
