import shutil
import unittest
from typing import Any

import numpy as np

from src.pyiak_instr.core import Code
from src.pyiak_instr.store import (
    BytesField,
    ContinuousBytesStorage,
    BytesFieldPattern,
    BytesStoragePattern,
)
from src.pyiak_instr.exceptions import NotConfiguredYet

from ..data_bin import (
    get_cbs_one,
    get_cbs_example,
    get_cbs_one_infinite,
    get_cbs_first_infinite,
    get_cbs_middle_infinite,
    get_cbs_last_infinite,
)
from ..env import get_local_test_data_dir
from ...utils import validate_object, compare_values

TEST_DATA_DIR = get_local_test_data_dir(__name__)

class TestBytesField(unittest.TestCase):

    def test_init(self) -> None:
        validate_object(
            self,
            BytesField(
                start=4,
                fmt=Code.U32,
                expected=-100,
            ),
            bytes_expected=0,
            default=b"",
            expected=0,
            fmt=Code.U32,
            infinite=True,
            order=Code.BIG_ENDIAN,
            slice=slice(4, None),
            start=4,
            stop=None,
            word_size=4,
            check_attrs=True,
        )

    def test_decode(self) -> None:
        obj = BytesField(
            start=4,
            fmt=Code.U32,
            expected=-100,
        )
        cases = (
            (b"\x00\x00\x00\x01", 1),
            (b"\x00\x00\x00\x01\x00\x00\x00\x02", [1, 2]),
            (b"\x00\x00\x00\x01\x00\x00\x00\x22", np.array([1, 0x22])),
        )
        for i_case, (data, ref) in enumerate(cases):
            with self.subTest(test=i_case):
                compare_values(self, ref, obj.decode(data))

    def test_encode(self) -> None:
        obj = BytesField(
            start=4,
            fmt=Code.U32,
            expected=-100,
            order=Code.BIG_ENDIAN,
        )
        cases = (
            (1, b"\x00\x00\x00\x01"),
            ([1, 2], b"\x00\x00\x00\x01\x00\x00\x00\x02"),
            (np.array([1, 0x22]), b"\x00\x00\x00\x01\x00\x00\x00\x22"),
        )
        for i_case, (data, ref) in enumerate(cases):
            with self.subTest(test=i_case):
                compare_values(self, ref, obj.encode(data))

    def test_validate(self) -> None:
        obj = BytesField(
            start=0,
            fmt=Code.I16,
            expected=2,
            order=Code.DEFAULT,
        )
        with self.subTest(test="finite True"):
            self.assertTrue(obj.validate(b"\x02\x04\x00\x00"))
        with self.subTest(test="finite False"):
            self.assertFalse(obj.validate(b"\x02\x04\x00\x00\x01"))

        obj = BytesField(
            start=0,
            fmt=Code.I16,
            expected=-1,
            order=Code.LITTLE_ENDIAN,
        )
        with self.subTest(test="infinite True"):
            self.assertTrue(obj.validate(b"\x02\x04\x00\x00"))
        with self.subTest(test="infinite False"):
            self.assertFalse(obj.validate(b"\x02\x04\x00"))

    def test_stop_after_infinite(self) -> None:
        data = (
            (BytesField(
                start=-4,
                fmt=Code.I16,
                expected=1,
                order=Code.DEFAULT,
            ), -2),
            (BytesField(
                start=-2,
                fmt=Code.I16,
                expected=1,
                order=Code.DEFAULT,
            ), None)
        )

        for i, (obj, ref) in enumerate(data):
            with self.subTest(test=i):
                self.assertEqual(ref, obj.stop)


class TestBytesFieldParser(unittest.TestCase):

    def test_init(self) -> None:
        validate_object(
            self,
            self._get_cbs()["f0"],
            content=b"",
            name="f0",
            words_count=0,
            wo_attrs=["fld"],
        )

    def test_decode(self) -> None:
        compare_values(self, [], self._get_cbs()["f0"].decode())

    @staticmethod
    def _get_cbs() -> ContinuousBytesStorage:
        return ContinuousBytesStorage(
                name="cbs",
                f0=BytesField(
                    start=0,
                    fmt=Code.U32,
                    expected=-1,
                    order=Code.BIG_ENDIAN,
                )
            )


