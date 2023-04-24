"""Private module of ``pyiak_instr.types.store`` with types for store
module."""
from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import (
    Any,
    Generic,
    Generator,
    Iterable,
    Iterator,
    Protocol,
    Self,
    TypeAlias,
    TypeVar,
    overload,
)

import numpy as np
import numpy.typing as npt

from .._pattern import MetaPatternABC, PatternABC, WritablePatternABC
from ...core import Code
from ...rwfile import RWConfig
from ...exceptions import NotConfiguredYet
from ...typing import SupportsContainsGetitem


__all__ = [
    "STRUCT_DATACLASS",
    "BytesFieldABC",
    "BytesFieldStructProtocol",
    "BytesStorageABC",
    "BytesStoragePatternABC",
    "ContinuousBytesStoragePatternABC",
]


StructT = TypeVar("StructT", bound="BytesFieldStructProtocol")
ParserT = TypeVar("ParserT", bound="BytesFieldABC[Any, Any]")
StorageT = TypeVar("StorageT", bound="BytesStorageABC[Any, Any]")
PatternT = TypeVar("PatternT", bound=PatternABC[Any])


STRUCT_DATACLASS = dataclass(frozen=True, kw_only=True)


@STRUCT_DATACLASS
class BytesFieldStructProtocol(Protocol):
    """
    Represents protocol for field structure.
    """

    start: int = 0
    """the number of bytes in the message from which the fields begin."""

    stop: int | None = None
    """index of stop byte. If None - stop is end of bytes."""

    bytes_expected: int = 0
    """expected bytes count for field. If less than 1, from the start byte
    to the end of the message."""

    fmt: Code = Code.U8
    """format for packing or unpacking the content.
    The word length is calculated from the format."""

    order: Code = Code.BIG_ENDIAN
    """bytes order for packing and unpacking."""

    default: bytes = b""  # todo: to ContentType
    """default value of the field."""

    def __post_init__(self) -> None:
        self._verify_values_before_modifying()
        self._modify_values()
        self._verify_values_after_modifying()

    @abstractmethod
    def decode(self, content: bytes) -> npt.NDArray[np.int_ | np.float_]:
        """
        Decode content from bytes with parameters from struct.

        Parameters
        ----------
        content : bytes
            content for decoding.

        Returns
        -------
        npt.NDArray[np.int_ | np.float_]
            decoded content.
        """

    @abstractmethod
    def encode(self, content: int | float | Iterable[int | float]) -> bytes:
        """
        Encode content to bytes with parameters from struct.

        Parameters
        ----------
        content : int | float | Iterable[int | float]
            content for encoding.

        Returns
        -------
        bytes
            encoded content.
        """

    @property
    @abstractmethod
    def word_bytesize(self) -> int:
        """
        Returns
        -------
        int
            count of bytes in one word.
        """

    def verify(self, content: bytes) -> bool:
        """
        Verify that `content` is correct for the given field structure.

        Parameters
        ----------
        content : bytes
            content to verifying.

        Returns
        -------
        bool
            True - content is correct, False - is not.
        """
        if self.is_dynamic:
            return len(content) % self.word_bytesize == 0
        return len(content) == self.bytes_expected

    def _modify_values(self) -> None:
        if self.bytes_expected < 0:
            object.__setattr__(self, "bytes_expected", 0)

        if self.bytes_expected > 0:
            stop = self.start + self.bytes_expected
            if stop != 0:
                object.__setattr__(self, "stop", stop)

        elif self.stop is not None:
            if not (self.start >= 0 and self.stop < 0):
                object.__setattr__(
                    self, "bytes_expected", self.stop - self.start
                )

        elif self.start <= 0 and self.stop is None:
            object.__setattr__(self, "bytes_expected", -self.start)

        else:
            raise AssertionError(
                "impossible to modify start, stop and bytes_expected"
            )

    def _verify_values_after_modifying(self) -> None:
        """
        Verify values after modifying.
        """
        if self.bytes_expected % self.word_bytesize:
            raise ValueError(
                "'bytes_expected' does not match an integer word count"
            )

    def _verify_values_before_modifying(self) -> None:
        """
        Verify values before modifying.
        """
        if self.stop == 0:
            raise ValueError("'stop' can't be equal to zero")
        if self.stop is not None and self.bytes_expected > 0:
            raise TypeError("'bytes_expected' or 'stop' setting not allowed")
        if 0 > self.start > -self.bytes_expected:
            raise ValueError("it will be out of bounds")

    @property
    def has_default(self) -> bool:
        """
        Returns
        -------
        bool
            True - default more than zero.
        """
        return len(self.default) != 0

    @property
    def is_dynamic(self) -> bool:
        """
        Returns
        -------
        bool
            if True - field is dynamic (from empty to any).
        """
        return self.bytes_expected == 0

    @property
    def slice_(self) -> slice:
        """
        Returns
        -------
        slice
            slice with start and stop indexes of field.
        """
        return slice(self.start, self.stop)

    @property
    def words_expected(self) -> int:
        """
        Returns
        -------
        int
            expected words count in the field. Returns 0 if field is infinite.
        """
        return self.bytes_expected // self.word_bytesize


