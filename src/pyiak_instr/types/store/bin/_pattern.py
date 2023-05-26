from __future__ import annotations
from pathlib import Path
from configparser import ConfigParser
from dataclasses import dataclass
from abc import abstractmethod
from typing import (
    Any,
    Generic,
    Iterable,
    Iterator,
    Protocol,
    Self,
    TypeVar,
    cast,
    overload,
)

import numpy as np
import numpy.typing as npt

from ....core import Code
from ....exceptions import NotConfiguredYet
from ....typing import WithBaseStringMethods
from ..._pattern import (
    MetaPatternABC,
    PatternABC,
    SubPatternAdditions,
    WritablePatternABC,
)
from ..._rwdata import RWData
from ._bin import BytesStorageABC
from ._struct import (
    BytesDecodeT,
    BytesEncodeT,
    BytesFieldStructABC,
    BytesStorageStructABC,
)


__all__ = [
    "BytesFieldStructPatternABC",
    "BytesStorageStructPatternABC",
    "BytesStoragePatternABC",
    "ContinuousBytesStorageStructPatternABC"
]


FieldStructT = TypeVar("FieldStructT", bound=BytesFieldStructABC)
StorageStructT = TypeVar(
    "StorageStructT", bound=BytesStorageStructABC[BytesFieldStructABC]
)
StorageT = TypeVar("StorageT", bound=BytesStorageABC)

FieldStructPatternT = TypeVar(
    "FieldStructPatternT", bound="BytesFieldStructPatternABC"
)
StorageStructPatternT = TypeVar(
    "StorageStructPatternT", bound="BytesStorageStructPatternABC"
)
StoragePatternT = TypeVar(
    "StoragePatternT", bound="BytesStoragePatternABC"
)


class BytesFieldStructPatternABC(PatternABC[FieldStructT]):
    """
    Represent abstract class of pattern for bytes struct (field).
    """

    @property
    def is_dynamic(self) -> bool:
        """
        Returns
        -------
        bool
            True if the pattern can be interpreted as a dynamic,
            otherwise - False.
        """
        return self.size <= 0

    @property
    def size(self) -> int:
        """
        Returns
        -------
        int
            size of the field in bytes.
        """
        if "bytes_expected" in self._kw:
            return cast(int, self._kw["bytes_expected"])

        start = self._kw["start"] if "start" in self._kw else 0
        stop = self._kw["stop"] if "stop" in self._kw else None

        if stop is None:
            if start < 0:
                return -start
        elif start >= 0 and stop > 0 or start < 0 and stop < 0:
            return stop - start
        return 0


class BytesStorageStructPatternABC(
    MetaPatternABC[StorageStructT, FieldStructPatternT]
):
    """
    Represent abstract class of pattern for bytes struct (storage).
    """

    _sub_p_par_name = "fields"

    def _modify_sub_additions(self, sub_additions: SubPatternAdditions) -> None:
        super()._modify_sub_additions(sub_additions)
        for name in self._sub_p:
            sub_additions.update_additions(name, name=name)