class TestContinuousBytesStorage(unittest.TestCase):

    def test_init(self) -> None:
        obj = self._get_cbs()
        ref_data = dict(
            f0=dict(
                content=b"",
                name="f0",
                words_count=0,
            ),
        )

        validate_object(self, obj, content=b"", name="cbs")
        for name, ref in ref_data.items():
            validate_object(self, obj[name], **ref, wo_attrs=["fld"])

    def test_init_exc(self) -> None:
        with self.assertRaises(TypeError)as exc:
            ContinuousBytesStorage(name="", f0={})
        self.assertEqual(
            "invalid type of 'f0': <class 'dict'>", exc.exception.args[0]
        )

    def test_extract(self) -> None:

        def get_storage_pars(
                content: bytes,
                name: str,
        ) -> dict[str, Any]:
            return dict(
                content=content,
                name=name,
            )

        def get_field_pars(
                content: bytes,
                words_count: int,
        ) -> dict[str, Any]:
            return dict(
                content=content,
                words_count=words_count,
                wo_attrs=["fld", "name"],
            )

        data = dict(
            one=dict(
                obj=get_cbs_one(),
                data=b"\x00\x01\xff\xff",
                validate_storage=get_storage_pars(
                    b"\x00\x01\xff\xff", "cbs_one"
                ),
                validate_fields=dict(
                    f0=get_field_pars(b"\x00\x01\xff\xff", 2),
                ),
                decode=dict(
                    f0=[1, -1],
                ),
            ),
            one_infinite=dict(
                obj=get_cbs_one_infinite(),
                data=b"\xef\x01\xff",
                validate_storage=get_storage_pars(
                    b"\xef\x01\xff", "cbs_one_infinite"
                ),
                validate_fields=dict(
                    f0=get_field_pars(b"\xef\x01\xff", 3),
                ),
                decode=dict(
                    f0=[-17, 1, -1],
                ),
            ),
            first_infinite=dict(
                obj=get_cbs_first_infinite(),
                data=b"\xef\x01\xff\xff\x0f\xab\xdd",
                validate_storage=get_storage_pars(
                    b"\xef\x01\xff\xff\x0f\xab\xdd", "cbs_first_infinite"
                ),
                validate_fields=dict(
                    f0=get_field_pars(b"\xef\x01\xff", 3),
                    f1=get_field_pars(b"\xff\x0f", 1),
                    f2=get_field_pars(b"\xab\xdd", 2),
                ),
                decode=dict(
                    f0=[-17, 1, -1],
                    f1=[0xFF0F],
                    f2=[0xAB, 0xDD],
                ),
            ),
            middle_infinite=dict(
                obj=get_cbs_middle_infinite(),
                data=b"\xef\x01\xff\xff\x01\x02\x03\x04\xab\xdd",
                validate_storage=get_storage_pars(
                    b"\xef\x01\xff\xff\x01\x02\x03\x04\xab\xdd",
                    "cbs_middle_infinite",
                ),
                validate_fields=dict(
                    f0=get_field_pars(b"\xef\x01\xff\xff", 2),
                    f1=get_field_pars(b"\x01\x02\x03\x04", 2),
                    f2=get_field_pars(b"\xab\xdd", 2),
                ),
                decode=dict(
                    f0=[0x1EF, 0xFFFF],
                    f1=[0x102, 0x304],
                    f2=[0xAB, 0xDD],
                ),
            ),
            last_infinite=dict(
                obj=get_cbs_last_infinite(),
                data=b"\xab\xcd\x00\x00\x01\x02\x03\x04\x00\x00",
                validate_storage=get_storage_pars(
                    b"\xab\xcd\x00\x00\x01\x02\x03\x04\x00\x00",
                    "cbs_last_infinite",
                ),
                validate_fields=dict(
                    f0=get_field_pars(b"\xab\xcd", 1),
                    f1=get_field_pars(b"\x00\x00\x01\x02\x03\x04\x00\x00", 2),
                ),
                decode=dict(
                    f0=[0xCDAB],
                    f1=[0x102, 0x3040000],
                ),
            ),
        )

        for short_name, comp in data.items():
            with self.subTest(test=short_name):
                obj = comp["obj"]
                comp_storage = comp["validate_storage"]
                comp_fields = comp["validate_fields"]
                comp_decode = comp["decode"]

                obj.extract(comp["data"])
                validate_object(self, obj, **comp_storage)
                for field in obj:
                    validate_object(self, field, **comp_fields[field.name])

                with self.subTest(sub_test="decode"):
                    self.assertListEqual(
                        list(comp_decode), [f.name for f in obj]
                    )
                    for f_name, decoded in obj.decode().items():
                        with self.subTest(field=f_name):
                            compare_values(self, comp_decode[f_name], decoded)

    def test_set_replace(self) -> None:
        obj = get_cbs_example()
        obj.set(f0=1, f1=[2, 3], f3=[4, 5], f4=6)
        self.assertEqual(b"\x00\x01\x02\x03\x04\x05\x06", obj.content)
        obj.set(f2=b"\xff\xfe\xfd")
        self.assertEqual(
            b"\x00\x01\x02\x03\xff\xfe\xfd\x04\x05\x06",
            obj.content,
        )
        obj.set(f0=32)
        self.assertEqual(
            b"\x00\x20\x02\x03\xff\xfe\xfd\x04\x05\x06",
            obj.content,
        )
        obj.set(f2=b"new content")
        self.assertEqual(
            b"\x00\x20\x02\x03new content\x04\x05\x06",
            obj.content,
        )

    def test_set_exc(self) -> None:
        with self.subTest(exception="missing or extra"):
            with self.assertRaises(AttributeError) as exc:
                get_cbs_example().set(f0=1, f1=2, f4=5, f8=1)
            self.assertEqual(
                "missing or extra fields were found: ['f3', 'f8']",
                exc.exception.args[0],
            )

        with self.subTest(exception="invalid new content"):
            with self.assertRaises(ValueError) as exc:
                get_cbs_example().set(f0=1, f1=[2, 3, 4], f3=1, f4=5)
            self.assertEqual(
                "'02 03 04' is not correct for 'f1'", exc.exception.args[0]
            )

    def test_magic_contains(self) -> None:
        self.assertIn("f0", self._get_cbs())

    def test_magic_getitem(self) -> None:
        self.assertEqual("f0", self._get_cbs()["f0"].name)

    def test_magic_iter(self) -> None:
        for ref, res in zip(("f0",), self._get_cbs()):
            with self.subTest(ref=ref):
                self.assertEqual(ref, res.name)

    @staticmethod
    def _get_cbs() -> ContinuousBytesStorage:
        return ContinuousBytesStorage(
            name="cbs",
            f0=BytesField(
                start=0,
                fmt=Code.U32,
                expected=1,
            ),
        )


