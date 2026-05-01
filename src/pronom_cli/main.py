import asyncio
import sys

import aiohttp

from pronom_cli import config, logger
from pronom_cli.models.entry import Entry
from pronom_cli.repository.fileformats import FileFormatsRepository
from pronom_cli.repository.fileinfo import FileInfoRepository
from pronom_cli.repository.manager import RepositoryManager
from pronom_cli.repository.pronom import PronomRepository
from pronom_cli.updater import update


def print_help() -> None:
    print("Usage: pronom [OPTIONS] <query> | update")
    print()

    print("Options")
    print(
        "  --all              displays all metadata (byte sequences, disclosure and more)"
    )
    print("  --update-cache     updates cache")
    print()

    print("Query types (auto-detected):")
    print("  PUID               fmt/128, x-fmt/1")
    print("  Extension          .pdf, .docx")
    print()

    print("Commands:")
    print("  update             Update local PRONOM repository")
    print()


def parse_args() -> str | None:
    """
    Parses command-line arguments and processes options.

    This function reads arguments provided through the command line input via sys.argv
    and parses them to extract a single positional argument and to configure global
    flags as specified in the configuration. If no argument is provided, or if an
    unrecognized option is encountered, the function will log an error and display
    help instructions.

    Returns the query
    """
    if len(sys.argv) < 2:
        logger.error("missing argument.")
        print_help()
        return

    pos = 1
    while pos < len(sys.argv):
        # option, so we'll move one arg position
        if sys.argv[pos].startswith("--"):
            option = sys.argv[pos].removeprefix("--")

            if option not in config.flags:
                logger.error(f"option {option} doesn't exist")
                print_help()
                pos += 1
                return

            config.flags[option] = True
            pos += 1
            continue

        return sys.argv[pos]


async def main_async():

    query = parse_args()

    if not query:
        return

    if query == "update":
        await update()
        return

    config.session = aiohttp.ClientSession()

    pronom, fileformats, fileinfo = await asyncio.gather(
        PronomRepository.load(),
        FileFormatsRepository.load(),
        FileInfoRepository.load(),
    )

    repository = RepositoryManager(pronom, fileformats, fileinfo)

    is_extension = query.startswith(".")
    is_puid = query.split("/")[0] in ("aca-fmt", "x-fmt", "fmt")
    if is_extension:
        res = await repository.get_from_extension(query)
    elif is_puid:
        res = await repository.get_from_puid(query)
    else:
        res = None

    if not res:
        logger.error(f"no results for {query}")
        return

    if isinstance(res, list):
        Entry.print_compact_list(res)
    elif isinstance(res, Entry):
        res.print()
    else:
        logger.error("unexpected error")

    await config.session.close()


# uvx expects a sync function, therefore we wrap the asyncronous main function in a sync main.
def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