class ContinuousBytesStorageStructPatternABC(
    BytesStorageStructPatternABC[StorageStructT, FieldStructPatternT],
):
    """
    Represents methods for configure continuous storage.

    It's means `start` of the field is equal to `stop` of previous field
    (e.g. without gaps in content).
    """

    def _modify_sub_additions(self, sub_additions: SubPatternAdditions) -> None:
        super()._modify_sub_additions(sub_additions)
        dyn_name = self._modify_before_dyn(sub_additions)
        if dyn_name is not None:
            self._modify_after_dyn(dyn_name, sub_additions)

    def _modify_before_dyn(self, sub_additions: SubPatternAdditions) -> str | None:
        """
        Modify `sub_additions` up to dynamic field.

        Parameters
        ----------
        sub_additions : SubPatternAdditions
            additional kwargs for sub-pattern object.

        Returns
        -------
        str | None
            name of the dynamic field. If None - there is no dynamic field.
        """
        start = 0
        for name, pattern in self._sub_p.items():
            sub_additions.update_additions(name, start=start)
            if pattern.is_dynamic:
                return name
            start += pattern.size

    def _modify_after_dyn(
            self, dyn_name: str, sub_additions: SubPatternAdditions
    ) -> None:
        """
        Modify `sub_additions` from dynamic field to end.

        Parameters
        ----------
        dyn_name : str
            name of the dynamic field.
        sub_additions : SubPatternAdditions
            additional kwargs for sub-pattern object.

        Raises
        ------
        TypeError
            if there is tow dynamic fields.
        AssertionError
            if for some reason the dynamic field is not found.
        """
        start = 0
        for name in list(self._sub_p)[::-1]:
            pattern = self._sub_p[name]

            if pattern.is_dynamic:
                if name == dyn_name:
                    sub_additions.update_additions(
                        name, stop=start if start != 0 else None
                    )
                    return
                raise TypeError("two dynamic field not allowed")

            start -= pattern.size
            sub_additions.update_additions(name, start=start)

        raise AssertionError("dynamic field not found")


class BytesStoragePatternABC(
    MetaPatternABC[StorageT, StorageStructPatternT], WritablePatternABC
):

    _rwdata: type[RWData[ConfigParser]]
    _sub_p_par_name = "storage"

    def configure(self, **patterns: StorageStructPatternT) -> Self:
        if len(patterns) > 1:
            raise TypeError(
                f"only one storage pattern allowed, got {len(patterns)}"
            )
        return super().configure(**patterns)

    def write(self, path: Path) -> None:
        """
        Write pattern configuration to config file.

        Parameters
        ----------
        path : Path
            path to config file.

        Raises
        ------
        NotConfiguredYet
            is patterns is not configured yet.
        """
        if len(self._sub_p) == 0:
            raise NotConfiguredYet(self)

        (name, pattern), = self._sub_p.items()
        pars = {
            "_": self.__init_kwargs__(),
            name: pattern.__init_kwargs__(),
            # todo: access to sub-patterns in MetaPattern
            **{n: p.__init_kwargs__() for n, p in pattern._sub_p.items()},
        }

        with self._rwdata(path) as cfg:
            if cfg.api.has_section(name):
                cfg.api.remove_section(name)
            cfg.set({name: pars})
            cfg.commit()

    @classmethod
    def read(cls, path: Path, *keys: str) -> Self:
        """
        Read init kwargs from `path` and initialize class instance.

        Parameters
        ----------
        path : Path
            path to the file.
        *keys : str
            keys to search required pattern in file. Must include only one
            argument - `name`.

        Returns
        -------
        Self
            initialized self instance.

        Raises
        ------
        TypeError
            if given invalid count of keys.
        """
        if len(keys) != 1:
            raise TypeError(
                f"{cls.__name__} takes only 1 argument "
                f"({len(keys)} given)"
            )
        (name,) = keys

        with cls._rwdata(path) as cfg:
            opts = cfg.api.options(name)
            opts.pop(opts.index("_"))
            opts.pop(opts.index(name))

            # todo: access to sub-pattern type in MetaPattern
            field_type = cls._sub_p_type._sub_p_type
            return cls(**cfg.get(name, "_")).configure(
                **{name: cls._sub_p_type(**cfg.get(name, name)).configure(
                    **{f: field_type(**cfg.get(name, f)) for f in opts}
                )}
            )

    def _get_parameters_dict(
        self,
        changes_allowed: bool,
        additions: dict[str, Any],
    ) -> dict[str, Any]:
        parameters = super()._get_parameters_dict(changes_allowed, additions)

        storage, = parameters[self._sub_p_par_name].values()
        parameters["storage"] = storage

        parameters["pattern"] = self
        return parameters

    def _modify_sub_additions(self, sub_additions: SubPatternAdditions) -> None:
        super()._modify_sub_additions(sub_additions)
        for name in self._sub_p:
            sub_additions.update_additions(name, name=name)