class TestBytesFieldPattern(unittest.TestCase):

    def test_add(self) -> None:
        pattern = self._get_pattern()
        self.assertNotIn("e", pattern)
        pattern.add("e", 223)
        self.assertIn("e", pattern)

    def test_add_exc(self) -> None:
        with self.assertRaises(KeyError) as exc:
            self._get_pattern().add("a", 1)
        self.assertEqual("parameter in pattern already", exc.exception.args[0])

    def test_get(self) -> None:
        pattern = BytesFieldPattern(
            fmt=Code.U8,
            order=Code.DEFAULT,
            expected=4,
        )
        validate_object(
            self,
            pattern.get(start=4),
            start=4,
            fmt=Code.U8,
            order=Code.DEFAULT,
            expected=4,
            check_attrs=False,
        )

    def test_get_updated(self) -> None:
        pattern = BytesFieldPattern(
            fmt=Code.U8,
            expected=4,
        )
        with self.assertRaises(TypeError) as exc:
            pattern.get(start=0, expected=1)
        self.assertIn(
            "got multiple values for keyword argument 'expected'",
            exc.exception.args[0],
        )

        validate_object(
            self,
            pattern.get_updated(start=0, expected=1),
            start=0,
            expected=1,
            check_attrs=False,
        )

    def test_pop(self) -> None:
        pattern = self._get_pattern()
        self.assertIn("a", pattern)
        self.assertEqual(1, pattern.pop("a"))
        self.assertNotIn("a", pattern)

    def test_magic_contains(self) -> None:
        self.assertIn("a", self._get_pattern())

    def test_magic_getitem(self) -> None:
        self.assertEqual(1, self._get_pattern()["a"])

    def test_magic_setitem(self) -> None:
        pattern = self._get_pattern()
        self.assertListEqual([], pattern["b"])
        pattern["b"] = 1
        self.assertEqual(1, pattern["b"])

    def test_magic_setitem_exc(self) -> None:
        pattern = self._get_pattern()
        with self.assertRaises(KeyError) as exc:
            pattern["e"] = 1
        self.assertEqual("'e' not in parameters", exc.exception.args[0])

    @staticmethod
    def _get_pattern() -> BytesFieldPattern:
        return BytesFieldPattern(
            a=1,
            b=[],
            c={},
            d="string"
        )


