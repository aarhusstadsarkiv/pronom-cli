from abc import ABC, abstractmethod
from typing import Any


class ActionABC(ABC):
    @classmethod
    @abstractmethod
    def parse(cls, data: dict[str, Any]) -> "ActionABC":
        pass

    @abstractmethod
    def print(self) -> str:
        pass


class IgnoreAction(ActionABC):
    def __init__(self) -> None:
        self.template: str = ""
        self.reason: str = ""

    @classmethod
    def parse(cls, data: dict[str, Any]) -> "IgnoreAction":
        section = data["ignore"]

        c = cls()
        c.template = section["template"]
        c.reason = section.get("reason", "No reason provided")

        return c

    def print(self) -> str:
        details: list[str] = []
        if self.template:
            details.append(f"template: {self.template}")
        if self.reason:
            details.append(f"reason: {self.reason}")

        if not details:
            return "ignore"

        return "ignore\n" + "\n".join(f"  • {line}" for line in details)


class ExtractAction(ActionABC):
    def __init__(self) -> None:
        self.tool = ""
        self.extension = ""
        self.on_success: ActionABC | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> "ExtractAction":
        section: dict[str, Any] = data["extract"]

        c = cls()
        c.tool = section["tool"]
        c.extension = section["extension"]

        if "on_success" in section:
            c.on_success = parse_action(data, _action=section["on_success"])

        return c

    def print(self) -> str:
        details: list[str] = []
        if self.tool:
            details.append(f"tool: {self.tool}")
        if self.extension:
            details.append(f"extension: {self.extension}")
        if self.on_success is not None:
            nested_lines = self.on_success.print().splitlines()
            if nested_lines:
                details.append(f"on success: {nested_lines[0]}")
                for line in nested_lines[1:]:
                    details.append(f"  {line}")
            else:
                details.append("on success: -")

        if not details:
            return "extract"

        return "extract\n" + "\n".join(f"{line}" for line in details)


class ManualAction(ActionABC):
    def __init__(self) -> None:
        self.reason = ""
        self.process = ""

    @classmethod
    def parse(cls, data: dict[str, Any]) -> "ManualAction":
        section = data["manual"]

        c = cls()
        c.reason = section["reason"]
        c.process = section["process"]

        return c

    def print(self) -> str:
        details: list[str] = []
        if self.reason:
            details.append(f"reason: {self.reason}")
        if self.process:
            details.append(f"process: {self.process}")

        if not details:
            return "manual"

        return "manual\n" + "\n".join(f"  • {line}" for line in details)


class ConvertAction(ActionABC):
    def __init__(self) -> None:
        self.tool = ""
        self.output = ""
        self.options = ""

    @classmethod
    def parse(cls, data: dict[str, Any]) -> "ConvertAction":
        section: dict[str, Any] = data["convert"]

        c = cls()
        c.tool = section["tool"]
        c.output = section.get("output", "")
        c.options = section.get("options", "")

        return c

    def print(self) -> str:
        details: list[str] = []
        if self.tool:
            details.append(f"tool: {self.tool}")
        if self.output:
            details.append(f"output: {self.output}")
        if self.options:
            details.append(f"options: {self.options}")

        if not details:
            return "convert"

        return "convert\n" + "\n".join(f"  • {line}" for line in details)


# not used in fileformats.yml, but defined as a valid action in fileformats-schema.
class TemplateAction(ActionABC):
    @classmethod
    def parse(cls, data: dict[str, Any]) -> "TemplateAction":
        return cls()

    def print(self) -> str:
        return "template"


def parse_action(data: dict[str, Any], _action: str = "") -> ActionABC | None:
    """
    Parses and constructs an action object based on the provided action type and data.

    This function checks the action type from the input dictionary or uses the specified
    action type if provided explicitly. Based on the action type, it delegates the data
    to the appropriate action parsing method to create and return the corresponding
    action object. If the action type is unrecognized, None is returned.

    Arguments:
        data (dict[str, Any]): A dictionary containing the data required to instantiate
            an action object. It should include the "action" key specifying the type of
            the action unless an explicit action type is provided.
        _action (str, optional): The explicit action type to override the action type
            specified in the data dictionary. Defaults to an empty string.

    Returns:
        ActionABC | None: An instance of the corresponding action class derived from
            ActionABC if the action type is valid; otherwise, None.
    """
    actions = {
        "ignore": IgnoreAction.parse,
        "extract": ExtractAction.parse,
        "manual": ManualAction.parse,
        "convert": ConvertAction.parse,
        "template": TemplateAction.parse,
    }

    # if an action already has been given, we don't need to look at the action key
    # used for cases, such as "on_success".
    if _action:
        return actions[_action](data)

    if (action := data["action"]) not in actions:
        return

    return actions[action](data)
