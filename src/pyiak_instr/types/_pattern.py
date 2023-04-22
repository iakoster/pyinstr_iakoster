"""Private module of ``pyiak_instr.types`` with pattern types."""
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Any, Generic, Self, TypeVar


__all__ = [
    "EditablePatternABC",
    "MetaPatternABC",
    "PatternABC",
    "WritablePatternABC",
]


OptionsT = TypeVar("OptionsT")  # Pattern target options
PatternT = TypeVar("PatternT", bound="PatternABC[Any]")


class PatternABC(ABC, Generic[OptionsT]):
    """
    Represents protocol for patterns.

    Parameters
    ----------
    typename: str
        name of pattern target type.
    **kwargs: Any
        parameters for target initialization.
    """

    _options: dict[str, type[OptionsT]]
    """pattern target options"""

    _only_auto_parameters: set[str] = set()

    # todo: parameters to TypedDict
    def __init__(self, typename: str, **parameters: Any) -> None:
        if typename not in self._options:
            raise KeyError(f"'{typename}' not in {set(self._options)}")
        self._tn = typename
        self._kw = parameters

    def get(
        self, changes_allowed: bool = False, **additions: Any
    ) -> OptionsT:
        """
        Get initialized class instance with parameters from pattern and from
        `additions`.

        Parameters
        ----------
        changes_allowed: bool, default = False
            allows situations where keys from the pattern overlap with kwargs.
            If False, it causes an error on intersection, otherwise the
            `additions` take precedence.
        **additions: Any
            additional initialization parameters.

        Returns
        -------
        OptionsT
            initialized target class.
        """
        return self._target(
            **self._get_parameters_dict(changes_allowed, additions)
        )

    def _get_parameters_dict(
        self, changes_allowed: bool, additions: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Get joined additions with pattern parameters.

        Parameters
        ----------
        changes_allowed : bool
            allows situations where keys from the pattern overlap with kwargs.
        additions : dict[str, Any]
            additional initialization parameters.

        Returns
        -------
        dict[str, Any]
            joined parameters.

        Raises
        ------
        SyntaxError
            if changes not allowed but parameter repeated in `additions`.
        TypeError
            if parameter in `additions` and pattern, but it must be to set
            automatically.
        """
        parameters = self._kw.copy()
        if len(additions) != 0:
            if not changes_allowed:
                intersection = set(parameters).intersection(set(additions))
                if len(intersection):
                    raise SyntaxError(
                        "keyword argument(s) repeated: "
                        f"{', '.join(intersection)}"
                    )

            parameters.update(additions)

        for auto_par in self._only_auto_parameters:
            if auto_par in parameters:
                raise TypeError(f"'{auto_par}' can only be set automatically")

        return parameters

    @property
    def typename(self) -> str:
        """
        Returns
        -------
        str
            name of pattern target type.
        """
        return self._tn

    @property
    def _target(self) -> type[OptionsT]:
        """
        Get target class by `type_name` or default if `type_name` not in
        options.

        Returns
        -------
        type[OptionsT]
            target class.
        """
        return self._options[self._tn]

    def __init_kwargs__(self) -> dict[str, Any]:
        return dict(typename=self._tn, **self._kw)

    def __contains__(self, name: str) -> bool:
        """Check that parameter in Pattern by name."""
        return name in self._kw

    def __eq__(self, other: object) -> bool:
        """
        Compare `__init_kwargs__` in two objects.

        Beware: not supports numpy arrays in __init_kwargs__.
        """
        if hasattr(other, "__init_kwargs__"):
            return (  # type: ignore[no-any-return]
                self.__init_kwargs__() == other.__init_kwargs__()
            )
        return False

    def __getitem__(self, name: str) -> Any:
        """Get parameter value"""
        return self._kw[name]


class EditablePatternABC(ABC):
    """
    Represents abstract class with methods to edit parameters.
    """

    _kw: dict[str, Any]

    def add(self, key: str, value: Any) -> None:
        """
        Add new parameter to the pattern.

        Parameters
        ----------
        key : str
            new parameter name.
        value : Any
            new parameter value.

        Raises
        ------
        KeyError
            if parameter name is already exists.
        """
        if key in self._kw:
            raise KeyError(f"parameter '{key}' in pattern already")
        self._kw[key] = value

    def pop(self, key: str) -> Any:
        """
        Extract parameter with removal.

        Parameters
        ----------
        key: str
            parameter name.

        Returns
        -------
        Any
            parameter value.
        """
        return self._kw.pop(key)

    def __setitem__(self, name: str, value: Any) -> None:
        """Change value of the existed parameter."""
        if name not in self._kw:
            raise KeyError(f"'{name}' not in parameters")
        self._kw[name] = value


class WritablePatternABC(ABC):
    """
    Represents protocol for patterns which supports read/write.
    """

    @abstractmethod
    def write(self, path: Path) -> None:
        """
        Write pattern init kwargs to the file at the `path`.

        Parameters
        ----------
        path: Path
            path to file.
        """

    @classmethod
    @abstractmethod
    def read(cls, path: Path, *keys: str) -> Self:
        """
        Read init kwargs from `path` and initialize class instance.

        Parameters
        ----------
        path : Path
            path to the file.
        *keys : str
            keys to search required pattern in file.

        Returns
        -------
        Self
            initialized self instance.
        """


class MetaPatternABC(
    PatternABC[OptionsT],
    Generic[OptionsT, PatternT],
):
    """
    Represent pattern which consist of other patterns.

    Used to create an instance of a compound object (i.e. the object contains
    other objects generated by the sub-patterns)

    Parameters
    ----------
    typename: str
        name of pattern target type.
    name: str
        name of pattern storage format.
    **kwargs: Any
        parameters for target initialization.
    """

    _sub_p: dict[str, PatternT]
    """list of sub patterns"""

    _sub_p_type: type[PatternT]
    """sub pattern type for initializing in class."""

    def __init__(self, typename: str, name: str, **kwargs: Any):
        super().__init__(typename, name=name, **kwargs)
        self._name = name
        self._sub_p = {}

    @abstractmethod
    def get(
        self, changes_allowed: bool = False, **additions: Any
    ) -> OptionsT:
        """
        Get initialized class instance with parameters from pattern and from
        `additions`.

        Parameters
        ----------
        changes_allowed: bool, default = False
            allows situations where keys from the pattern overlap with kwargs.
            If False, it causes an error on intersection, otherwise the
            `additions` take precedence.
        **additions: Any
            additional initialization parameters. Those keys that are
            separated by "__" will be defined as parameters for other
            patterns target, otherwise for the storage target.

        Returns
        -------
        OptionsT
            initialized target class.
        """

    def configure(self, **patterns: PatternT) -> Self:
        """
        Configure storage pattern with other patterns.

        Parameters
        ----------
        **patterns : PatternT
            dictionary of patterns where key is a pattern name.

        Returns
        -------
        Self
            self instance.
        """

        self._sub_p = patterns
        return self

    @property
    def name(self) -> str:
        """
        Returns
        -------
        str
            name of pattern storage.
        """
        return self._name
