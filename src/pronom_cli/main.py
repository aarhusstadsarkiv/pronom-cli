import argparse

from sqlalchemy.orm import Session

from pronom_cli import database, service
from pronom_cli.repository.manager import RepositoryManager
from pronom_cli.utils import Filter


def parse_filter(value: str) -> list[Filter]:
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

    engine = database.get_engine()

    with Session(engine) as session:
        repository = RepositoryManager(session, args.filter)
        format = repository.get_from_identifier(query)
        print(format)

    # if query == "update":
    #     update()
    #     return

    # is_extension = args.query.startswith(".")

    # if is_extension:
    #     res = repository.get_from_extension(query, limit=args.limit)

    #     if not res:
    #         logger.error(f"no results for {query}")
    #         service.session.close()
    #         return

    #     for result in res:
    #         print(result.__dict__)
    #     # if args.detailed:
    #     #     console.print(
    #     #         "[white]----------------------------------------------------[/white]"
    #     #     )
    #     #     for result in res:
    #     #         result.print(args.detailed)
    #     #         console.print(
    #     #             "[white]----------------------------------------------------[/white]"
    #     #         )
    #     # else:
    #     #     print_compact_list(res)

    # else:
    #     res = repository.get_from_identifier(query)

    #     if not res:
    #         logger.error(f"no results for {query}")
    #         service.session.close()
    #         return

    #     print(res.__dict__)
    #     # res.print(args.detailed)

    service.session.close()


if __name__ == "__main__":
    main()
