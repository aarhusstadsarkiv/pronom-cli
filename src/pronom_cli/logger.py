RESET = "\033[0m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"


def _log(level: str, color: str, message: str) -> None:
    print(f"{color}{level}{RESET}: {message}")


def error(message: str) -> None:
    _log("error", RED, message)


def info(message: str) -> None:
    _log("info", CYAN, message)


def warn(message: str) -> None:
    _log("warn", YELLOW, message)
