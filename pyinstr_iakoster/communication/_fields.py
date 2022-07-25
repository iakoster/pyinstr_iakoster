import struct
from typing import (
    Any,
    Iterable,
    SupportsBytes,
    Generator,
    Protocol,
    runtime_checkable
)

import numpy as np
import numpy.typing as npt


from ..exceptions import (
    FloatWordsCountError,
    PartialFieldError,
)


__all__ = [
    "ContentType",
    "Field",
    "FieldSetter",
    "AddressField",
    "DataField",
    "DataLengthField",
    "OperationField",
    "SingleField",
    "StaticField",
    "FieldType",
    "FloatWordsCountError",
    "PartialFieldError",
]


ContentType = (
        bytes | bytearray | int | float | Iterable |
        SupportsBytes | np.number | npt.NDArray
)


class BaseField(object):
    """
    Represents a basic class for single field of a Message.

    Parameters
    ----------
    format_name: str
        the name of package format to which the field belongs.
    name: str
        the name of the field.
    info: dict of {str, Any}
        additional info about a field.
    start_byte: int
        the number of bytes in the message from which the fields begin.
    expected: int
        expected number of words in the field. If equal to -1, from
        the start byte to the end of the message.
    may_be_empty: bool
        if True then field can be empty in a message.
    fmt: str
        format for packing or unpacking the content. The word length
        is calculated from the format.
    content: bytes
        field content in bytes.
    parent: MessageType or None
        parent message.
    """

    def __init__(
            self,
            format_name: str,
            name: str,
            *,
            start_byte: int,
            expected: int,
            may_be_empty: bool,
            fmt: str,
            info: dict[str, Any],
            content: bytes,
            default: ContentType,
            parent,
    ):
        self._fmt_name = format_name
        self._name = name
        self._info = info
        self._st_byte = start_byte
        self._exp = expected
        self._may_be_empty = may_be_empty
        self._fmt = fmt
        self._content = content
        self._def = default
        self._parent = parent

        self._word_bsize = struct.calcsize(self._fmt)
        self._fin = expected > 0
        self._end_byte = start_byte + self._word_bsize * expected \
            if self._fin else None
        self._slice = slice(start_byte, self._end_byte)

    @property
    def bytesize(self) -> int:
        """The length of the one word in bytes."""
        return self._word_bsize

    @property
    def content(self) -> bytes:
        """The field content."""
        return self._content

    @property
    def default(self) -> bytes:
        """Default field content"""
        return self._def

    @property
    def end_byte(self) -> int | None:
        """The number of byte in the message from which the field starts."""
        return self._end_byte

    @end_byte.setter
    def end_byte(self, stop: int | None) -> None: # nodesc
        self._end_byte = stop
        self._slice = slice(self._st_byte, stop)

    @property
    def expected(self) -> int:
        """The expected count of words."""
        return self._exp

    @property
    def field_class(self):
        """The field class."""
        return self.__class__

    @property
    def finite(self):
        return self._fin

    @property
    def fmt(self) -> str:
        """The converion format."""
        return self._fmt

    @property
    def format_name(self) -> str:
        """The name of package format to which the field belongs."""
        return self._fmt_name

    @property
    def info(self) -> dict[str, Any]:
        """Additional information about the field."""
        return self._info

    @property
    def may_be_empty(self) -> bool:
        """May be empty content in the field"""
        return self._may_be_empty

    @property
    def name(self) -> str:
        """The name of the massage field."""
        return self._name

    @property
    def parent(self):
        return self._parent

    @property
    def slice(self):
        """The range of bytes from the message belonging to the field"""
        return self._slice

    @property
    def start_byte(self) -> int:
        """The number of byte in the message from which the field starts."""
        return self._st_byte

    @start_byte.setter
    def start_byte(self, start: int | None) -> None: # nodesc
        self._st_byte = start
        self._slice = slice(start, self._end_byte)

    @property
    def words_count(self) -> int:
        """The length of the field in words."""
        return len(self._content) // self._word_bsize

    def __bytes__(self) -> bytes:
        """Returns field content"""
        return self._content

    def __len__(self) -> int:
        """Returns the length of the content in bytes"""
        return len(self._content)