class BytesFieldABC(ABC, Generic[StorageT, StructT]):
    """
    Represents base parser class for work with field content.

    Parameters
    ----------
    name : str
        field name.
    struct : StructT
        field structure instance.
    """

    def __init__(self, storage: StorageT, name: str, struct: StructT) -> None:
        self._storage = storage
        self._name = name
        self._struct = struct

    def decode(self) -> npt.NDArray[np.int_ | np.float_]:
        """
        Decode field content.

        Returns
        -------
        NDArray
            decoded content.
        """
        return self._struct.decode(self.content)

    def encode(self, content: int | float | Iterable[int | float]) -> None:
        """
        Encode content to bytes and set .

        Parameters
        ----------
        content : int | float | Iterable[int | float]
            content to encoding.
        """
        self._storage.change(self._name, content)

    def verify(self, content: bytes) -> bool:
        """
        Check the content for compliance with the field parameters.

        Parameters
        ----------
        content: bytes
            content for validating.

        Returns
        -------
        bool
            True - content is correct, False - not.
        """
        return self._struct.verify(content)

    @property
    def bytes_count(self) -> int:
        """
        Returns
        -------
        int
            bytes count of the content.
        """
        return len(self.content)

    @property
    def content(self) -> bytes:
        """
        Returns
        -------
        bytes
            field content.
        """
        return self._storage.content[self._struct.slice_]

    @property
    def is_empty(self) -> bool:
        """
        Returns
        -------
        bool
            True - if field content is empty.
        """
        return len(self.content) == 0

    @property
    def name(self) -> str:
        """
        Returns
        -------
        str
            field name.
        """
        return self._name

    @property
    def struct(self) -> StructT:
        """
        Returns
        -------
        StructT
            struct instance.
        """
        return self._struct

    @property
    def words_count(self) -> int:
        """
        Returns
        -------
        int
            count of words in the field.
        """
        return self.bytes_count // self._struct.word_bytesize

    def __bytes__(self) -> bytes:
        """
        Returns
        -------
        bytes
            field content.
        """
        return self.content

    @overload
    def __getitem__(self, index: int) -> int | float:
        ...

    @overload
    def __getitem__(self, index: slice) -> npt.NDArray[np.int_ | np.float_]:
        ...

    def __getitem__(
        self, index: int | slice
    ) -> int | float | npt.NDArray[np.int_ | np.float_]:
        """
        Parameters
        ----------
        index : int | slice
            word index.

        Returns
        -------
        int | float | NDArray[int | float]
            word value.
        """
        return self.decode()[index]

    def __iter__(self) -> Generator[int | float, None, None]:
        """
        Yields
        ------
        int | float
            word value.
        """
        for item in self.decode():
            yield item

    def __len__(self) -> int:
        """
        Returns
        -------
        int
            bytes count of the content.
        """
        return self.bytes_count


