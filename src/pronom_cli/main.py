import argparse
import asyncio

import aiohttp

from pronom_cli import database, logger, service
from pronom_cli.repository.fileformats import FileFormatsRepository
from pronom_cli.repository.fileinfo import FileInfoRepository
from pronom_cli.repository.filext import FilextRepository
from pronom_cli.repository.manager import RepositoryManager
from pronom_cli.repository.masterformats import MasterFormatsRepository
from pronom_cli.repository.pronom import PronomRepository
from pronom_cli.updater import update
from pronom_cli.utils import Filter, console, print_compact_list


def parse_filter(value: str) -> list[Filter]:
    try:
        return [Filter(val) for val in value.split(",")]
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid filter: {value}") from e


async def main_async():
    database.initialize_database()

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--filter",
        type=parse_filter,
        help="Filter what repositories you want data from",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Include extended metadata and byte sequence output.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit the number of rows when fetching extensions",
    )
    parser.add_argument("query")

    args = parser.parse_args()
    query = args.query

    if query == "update":
        await update()
        return

    service.session = aiohttp.ClientSession()

    pronom, fileformats, fileinfo, filext, masterformats = await asyncio.gather(
        PronomRepository.load(),
        FileFormatsRepository.load(),
        FileInfoRepository.load(),
        FilextRepository.load(),
        MasterFormatsRepository.load(),
    )

    repository = RepositoryManager(
        pronom, fileformats, fileinfo, filext, masterformats, filters=args.filter
    )

    is_extension = args.query.startswith(".")
    is_puid = query.split("/")[0] in ("aca-fmt", "x-fmt", "fmt")

    if is_extension:
        res = await repository.get_from_extension(query, limit=args.limit)

        if not res:
            logger.error(f"no results for {query}")
            await service.session.close()
            return

        if args.detailed:
            console.print(
                "[white]----------------------------------------------------[/white]"
            )
            for result in res:
                result.print(args.detailed)
                console.print(
                    "[white]----------------------------------------------------[/white]"
                )
        else:
            print_compact_list(res)

    elif is_puid:
        res = await repository.get_from_puid(query)

        if not res:
            logger.error(f"no results for {query}")
            await service.session.close()
            return

        res.print(args.detailed)
    else:
        logger.error("unexpected error")

    await service.session.close()


# uvx expects a sync function, therefore we wrap the asyncronous main function in a sync main.
def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