class Field(BaseField):
    """
    Represents a general field of a Message.

    Parameters
    ----------
    format_name: str
        the name of package format to which the field belongs.
    name: str
        the name of the field.
    info: dict of {str, Any}, optional
        additional info about a field.
    start_byte: int
        the number of bytes in the message from which the fields begin.
    expected: int
        expected number of words in the field. If equal to -1, from
        the start byte to the end of the message.
    fmt: str
        format for packing or unpacking the content. The word length
        is calculated from the format.
    default: Content, default=b""
        field content.
    may_be_empty: bool, default=False
        if True then field can be empty in a message.

    See Also
    --------
    FieldBase: parent class.
    """

    def __init__(
            self,
            format_name: str,
            name: str,
            *,
            start_byte: int,
            expected: int,
            fmt: str,
            info: dict[str, Any] = None,
            default: ContentType = b"",
            may_be_empty: bool = False,
            parent=None,
    ):
        if info is None:
            info = {}
        BaseField.__init__(
            self,
            format_name,
            name,
            start_byte=start_byte,
            expected=expected,
            may_be_empty=may_be_empty,
            fmt=fmt,
            info=info,
            content=b"",
            default=b"",
            parent=parent
        )
        if not isinstance(default, bytes) or len(default):
            self.set(default)
            self._def = self._content

    def get_setter(self): # nodesc
        return FieldSetter.base(
            expected=self._exp,
            fmt=self._fmt,
            default=self.unpack_default(),
            info=self._info,
            may_be_empty=self._may_be_empty
        )

    def set(self, content: ContentType) -> None:
        """
        Set the field content.

        If the received content is not of type bytes, then there will be
        an attempt to convert the received variable into type bytes,
        otherwise an exception will be raised.

        Parameters
        ----------
        content: Content type
            new field content.

        See Also
        --------
        _validate_content: method of validating new content.
        """
        self._content = self._validate_content(self._convert_content(content))

    def extract(self, message: bytes) -> None:
        """
        Extract new content from a message in range self.slice.

        Extracts a field from start_byte to bytesize * expected from
        the message received in the method. If expected < 1, it writes
        everything from start_byte to the end of the received message.

        Parameters
        ----------
        message: bytes
            incoming message.

        Raises
        ------
        ValueError
            if message is empty.

        See Also
        --------
        set_content: method of setting new field content.
        """
        if len(message) == 0:
            raise ValueError(
                "Unable to extract because the incoming message is empty"
            )
        self.set(message[self._slice])

    def hex(self, sep: str = " ", sep_step: int = None) -> str:
        """
        Returns a string of hexadecimal numbers from the content.

        Parameters
        ----------
        sep: str
            separator between bytes.
        sep_step: int
            separator step. If None equals bytesize.

        Returns
        -------
        str
            hex string.
        """
        if sep_step is None:
            sep_step = self._word_bsize
        return self._content.hex(sep=sep, bytes_per_sep=sep_step)

    def reset_to_default(self) -> None: # nodesc
        self._content = self._def

    def unpack(self, fmt: str = None) -> npt.NDArray:
        """
        Returns the content of the field unpacked in fmt.

        Parameters
        ----------
        fmt: str
            format for unpacking. If None, fmt is taken from
            an instance of the class.

        Returns
        -------
        NDArray
            an array of words
        """
        return self._unpack_bytes(self._content, fmt=fmt)

    def unpack_default(self, fmt: str = None) -> npt.NDArray: # nodesc
        return self._unpack_bytes(self._def, fmt=fmt)

    def _convert_content(self, content: ContentType) -> bytes:
        """
        Convert content to bytes via `fmt` or `__bytes__`.

        Parameters
        ----------
        content: Content
            content for converting.

        Returns
        -------
        bytes
            content converted to bytes.
        """

        if isinstance(content, bytes):
            converted = content
        elif isinstance(content, bytearray):
            converted = bytes(content)
        elif isinstance(content, np.ndarray):
            converted = content.astype(self._fmt).tobytes()
        elif isinstance(content, Iterable):
            converted = np.array(content, dtype=self._fmt).tobytes()
        elif np.issubdtype(type(content), np.number):
            converted = struct.pack(self._fmt, content)
        else:
            converted = bytes(content)

        return converted

    def _unpack_bytes(self, bytes_: bytes, fmt: str = None) -> npt.NDArray: # nodesc
        if fmt is None:
            fmt = self._fmt
        return np.frombuffer(bytes_, dtype=fmt)

    def _validate_content(
            self, content: bytes = None, exp: int = None
    ) -> bytes:
        """
        Validate field content.

        If the content is None, checks the content from the class instance.

        Parameters
        ----------
        content: bytes, default=None
            content for validating.
        exp: int, default=None
            expected words in content.

        Returns
        -------
        bytes
            content.

        Raises
        ------
        FloatWordsCountError
            if the number of words in the content is not an integer.
        PartialFieldError
            if the length of the content is less than expected.
        """
        if content is None:
            content = self._content
        if content == b"":
            return content
        if exp is None:
            exp = self._exp

        if len(content) % self._word_bsize != 0:
            raise FloatWordsCountError(
                self.__class__.__name__,
                exp,
                len(content) / self._word_bsize
            )

        # Similary to self._exp > 0 and
        # len(content) / self._word_bsize != self._exp
        if 0 < exp != len(content) / self._word_bsize:
            raise PartialFieldError(
                self.__class__.__name__, len(content) / (exp * self._word_bsize)
            )

        return content

    def __getitem__(self, word_index: int | slice) -> int | float | npt.NDArray:
        """
        Returns from the field a word or a slice of words unpacked in fmt.

        Parameters
        ----------
        word_index: int or slice
            requared word(s).

        Returns
        -------
        int of float
            unpacked word(s).
        """
        return self.unpack()[word_index]

    def __iter__(self) -> Generator[int | float, None, None]:
        """
        Iterating over words unpacked in fmt.

        Yields
        ------
        int or float
            unpacked word.
        """
        for word in self.unpack():
            yield word

    def __str__(self) -> str:
        """
        Returns a string representing the content in a readable format.

        When converting, left insignificant zeros are removed and
        a space separator between words.

        Returns
        -------
        str
            content as readable string.
        """
        return " ".join("%X" % word for word in self)

    def __repr__(self) -> str:
        """Returns string representation of the field instance"""
        words_count = self.words_count
        if words_count > 16:
            self_str = "{} ...({})".format(
                " ".join(str(self).split(" ")[:8]), words_count - 8
            )
        else:
            self_str = str(self)
        return f"<{self.__class__.__name__}({self_str}, fmt='{self._fmt}')>"


