import logging

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

logging.getLogger('aiohttp.access').setLevel(logging.WARNING)

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    Returns:
        A configured logger instance
    """
    return logging.getLogger(name)