class BytesStorageABC(ABC, Generic[ParserT, StructT]):
    """
    Represents abstract class for bytes storage.
    """

    _struct_field: dict[type[StructT], type[ParserT]]

    def __init__(self, name: str, fields: dict[str, StructT]) -> None:
        self._name = name
        self._f = fields
        self._c = bytearray()

    def change(
            self, name: str, content: int | float | Iterable[int | float]
    ) -> None:
        """
        Change content of one field by name.

        Parameters
        ----------
        name : str
            field name.
        content : bytes
            new field content.
        """
        if len(self) == 0:
            raise TypeError("message is empty")
        parser = self[name]
        self._c[parser.struct.slice_] = self._encode_content(parser, content)

    def decode(self) -> dict[str, npt.NDArray[np.int_ | np.float_]]:
        """
        Iterate by fields end decode each.

        Returns
        -------
        dict[str, npt.NDArray[Any]]
            dictionary with decoded content where key is a field name.
        """
        return {n: f.decode() for n, f in self.items()}

    @overload
    def encode(self, content: bytes) -> Self:
        ...

    @overload
    def encode(self, **fields: int | float | Iterable[int | float]) -> Self:
        ...

    def encode(  # type: ignore[misc]
        self,
        content: bytes = b"",
        **fields: int | float | Iterable[int | float],
    ) -> Self:
        """
        Encode new content to storage.

        Parameters
        ----------
        content : bytes, default=b''
            new full content for storage.
        **fields : int | float | Iterable[int | float]
            content for each field.

        Returns
        -------
        Self
            self instance.

        Raises
        ------
        TypeError
            if trying to set full content and content for each field;
            if full message or fields list is empty.
        """
        if len(content) != 0 and len(fields) != 0:
            raise TypeError("takes a message or fields (both given)")

        if len(content) != 0:
            self._extract(content)
        elif len(fields) != 0:
            self._set(fields)
        else:
            raise TypeError("message is empty")

        return self

    def items(self) -> Iterator[tuple[str, ParserT]]:
        """
        Returns
        -------
        Iterable[tuple[str, ParserT]]
            Iterable of names and parsers.
        """
        return ((f.name, f) for f in self)

    def _check_fields_list(self, fields: set[str]) -> None:
        """
        Check that fields names is correct.

        Parameters
        ----------
        fields : set[str]
            set of field names for setting.

        Raises
        ------
        AttributeError
            if extra or missing field names founded.
        """
        diff = set(self._f).symmetric_difference(fields)
        for name in diff.copy():
            if name in self:
                parser = self[name]
                if (
                    parser.struct.has_default
                    or parser.struct.is_dynamic
                    or len(parser) != 0
                ):
                    diff.remove(name)

        if len(diff) != 0:
            raise AttributeError(
                "missing or extra fields were found: "
                f"{', '.join(map(repr, sorted(diff)))}"
            )

    def _extract(self, content: bytes) -> None:
        """
        Extract fields from existing bytes content.

        Parameters
        ----------
        content: bytes
            new content.

        Raises
        ------
        ValueError
            if content length smaller than minimal storage length
            (`bytes_expected`).
        """
        bytes_expected = self.bytes_expected
        if len(content) < bytes_expected:
            raise ValueError("bytes content too short")
        if not self.is_dynamic and len(content) > bytes_expected:
            raise ValueError("bytes content too long")

        if len(self) != 0:
            self._c = bytearray()
        self._set_all(
            {p.name: content[p.struct.slice_] for p in self}
        )

    def _set(
        self, fields: dict[str, int | float | Iterable[int | float]]
    ) -> None:
        """
        Set fields content.

        Parameters
        ----------
        fields : dict[str, int | float | Iterable[int | float]]
            dictionary of fields content where key is a field name.
        """
        if len(self) == 0:
            self._set_all(fields)
        else:
            for name, content in fields.items():
                self.change(name, content)

    def _set_all(
        self, fields: dict[str, int | float | Iterable[int | float]]
    ) -> None:
        """
        Set content to empty field.

        Parameters
        ----------
        fields : dict[str, int | float | Iterable[int | float]]
            dictionary of fields content where key is a field name.

        Raises
        ------
        AssertionError
            if in some reason message is not empty.
        """
        assert len(self) == 0, "message must be empty"

        self._check_fields_list(set(fields))
        for name, parser in self.items():
            if name in fields:
                self._c += self._encode_content(parser, fields[name])

            elif parser.struct.has_default:
                self._c += parser.struct.default

            elif parser.struct.is_dynamic:
                continue

            else:
                raise AssertionError(
                    f"it is impossible to set the value of the '{name}' field"
                )

    @staticmethod
    def _encode_content(
            parser: ParserT, raw: Iterable[int | float] | int | float,
    ) -> bytes:
        """
        Get new content to the field.

        Parameters
        ----------
        parser: str
            field parser.
        raw: ArrayLike
            new content.

        Returns
        -------
        bytes
            new field content

        Raises
        ------
        ValueError
            if new content is not correct for field.
        """
        if isinstance(raw, bytes):
            content = raw
        else:
            content = parser.struct.encode(raw)  # todo: bytes support

        if not parser.verify(content):
            raise ValueError(
                f"'{content.hex(' ')}' is not correct for '{parser.name}'"
            )

        return content

    @property
    def content(self) -> bytes:
        """
        Returns
        -------
        bytes
            content of the storage.
        """
        return bytes(self._c)

    @property
    def bytes_expected(self) -> int:
        """
        Returns
        -------
        int
            expected bytes count or minimal length (if it has dynamic field).
        """
        return sum(s.bytes_expected for s in self._f.values())

    @property
    def is_dynamic(self) -> bool:
        return any(p.struct.is_dynamic for p in self)

    @property
    def name(self) -> str:
        """
        Returns
        -------
        str
            name of the storage.
        """
        return self._name

    def __contains__(self, name: str) -> bool:
        """Check that field name in message."""
        return name in self._f

    def __getitem__(self, name: str) -> ParserT:
        """Get field parser."""
        struct = self._f[name]
        return self._struct_field[struct.__class__](self, name, struct)

    def __iter__(self) -> Iterator[ParserT]:
        """Iterate by field parsers."""
        return (self[n] for n in self._f)

    def __len__(self) -> int:
        """Bytes count in message"""
        return len(self._c)