class SingleField(Field):
    """
    Represents a field of a Message with single word.

    Parameters
    ----------
    format_name: str
        the name of package format to which the field belongs.
    name: str
        the name of the field.
    info: dict of {str, Any}, optional
        additional info about a field.
    start_byte: int
        the number of bytes in the message from which the fields begin.
    fmt: str
        format for packing or unpacking the content. The word length
        is calculated from the format.
    may_be_empty: bool, default=False
        if True then field can be empty in a message.
    parent: MessageType or None
        parent message.

    Notes
    -----
    The __getitem__ method was disallowed because only one word is expected.

    See Also
    --------
    Field: parent class.
    """

    def __init__(
            self,
            format_name: str,
            name: str,
            *,
            start_byte: int,
            fmt: str,
            info: dict[str, Any] = None,
            default: ContentType = b"",
            may_be_empty: bool = False,
            parent=None,
    ):
        Field.__init__(
            self,
            format_name,
            name,
            start_byte=start_byte,
            expected=1,
            fmt=fmt,
            info=info,
            default=default,
            may_be_empty=may_be_empty,
            parent=parent
        )

    def get_setter(self): # nodesc
        return FieldSetter.single(
            fmt=self._fmt,
            default=self.unpack_default(),
            info=self._info,
            may_be_empty=self._may_be_empty
        )


class StaticField(SingleField):
    """
    Represents a field of a Message with static single word (e.g. preamble).

    Parameters
    ----------
    format_name: str
        the name of package format to which the field belongs.
    name: str
        the name of the field.
    info: dict of {str, Any}, optional
        additional info about a field.
    start_byte: int
        the number of bytes in the message from which the fields begin.
    fmt: str
        format for packing or unpacking the content. The word length
        is calculated from the format.
    default: Content, default=b""
        field content.
    parent: MessageType or None
        parent message.

    Notes
    -----
    The __getitem__ method was disallowed because only one word is expected.

    See Also
    --------
    FieldSingle: parent class.
    """

    def __init__(
            self,
            format_name: str,
            name: str,
            *,
            start_byte: int,
            fmt: str,
            default: ContentType,
            info: dict[str, Any] | None = None,
            parent=None,
    ):
        SingleField.__init__(
            self,
            format_name,
            name,
            start_byte=start_byte,
            fmt=fmt,
            info=info,
            parent=parent
        )
        self.set(default)

    def get_setter(self): # nodesc
        return FieldSetter.static(
            fmt=self._fmt,
            default=self.unpack_default(),
            info=self._info,
        )

    def set(self, content: ContentType) -> None:
        content = self._convert_content(content)
        if content == b"":
            pass
        elif self._content != b"" and content != self._content:
            raise ValueError(
                "The current content of the static field is different from "
                "the new content: %r != %r" % (self._content, content)
            )
        else:
            self._content = self._validate_content(content)


