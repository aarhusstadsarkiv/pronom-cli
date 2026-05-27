import argparse

import httpx
from sqlalchemy.orm import Session

from pronom_cli import database, logger
from pronom_cli.repository.manager import RepositoryManager
from pronom_cli.updater import update
from pronom_cli.utils import Filter, console, print_compact_list


def parse_filter(value: str) -> list[Filter]:
    """Parses a comma-separated string of filter names into a list of Filter enum members."""
    try:
        return [Filter(val) for val in value.split(",")]
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid filter: {value}") from e


def main():
    database.initialize_database()

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--filter",
        type=parse_filter,
        default=[
            Filter.FILEINFO,
            Filter.FILEFORMATS,
            Filter.PRONOM,
            Filter.FILEXT,
            Filter.FILEPROINFO,
        ],
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
        update()
        return

    is_extension = query.startswith(".")

    http_session = httpx.Client()

    with Session(database.get_engine()) as db_session:
        repository = RepositoryManager(db_session, http_session, args.filter)

        if is_extension:
            result = repository.get_from_extension(query, args.limit)
        else:
            result = repository.get_from_identifier(query)

        db_session.commit()

        if not result:
            logger.error(f"no results for {query}")
            http_session.close()
            return

        if isinstance(result, list):
            if args.detailed:
                sep = "[white]----------------------------------------------------[/white]"
                for format in result:
                    console.print(sep)
                    format.print(args.detailed)
                console.print(sep)
            else:
                print_compact_list(result)
        else:
            result.print(args.detailed)

    http_session.close()


if __name__ == "__main__":
    main()