class TestBytesStoragePattern(unittest.TestCase):

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(TEST_DATA_DIR.parent)

    def test_init(self) -> None:
        validate_object(
            self,
            BytesStoragePattern(name="cbs", kwarg="None"),
            name="cbs",
        )

    def test_get_continuous(self) -> None:
        data = b"\xaa\x55\xab\xcd\x11\x22\x33\x44\x55\xdc\xbb\x99"
        ref = dict(
            validate_storage=dict(
                content=b"\xaa\x55\xab\xcd\x11\x22\x33\x44\x55\xdc\xbb\x99",
                name="cbs_example"
            ),
            validate_fields=dict(
                f0=dict(
                    content=b"\xaa\x55",
                    words_count=1,
                    wo_attrs=["name", "fld"],
                ),
                f1=dict(
                    content=b"\xab\xcd",
                    words_count=2,
                    wo_attrs=["name", "fld"],
                ),
                f2=dict(
                    content=b"\x11\x22\x33\x44\x55",
                    words_count=5,
                    wo_attrs=["name", "fld"],
                ),
                f3=dict(
                    content=b"\xdc\xbb",
                    words_count=2,
                    wo_attrs=["name", "fld"],
                ),
                f4=dict(
                    content=b"\x99",
                    words_count=1,
                    wo_attrs=["name", "fld"],
                ),
            ),
            field_slices=dict(
                f0=slice(0, 2),
                f1=slice(2, 4),
                f2=slice(4, -3),
                f3=slice(-3, -1),
                f4=slice(-1, None),
            ),
            decode=dict(
                f0=[0xAA55],
                f1=[0xAB, 0xCD],
                f2=[0x11, 0x22, 0x33, 0x44, 0x55],
                f3=[0xDC, 0xBB],
                f4=[-103],
            ),
        )

        pattern = self._get_example_pattern()
        res = pattern.get()
        res.extract(data)

        ref_storage = ref["validate_storage"]
        ref_fields = ref["validate_fields"]
        ref_slice = ref["field_slices"]
        ref_decode = ref["decode"]

        validate_object(self, res, **ref_storage)
        for field in res:
            validate_object(self, field, **ref_fields[field.name])

        with self.subTest(sub_test="slice"):
            self.assertListEqual(list(ref_slice), [f.name for f in res])
            for parser in res:
                with self.subTest(field=parser.name):
                    compare_values(
                        self, ref_slice[parser.name], parser.fld.slice
                    )

        with self.subTest(sub_test="decode"):
            self.assertListEqual(list(ref_decode), [f.name for f in res])
            for f_name, decoded in res.decode().items():
                with self.subTest(field=f_name):
                    compare_values(self, ref_decode[f_name], decoded)

    def test_get_exc(self) -> None:
        with self.assertRaises(NotConfiguredYet) as exc:
            BytesStoragePattern(name="test").get()
        self.assertEqual(
            "BytesStoragePattern not configured yet", exc.exception.args[0]
        )

    def test_to_from_config(self) -> None:
        path = TEST_DATA_DIR / "test.ini"
        ref = self._get_example_pattern()
        ref.to_config(path)
        res = BytesStoragePattern.from_config(path, "cbs_example")

        with self.subTest(test="storage"):
            self.assertDictEqual(ref._kw, res._kw)

        for (name, rf), (_, rs) in zip(ref, res):
            with self.subTest(test=name):
                for (par, rf_kw), rs_kw in zip(
                        rf._kw.items(), rs._kw.values()
                ):
                    with self.subTest(parameter=par):
                        self.assertEqual(rf_kw, rs_kw)
                        self.assertIsInstance(rs_kw, type(rf_kw))
        res.get()

    @staticmethod
    def _get_example_pattern() -> BytesStoragePattern:
        pattern = BytesStoragePattern(name="cbs_example")
        pattern.configure(
            f0=BytesFieldPattern(
                fmt=Code.U16,
                expected=1,
                order=Code.BIG_ENDIAN,
            ),
            f1=BytesFieldPattern(
                fmt=Code.U8,
                expected=2,
            ),
            f2=BytesFieldPattern(
                fmt=Code.I8,
                expected=-1,
            ),
            f3=BytesFieldPattern(
                fmt=Code.U8,
                expected=2,
            ),
            f4=BytesFieldPattern(
                fmt=Code.I8,
                expected=1,
            )
        )
        return pattern