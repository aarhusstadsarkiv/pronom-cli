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


def init_parser() -> argparse.ArgumentParser:
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
        "--limit",
        type=int,
        default=0,
        help="Limit the number of rows when fetching extensions",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Include extended metadata and byte sequence output.",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Refreshes all expired searches and fetches new PRONOM releases, if any. This flag does not require `query` to be present.",
    )
    parser.add_argument(
        "query",
        type=str,
        nargs="?",
        help="""
        Autodetects whether the query is an extension (e.g. .pdf, .exe, .dxf) or an identifier (e.g. fmt/1, aca-fmt/2, fileinfo/4).

        If the identifier is a custom one (from fileinfo, fileproinfo or filext), the identifiers will increment, whenever a new format has been saved.
        You can not search for fileinfo/2, if there isn't any fileinfo/1 (this doesn't apply for PUIDs).
        """,
    )

    return parser


def main():
    database.initialize_database()

    parser = init_parser()
    args = parser.parse_args()

    if args.update:
        update()
        return

    if not args.query:
        parser.print_help()
        return

    query = args.query
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
            if args.verbose:
                sep = "[white]----------------------------------------------------[/white]"
                for format in result:
                    console.print(sep)
                    format.print(args.verbose)
                console.print(sep)
            else:
                print_compact_list(result)
        else:
            result.print(args.verbose)

    http_session.close()


if __name__ == "__main__":
    main()
