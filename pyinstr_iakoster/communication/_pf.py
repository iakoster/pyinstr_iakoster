import os
import re
import sqlite3
import inspect
import itertools
from pathlib import Path
from typing import Any

from tinydb.table import Document

from ._msg import FieldSetter, Message
from ..rwfile import (
    RWNoSqlJsonDatabase,
)


__all__ = [
    "PackageFormat"
]


class PackageFormatBase(object):

    FILENAME_PATTERN = re.compile("\S+.db$")
    SETTER_CLASS = FieldSetter
    MESSAGE_CLASS = Message

    def __init__(
            self,
            **settings: FieldSetter | Any
    ):
        self._message = {}
        self._setters = {}
        for k, v in settings.items():
            if isinstance(v, FieldSetter):
                self._setters[k] = v
            else:
                self._message[k] = v

        setters_diff = set(self._setters) - set(Message.REQ_FIELDS)
        if len(setters_diff):
            ValueError(
                f"not all requared setters were got: %s are missing" %
                ", ".join(setters_diff)
            )

    @property
    def msg_args(self) -> list[str]:
        return list(
            inspect.getfullargspec(
                self.MESSAGE_CLASS.__init__
            ).annotations.keys()
        )

    @property
    def message(self) -> dict[str, Any]:
        return self._message

    @property
    def setters(self) -> dict[str, FieldSetter]:
        return self._setters

    @property
    def fields_args(self) -> list[str]:
        args = ["name", "special"]
        for name, method in inspect.getmembers(
                self.SETTER_CLASS(), predicate=inspect.ismethod
        ):
            if "of <class 'pyinstr" not in repr(method):
                continue

            for par in inspect.getfullargspec(method).annotations.keys():
                if par not in args:
                    args.append(par)
        return args


class PackageFormat(PackageFormatBase):

    def write_pf(self, path: Path) -> None:

        def drop_none(dict_: dict[Any]) -> Any:
            new_dict = {}
            for k, v in dict_.items():
                if v is not None:
                    new_dict[k] = v
            return new_dict

        with RWNoSqlJsonDatabase(path) as db:
            table = db.table(self._message["format_name"])
            table.truncate()
            table.insert(Document(drop_none(self._message), doc_id=-1))

            for i_setter, (name, setter) in enumerate(self.setters.items()):
                field_pars = {"name": name}
                if setter.special is not None:
                    field_pars["special"] = setter.special
                field_pars.update(drop_none(setter.kwargs))
                table.insert(Document(field_pars, doc_id=i_setter))

    @classmethod
    def read_pf(cls, path: Path, fmt_name: str):

        with RWNoSqlJsonDatabase(path) as db:
            if fmt_name not in db.tables():
                raise ValueError(
                    "The format not exists in the database: %s" % fmt_name
                )

            table = db.table(fmt_name)
            msg = dict(table.get(doc_id=-1))

            setters = {}
            for field_id in range(len(table) - 1):
                field = dict(table.get(doc_id=field_id))
                name = field.pop("name")
                special = field.pop("special") if "special" in field else None
                setters[name] = FieldSetter(special=special, **field)

        return cls(**msg, **setters)