class AddressField(SingleField):
    """
    Represents a field of a Message with address.

    Parameters
    ----------
    format_name: str
        the name of package format to which the field belongs.
    info: dict of {str, Any}, optional
        additional info about a field.
    start_byte: int
        the number of bytes in the message from which the fields begin.
    fmt: str
        format for packing or unpacking the content. The word length
        is calculated from the format.
    parent: MessageType or None
        parent message.

    See Also
    --------
    FieldSingle: parent class.
    """

    def __init__(
            self,
            format_name: str,
            *,
            start_byte: int,
            fmt: str,
            info: dict[str, Any] | None = None,
            parent=None,
    ):
        SingleField.__init__(
            self,
            format_name,
            "address",
            start_byte=start_byte,
            fmt=fmt,
            info=info,
            parent=parent
        )

    def get_setter(self): # nodesc
        return FieldSetter.address(
            fmt=self._fmt,
            info=self._info,
        )


class DataField(Field):
    """
    Represents a field of a Message with data.

    Parameters
    ----------
    format_name: str
        the name of package format to which the field belongs.
    info: dict of {str, Any}, optional
        additional info about a field.
    start_byte: int
        the number of bytes in the message from which the fields begin.
    fmt: str
        format for packing or unpacking the content. The word length
        is calculated from the format.
    parent: MessageType or None
        parent message.

    See Also
    --------
    Field: parent class.
    """

    def __init__(
            self,
            format_name: str,
            *,
            start_byte: int,
            expected: int,
            fmt: str,
            info: dict[str, Any] | None = None,
            parent=None
    ):
        Field.__init__(
            self,
            format_name,
            "data",
            start_byte=start_byte,
            expected=expected,
            fmt=fmt,
            info=info,
            may_be_empty=True,
            parent=parent
        )

    def append(self, content: ContentType) -> None:
        content = self._convert_content(content)
        if self._exp > 0:
            exp = self._exp + len(content) // self._word_bsize
        else:
            exp = None
        self._content = self._validate_content(
            self._content + content, exp=exp
        )
        if self._exp > 0:
            self._exp = exp

    def get_setter(self): # nodesc
        return FieldSetter.data(
            expected=self._exp,
            fmt=self._fmt,
            info=self._info,
        )


class DataLengthField(SingleField):
    """
    Represents a field of a Message with data length.

    Parameters
    ----------
    format_name: str
        the name of package format to which the field belongs.
    info: dict of {str, Any}, optional
        additional info about a field.
    start_byte: int
        the number of bytes in the message from which the fields begin.
    fmt: str
        format for packing or unpacking the content. The word length
        is calculated from the format.
    units: int
        data length units. Data can be measured in bytes or words.
    additive: int
        additional value to the length of the data.
    parent: MessageType or None
        parent message.

    Raises
    ------
    ValueError
        if units not in {BYTES, WORDS}.
    ValueError
        if additive value is not integer or negative.

    See Also
    --------
    SingleField: parent class.
    """

    BYTES = 0x10
    WORDS = 0x11

    def __init__(
            self,
            format_name: str,
            *,
            start_byte: int,
            fmt: str,
            units: int = BYTES,
            additive: int = 0,
            info: dict[str, Any] | None = None,
            parent=None
    ):
        if units not in (self.BYTES, self.WORDS):
            raise ValueError("invalid units: %d" % units)
        if additive < 0 or not isinstance(additive, int):
            raise ValueError(
                "additive number must be integer and positive, "
                f"got {additive}"
            )

        SingleField.__init__(
            self,
            format_name,
            "data_length",
            start_byte=start_byte,
            fmt=fmt,
            info=info,
            parent=parent
        )
        self._units = units
        self._add = additive

    def calculate(self, data: DataField) -> int:
        """
        Calculate data length via data field.

        Parameters
        ----------
        data: DataField
            data field.

        Returns
        -------
        int
            actual length of data field.

        Raises
        ------
        ValueError
            if units not in {BYTES, WORDS}.
        """

        if self._units == self.BYTES:
            return len(data) + self._add
        elif self._units == self.WORDS:
            return data.words_count + self._add
        else:
            raise ValueError(f"invalid units: {self._units}")

    def get_setter(self): # nodesc
        return FieldSetter.data_length(
            fmt=self._fmt,
            units=self._units,
            additive=self._add,
            info=self._info,
        )

    def update(self) -> None:
        """
        Update data length content via parent message.

        Raises
        ------
        ValueError
            if units not in {BYTES, WORDS}.
        """
        if self._parent is None:
            raise ValueError("There is no parent message")
        self.set(self.calculate(self._parent.data))

    @property
    def units(self) -> int:
        """Data length units."""
        return self._units

    @property
    def additive(self) -> int:
        """Additional value to the data length."""
        return self._add


