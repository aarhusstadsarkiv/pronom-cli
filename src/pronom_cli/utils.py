from typing import TYPE_CHECKING, Callable, Union
from xml.etree.ElementTree import Element, ElementTree

if TYPE_CHECKING:
    from pronom_cli.models.entry import Entry


def find_xml(
    root: Union["ElementTree[Element[str]]", "Element[str]"],
    string: str,
    default: str = "",
) -> str:
    """
    Finds a text value within the given XML element tree or element using the provided string query.

    Parameters:
        root: Union[ElementTree[Element[str]], Element[str]]
            The XML element tree or XML element to be searched.

        string: str
            The query string specifying the child element to search for.

        default: str, optional
            The default value to return if the queried element or its text is not found
            or if its text is empty. Defaults to an empty string.

    Returns:
        str:
            The stripped text content of the found element, or the default value if no
            valid content is found.
    """
    value = root.find(string)
    if value is None or value.text is None:
        return default

    text = value.text.strip()
    if not text:
        return default

    return text


def merge_unique(
    list_a: list["Entry"] | None,
    list_b: list["Entry"] | None,
    key: Callable[["Entry"], object],
) -> list["Entry"]:
    if not list_b and list_a:
        return list_a

    if not list_a and list_b:
        return list_b

    seen: dict[object, Entry] = {}

    for item in list_a + list_b:  # type: ignore
        k = key(item)
        if k not in seen:
            seen[k] = item

    return list(seen.values())