class BytesStoragePatternABC(
    MetaPatternABC[StorageT, PatternT],
    WritablePatternABC,
    Generic[StorageT, PatternT],
):
    """
    Represent abstract class of bytes storage.
    """

    _sub_p_par_name = "fields"

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
        pars = {
            self._name: self.__init_kwargs__(),
            **{n: p.__init_kwargs__() for n, p in self._sub_p.items()},
        }

        with RWConfig(path) as cfg:
            if cfg.api.has_section(self._name):
                cfg.api.remove_section(self._name)
            cfg.set({self._name: pars})
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
            raise TypeError(f"given {len(keys)} keys, expect one")
        (name,) = keys

        with RWConfig(path) as cfg:
            opts = cfg.api.options(name)
            opts.pop(opts.index(name))
            return cls(**cfg.get(name, name)).configure(
                **{f: cls._sub_p_type(**cfg.get(name, f)) for f in opts}
            )

    # @staticmethod
    # def _is_dynamic_pattern(
    #     kwargs: dict[str, Any], pattern: PatternT | None = None
    # ) -> bool:  # todo: tests
    #     """
    #     Returns True if the joined parameters can be interpreted as a dynamic.
    #
    #     Parameters
    #     ----------
    #     kwargs : dict[str, Any]
    #         additional parameters.
    #     pattern : PatternT | None, default=None
    #         pattern instance
    #
    #     Returns
    #     -------
    #     bool
    #         True if the `kwargs` or `pattern` can be interpreted as a
    #         dynamic, otherwise - False
    #     """
    #
    #     def check(obj: SupportsContainsGetitem | None) -> bool:
    #         """
    #         Check that the object can be interpreted as a dynamic.
    #
    #         Parameters
    #         ----------
    #         obj : SupportsContainsGetitem
    #             object for checking.
    #
    #         Returns
    #         -------
    #         bool
    #             True if the object can be interpreted as a dynamic,
    #             otherwise - False
    #         """
    #         if obj is None:
    #             return False
    #         return (
    #             "stop" in obj
    #             and obj["stop"] is None
    #             or "bytes_expected" in obj
    #             and isinstance(obj["bytes_expected"], int)
    #             and obj["bytes_expected"] <= 0
    #         )
    #
    #     return check(kwargs) or check(pattern)