class OperationField(SingleField):
    """
    Represents a field of a Message with operation (e.g. read).

    Field operation contains operation codes:
        * READ = "r" -- read operation;
        * WRITE = "w" -- write operation;
        * ERROR = "e" -- error operation.
    Operation codes are needed to compare the base of the operation
    (the first letter of desc) when receiving a message and
    generally to understand what operation is written in the message.

    To work correctly, the first letter of keys in desc_dict must be
    one of {'r', 'w', 'e'} (see examples). If the dictionary is None,
    the standard value will be assigned {'r': 0, 'w': 1, 'e': 2}.

    Parameters
    ----------
    format_name: str
        the name of package format to which the field belongs.
    info: dict of {str, Any}, optional
        additional info about a field.
    start_byte: int
        the number of bytes in the message from which the fields begin.
    fmt: str
        format for packing or unpacking the content. The word length
        is calculated from the format.
    desc_dict: dict of {str, int}, optional
        dictionary of correspondence between the operation base and
        the value in the content.
    parent: MessageType or None
        parent message.

    Notes
    -----
    The __getitem__ method was disallowed because only one word is expected.

    See Also
    --------
    FieldSingle: parent class.

    Examples
    --------
    Example of po
    """

    READ = "r"
    WRITE = "w"
    ERROR = "e"

    def __init__(
            self,
            format_name: str,
            *,
            start_byte: int,
            fmt: str,
            desc_dict: dict[str, int] = None,
            info: dict[str, Any] | None = None,
            parent=None,
    ):
        if desc_dict is None:
            self._desc_dict = {"r": 0, "w": 1, "e": 2}
        else:
            self._desc_dict = desc_dict
        self._desc_dict_r = {v: k for k, v in self._desc_dict.items()}

        SingleField.__init__(
            self,
            format_name,
            "operation",
            start_byte=start_byte,
            fmt=fmt,
            info=info,
            parent=parent
        )
        self._desc = ""

    def get_setter(self): # nodesc
        return FieldSetter.operation(
            fmt=self._fmt,
            desc_dict=self._desc_dict,
            info=self._info,
        )

    def update_desc(self) -> None:
        """Update desc by desc dict where key is a content value."""
        c_value = self.unpack()
        if len(c_value):
            self._desc = self._desc_dict_r[c_value[0]]
        else:
            self._desc = ""

    def compare(self, other) -> bool:
        """
        Compare operations between self and other.

        Parameters
        ----------
        other: str or OperationField or MessageType
            object for comparsion.

        Returns
        -------
        bool
            result of comparsion using == operator.

        Raises
        ------
        TypeError:
            if other is not instanse string, FieldOperation or MessageType.
        """
        if isinstance(other, str):
            base = other[0]
        elif isinstance(other, OperationField):
            base = other.base
        elif isinstance(other, MessageType):
            base = other.operation.base
        else:
            raise TypeError("invalid class for comparsion: %s" % type(other))

        return self.base == base

    def set(self, content: ContentType | str) -> None:
        if isinstance(content, str):
            c_value = self._desc_dict[content]
        else:
            c_value = content
        SingleField.set(self, c_value)
        self.update_desc()

    @property
    def base(self) -> str:
        """Operation base (fisrt letter of desc) or
        empty if content is empty."""
        return self._desc[0] if len(self._desc) else ""

    @property
    def desc(self) -> str:
        """Operation description. Can contain several letters."""
        return self._desc

    @property
    def desc_dict(self) -> dict[str, int]:
        """Dictionary of correspondence between the base content value."""
        return self._desc_dict

    @property
    def desc_dict_r(self) -> dict[int, str]:
        """Reversed desc_dict."""
        return self._desc_dict_r

    def __eq__(self, other) -> bool:
        """
        Compare operations between self and other.

        Parameters
        ----------
        other: str, FieldOperation or MessageType
            object for comparsion.

        Returns
        -------
        bool
            result of comparsion using == operator.

        See Also
        --------
        compare: comparsion method.
        """
        return self.compare(other)

    def __ne__(self, other) -> bool:
        """
        Compare operations between self and other.

        Parameters
        ----------
        other: str, FieldOperation or MessageType
            object for comparsion.

        Returns
        -------
        bool
            result of comparsion using != operator.

        See Also
        --------
        compare: comparsion method.
        """
        return not self.compare(other)


class FieldSetter(object):

    BYTES = DataLengthField.BYTES
    WORDS = DataLengthField.WORDS

    def __init__(
            self,
            special: str = None,
            **kwargs: Any,
    ):
        self.special = special
        if "default" in kwargs and isinstance(kwargs["default"], bytes):
            raise TypeError(
                "%s not recomended bytes type for 'default' argument" % type(
                    kwargs["default"]
                )
            )
        self.kwargs = kwargs

    @classmethod
    def base(
            cls,
            *,
            expected: int,
            fmt: str,
            default: ContentType = None,
            info: dict[str, Any] = None,
            may_be_empty: bool = False,
    ):
        """For classical field"""
        if default is None:
            default = []
        return cls(
            expected=expected,
            fmt=fmt,
            default=default,
            info=info,
            may_be_empty=may_be_empty
        )

    @classmethod
    def single(
            cls,
            *,
            fmt: str,
            default: ContentType = None,
            info: dict[str, Any] = None,
            may_be_empty: bool = False,
    ):
        if default is None:
            default = []
        return cls(
            special="single",
            fmt=fmt,
            default=default,
            info=info,
            may_be_empty=may_be_empty
        )

    @classmethod
    def static(
            cls,
            *,
            fmt: str,
            default: ContentType,
            info: dict[str, Any] = None,
    ):
        return cls(
            special="static",
            fmt=fmt,
            default=default,
            info=info,
        )

    @classmethod
    def address(
            cls,
            *,
            fmt: str,
            info: dict[str, Any] | None = None
    ):
        return cls(fmt=fmt, info=info)

    @classmethod
    def data(
            cls,
            *,
            expected: int,
            fmt: str,
            info: dict[str, Any] | None = None
    ):
        return cls(expected=expected, fmt=fmt, info=info)

    @classmethod
    def data_length(
            cls,
            *,
            fmt: str,
            units: int = BYTES,
            additive: int = 0,
            info: dict[str, Any] | None = None
    ):
        return cls(fmt=fmt, units=units, additive=additive, info=info)

    @classmethod
    def operation(
            cls,
            *,
            fmt: str,
            desc_dict: dict[str, int] = None,
            info: dict[str, Any] | None = None
    ):
        return cls(fmt=fmt, desc_dict=desc_dict, info=info)

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        kwargs = ", ".join(f"{k}={v}" for k, v in self.kwargs.items())
        if len(kwargs):
            kwargs = ", " + kwargs
        return f"<{cls_name}(special={self.special}{kwargs})>"

    __str__ = __repr__


@runtime_checkable
class MessageType(Protocol):

    @property
    def address(self) -> AddressField:
        return AddressField("", start_byte=0, fmt="i")

    @property
    def data(self) -> DataField:
        return DataField(
            "",
            start_byte=0,
            expected=-1,
            fmt="i"
        )

    @property
    def data_length(self) -> DataLengthField:
        return DataLengthField("", start_byte=0, fmt="i")

    @property
    def operation(self):
        return OperationField("", start_byte=0, fmt="i")


FieldType = (
        Field |
        SingleField |
        StaticField |
        AddressField |
        DataField |
        DataLengthField |
        OperationField
)