class ContinuousBytesStoragePatternABC(
    BytesStoragePatternABC[StorageT, PatternT],
    Generic[StorageT, PatternT],
):
    """
    Represents methods for configure continuous storage.

    It's means `start` of the field is equal to `stop` of previous field
    (e.g. without gaps in content).
    """

    _only_auto_parameters = {"start", "stop"}
    _step_name = "bytes_expected"  # todo: check exists in pattern

    def _modify_all(
            self, changes_allowed: bool, for_subs: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        dyn_name = self._modify_before_dyn(for_subs)
        if len(dyn_name) > 0:
            self._modify_after_dyn(dyn_name, for_subs)
        return super()._modify_all(changes_allowed, for_subs)

    def _modify_before_dyn(
            self, for_subs: dict[str, dict[str, Any]]
    ) -> str:
        start = 0
        for name, kw in for_subs.items():
            if kw[self._step_name] <= 0:  # is dynamic field
                kw.update(start=start)
                return name
            kw.update(start=start, stop=start + kw[self._step_name])
            start = kw["stop"]
        return ""

    def _modify_after_dyn(
            self,
            dyn_name: str,
            for_subs: dict[str, dict[str, Any]],
      ) -> None:
        stop = 0
        for name in list(for_subs)[::-1]:
            kw = for_subs[name]
            if name == dyn_name:
                kw.update(stop=stop if stop != 0 else None)
                return
            kw.update(
                start=stop - kw[self._step_name],
                stop=stop if stop != 0 else None,
            )
            stop -= kw["start"]

    # def _get_continuous(
    #     self,
    #     changes_allowed: bool,
    #     for_storage: dict[str, Any],
    #     for_fields: dict[str, dict[str, Any]],
    # ) -> StorageT:
    #     """
    #     Get initialized continuous storage.
    #
    #     Parameters
    #     ----------
    #     changes_allowed: bool
    #         allows situations where keys from the pattern overlap with kwargs.
    #         If False, it causes an error on intersection, otherwise the
    #         `additions` take precedence.
    #     for_storage: dict[str, Any]:
    #         dictionary with parameters for storage in format
    #         {PARAMETER: VALUE}.
    #     for_fields: dict[str, dict[str, Any]]
    #         dictionary with parameters for fields in format
    #         {FIELD: {PARAMETER: VALUE}}.
    #
    #     Returns
    #     -------
    #     ContinuousBytesStorage
    #         initialized storage.
    #
    #     Raises
    #     ------
    #     SyntaxError
    #         if changes are not allowed, but there is an attempt to modify
    #         the parameter.
    #     TypeError
    #         if trying to set 'fields'.
    #     """
    #     storage_kw = self._get_parameters_dict(changes_allowed, for_storage)
    #
    #     fields, dyn_name, dyn_start = self._get_fields_before_dyn(
    #         changes_allowed, for_fields
    #     )
    #
    #     if dyn_start >= 0:
    #         after, dyn_stop = self._get_fields_after_dyn(
    #             changes_allowed, for_fields, dyn_name
    #         )
    #
    #         dyn_kw = for_fields[dyn_name] if dyn_name in for_fields else {}
    #         dyn_kw.update(start=dyn_start, stop=dyn_stop)
    #         fields[dyn_name] = self._sub_p[dyn_name].get(
    #             changes_allowed=changes_allowed, **dyn_kw
    #         )
    #
    #         fields.update(after)
    #
    #     return self._target(fields=fields, **storage_kw)
    #
    # def _get_fields_after_dyn(
    #     self,
    #     changes_allowed: bool,
    #     fields_kw: dict[str, dict[str, Any]],
    #     dyn: str,
    # ) -> tuple[dict[str, StructT], int | None]:
    #     """
    #     Get the dictionary of fields that go from infinite field
    #     (not included) to end.
    #
    #     Parameters
    #     ----------
    #     changes_allowed: bool
    #         allows situations where keys from the pattern overlap with kwargs.
    #         If False, it causes an error on intersection, otherwise the
    #         `additions` take precedence.
    #     fields_kw : dict[str, dict[str, Any]]
    #         dictionary of kwargs for fields.
    #     dyn : str
    #         name of dynamic field.
    #
    #     Returns
    #     -------
    #     tuple[dict[str, OptionsT], str]
    #         fields - dictionary of fields from infinite (not included);
    #         dyn_stop - stop index of dynamic field.
    #
    #     Raises
    #     ------
    #     TypeError
    #         if there is tow dynamic fields.
    #     AssertionError
    #         if for some reason the dynamic field is not found.
    #     """
    #     start = 0
    #     fields: list[tuple[str, StructT]] = []
    #     for name in list(self._sub_p)[::-1]:
    #         if name == dyn:
    #             return dict(fields[::-1]), start if start != 0 else None
    #
    #         pattern = self._sub_p[name]
    #         field_kw = fields_kw[name] if name in fields_kw else {}
    #         if self._is_dynamic_pattern(field_kw, pattern):
    #             raise TypeError("two dynamic field not allowed")
    #
    #         start -= pattern["bytes_expected"]
    #         field_kw.update(start=start)
    #         fields.append(
    #             (
    #                 name,
    #                 pattern.get(changes_allowed=changes_allowed, **field_kw),
    #             )
    #         )
    #
    #     raise AssertionError("dynamic field not found")
    #
    # def _get_fields_before_dyn(
    #     self, changes_allowed: bool, fields_kw: dict[str, dict[str, Any]]
    # ) -> tuple[dict[str, StructT], str, int]:
    #     """
    #     Get the dictionary of fields that go up to and including the infinite
    #     field.
    #
    #     Parameters
    #     ----------
    #     changes_allowed: bool
    #         allows situations where keys from the pattern overlap with kwargs.
    #         If False, it causes an error on intersection, otherwise the
    #         `additions` take precedence.
    #     fields_kw : dict[str, dict[str, Any]]
    #         dictionary of kwargs for fields.
    #
    #     Returns
    #     -------
    #     tuple[dict[str, StructT], str, int]
    #         fields - dictionary of fields up to infinite (include);
    #         dyn_name - name of infinite field. Empty if there is no found;
    #         dyn_start - start index of infinite field. -1 if field is no
    #             found.
    #     """
    #     start: int = 0
    #     fields: dict[str, StructT] = {}
    #     for name, pattern in self._sub_p.items():
    #         field_kw = fields_kw[name] if name in fields_kw else {}
    #         if self._is_dynamic_pattern(field_kw, pattern):
    #             return fields, name, start
    #
    #         field_kw.update(start=start)
    #         fields[name] = pattern.get(
    #             changes_allowed=changes_allowed, **field_kw
    #         )
    #         start = fields[name].stop  # type: ignore[assignment]
    #
    #     return fields, "", -1
