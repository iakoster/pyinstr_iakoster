import unittest

from src.pyiak_instr.core import Code

from .....utils import validate_object, get_object_attrs
from .ti import (
    TIMessageFieldStruct,
    TISingleMessageFieldStruct,
    TIStaticMessageFieldStruct,
    TIAddressMessageFieldStruct,
    TICrcMessageFieldStruct,
    TIDataMessageFieldStruct,
    TIDataLengthMessageFieldStruct,
    TIIdMessageFieldStruct,
    TIOperationMessageFieldStruct,
    TIResponseMessageFieldStruct,
    TIMessageStruct,
    TIMessage,
)


class TestMessageABC(unittest.TestCase):

    def test_init(self) -> None:
        validate_object(
            self,
            TIMessage(TIMessageStruct(fields=dict(
                f0=TIDataLengthMessageFieldStruct(
                    name="f0", stop=2, fmt=Code.U16
                ),
                f1=TIDataMessageFieldStruct(name="f1", start=2, fmt=Code.U32),
            ))),
            has_pattern=False,
            src=None,
            dst=None,
            wo_attrs=["struct", "get", "has"],
        )

    def test_init_exc(self) -> None:
        with self.assertRaises(TypeError) as exc:
            TIMessage(TIMessageStruct(
                fields={
                    "f0": TIAddressMessageFieldStruct(
                        name="f0", behaviour=Code.STRONG
                    ),
                    "f1": TIDataMessageFieldStruct(name="f1"),
                },
                divisible=True,
            ))
        self.assertEqual(
            "invalid address behaviour for divisible message: "
            "<Code.STRONG: 1540>",
            exc.exception.args[0],
        )

    def test_has(self) -> None:
        obj = TIMessage(TIMessageStruct(fields=dict(
            f0=TIMessageFieldStruct(name="f0", stop=1),
            f1=TISingleMessageFieldStruct(name="f1", start=1, stop=2),
            f2=TIStaticMessageFieldStruct(name="f2", start=2, stop=3, default=b"a"),
            f3=TIAddressMessageFieldStruct(name="f3", start=3, stop=4),
            f4=TICrcMessageFieldStruct(name="f4", start=4, stop=6, fmt=Code.U16),
            f5=TIDataMessageFieldStruct(name="f5", start=6, stop=-4),
            f6=TIDataLengthMessageFieldStruct(name="f6", start=-4, stop=-3),
            f7=TIIdMessageFieldStruct(name="f7", start=-3, stop=-2),
            f8=TIOperationMessageFieldStruct(name="f8", start=-2),
        )))

        validate_object(
            self,
            obj.has,
            basic=True,
            single=True,
            address=True,
            id_=True,
            data_length=True,
            response=False,
            static=True,
            crc=True,
            operation=True,
            data=True,
        )

        self.assertFalse(obj.has(Code.UNDEFINED))

    def test_get(self) -> None:
        obj = TIMessage(TIMessageStruct(fields=dict(
            f0=TIMessageFieldStruct(name="f0", stop=1),
            f1=TISingleMessageFieldStruct(name="f1", start=1, stop=2),
            f2=TIStaticMessageFieldStruct(name="f2", start=2, stop=3, default=b"a"),
            f3=TIAddressMessageFieldStruct(name="f3", start=3, stop=4),
            f4=TICrcMessageFieldStruct(name="f4", start=4, stop=6, fmt=Code.U16),
            f5=TIDataMessageFieldStruct(name="f5", start=6, stop=-4),
            f6=TIDataLengthMessageFieldStruct(name="f6", start=-4, stop=-3),
            f7=TIIdMessageFieldStruct(name="f7", start=-3, stop=-2),
            f8=TIOperationMessageFieldStruct(name="f8", start=-2, stop=-1),
            f9=TIResponseMessageFieldStruct(name="f9", start=-1)
        )))

        ref = dict(
            basic="f0",
            single="f1",
            address="f3",
            id_="f7",
            data_length="f6",
            response="f9",
            static="f2",
            crc="f4",
            operation="f8",
            data="f5",
        )
        get = obj.get
        for attr in get_object_attrs(get):
            with self.subTest(field=attr):
                self.assertEqual(ref[attr], getattr(get, attr).name)

    def test_src_dst(self) -> None:
        obj = TIMessage(TIMessageStruct(fields={
            "f0": TIDataLengthMessageFieldStruct(name="f0"),
        }))

        self.assertTupleEqual((None, None), (obj.src, obj.dst))
        obj.src = "123"
        obj.dst = 456
        self.assertTupleEqual(("123", 456), (obj.src, obj.dst))

#
#
# @STRUCT_DATACLASS
# class TIMessageFieldStruct(BytesFieldStruct):
#     ...
#
#
# class TIMessageField(MessageFieldABC["TIMessage", TIMessageFieldStruct]):
#     ...
#
#
# class TIMessageGetParser(MessageGetParserABC["TIMessage", TIMessageField]):
#
#     @property
#     def basic(self) -> TIMessageField:
#         return self(TIMessageField)
#
#
# class TIMessageHasParser(MessageHasParserABC[TIMessageField]):
#
#     @property
#     def basic(self) -> bool:
#         return self(TIMessageField)
#
#
# class TIMessage(
#     MessageABC[
#         "TIMessagePatternABC",
#         TIMessageField,
#         TIMessageFieldStruct,
#         TIMessageGetParser,
#         TIMessageHasParser,
#         str,
#     ]
# ):
#
#     _get_parser = TIMessageGetParser
#     _has_parser = TIMessageHasParser
#     _struct_field = {TIMessageFieldStruct: TIMessageField}
#
#     def split(self) -> Generator[Self, None, None]:
#         raise NotImplementedError()
#
#
# class TIMessageFieldPatternABC(MessageFieldPatternABC):
#
#     _options = {"basic": TIMessageFieldStruct}
#
#     @staticmethod
#     def get_bytesize(fmt: Code) -> int:
#         if fmt is Code.U8:
#             return 1
#         if fmt is Code.U16:
#             return 2
#         raise ValueError(f"invalid fmt: {repr(fmt)}")
#
#
# class TIMessagePatternABC(MessagePatternABC):
#
#     _options = {"basic": TIMessage}
#
#
#
# class TestMessageABC(unittest.TestCase):
#
#     def test_init(self) -> None:
#         validate_object(
#             self,
#             TIMessage({"f0": TIMessageFieldStruct()}),
#             content=b"",
#             divisible=False,
#             dst=None,
#             has_pattern=False,
#             is_dynamic=True,
#             minimum_size=0,
#             mtu=1500,
#             name="std",
#             src=None,
#             src_dst=(None, None),
#             wo_attrs=["get", "has"]
#         )
#
#     def test_init_exc(self) -> None:
#         with self.subTest(test="divisible without dynamic field"):
#             with self.assertRaises(TypeError) as exc:
#                 TIMessage(
#                     {"f0": TIMessageFieldStruct(bytes_expected=1)},
#                     divisible=True,
#                 )
#             self.assertEqual(
#                 "TIMessage can not be divided because it does not have "
#                 "a dynamic field",
#                 exc.exception.args[0],
#             )
#
#         with self.subTest(test="invalid mtu"):
#             with self.assertRaises(ValueError) as exc:
#                 TIMessage(
#                     {
#                         "f0": TIMessageFieldStruct(bytes_expected=10),
#                         "f1": TIMessageFieldStruct(fmt=Code.U16, start=10),
#                     },
#                     divisible=True,
#                     mtu=5,
#                 )
#             self.assertEqual(
#                 "MTU value does not allow you to split the message if "
#                 "necessary. The minimum MTU is 12 (got 5)",
#                 exc.exception.args[0],
#             )
#
#     def test_get_has(self) -> None:
#         instance = TIMessage(dict(
#             f0=TIMessageFieldStruct(stop=5),
#             f1=TIMessageFieldStruct(start=5),
#         ))
#
#         with self.subTest(test="get basic"):
#             self.assertEqual("f0", instance.get.basic.name)
#
#         with self.subTest(test="has basic"):
#             self.assertTrue(instance.has.basic)
#
#         with self.subTest(test="hasn't other"):
#             self.assertFalse(instance.has(MessageFieldABC))
#
#     def test_get_exc(self) -> None:
#         with self.assertRaises(TypeError) as exc:
#             TIMessage(
#                 {"f0": TIMessageFieldStruct()}, "test"
#             ).get(MessageFieldABC)
#         self.assertEqual(
#             "MessageFieldABC instance is not found", exc.exception.args[0]
#         )
#
#     def test_src_dst(self) -> None:
#         instance = TIMessage({"f0": TIMessageFieldStruct()})
#
#         self.assertTupleEqual((None, None), instance.src_dst)
#         instance.src_dst = None, "test"
#         self.assertTupleEqual((None, "test"), instance.src_dst)
#         instance.src = "alal"
#         self.assertEqual("alal", instance.src)
#         instance.dst = "test/2"
#         self.assertEqual("test/2", instance.dst)
#
#
# class TestMessagePatternABC(unittest.TestCase):
#
#     def test_get(self) -> None:
#         pattern = TIMessagePatternABC("basic", "test").configure(
#             f0=TIMessageFieldPatternABC("basic", bytes_expected=1),
#             f1=TIMessageFieldPatternABC(
#                 "basic", bytes_expected=2, fmt=Code.U16
#             ),
#             f2=TIMessageFieldPatternABC("basic", bytes_expected=0),
#             f3=TIMessageFieldPatternABC("basic", bytes_expected=2),
#             f4=TIMessageFieldPatternABC("basic", bytes_expected=4, fmt=Code.U16),
#         )
#         res = pattern.get()
#
#         validate_object(
#             self,
#             res,
#             content=b"",
#             divisible=False,
#             dst=None,
#             has_pattern=True,
#             is_dynamic=True,
#             minimum_size=9,
#             mtu=1500,
#             name="test",
#             src=None,
#             src_dst=(None, None),
#             pattern=pattern,
#             wo_attrs=["get", "has"]
#         )
#
#         for field, pars in dict(
#             f0=dict(
#                 fmt=Code.U8,
#                 slice_=slice(0, 1),
#                 words_expected=1,
#             ),
#             f1=dict(
#                 fmt=Code.U16,
#                 slice_=slice(1, 3),
#                 words_expected=1,
#             ),
#             f2=dict(
#                 fmt=Code.U8,
#                 slice_=slice(3, -6),
#                 words_expected=0,
#             ),
#             f3=dict(
#                 fmt=Code.U8,
#                 slice_=slice(-6, -4),
#                 words_expected=2,
#             ),
#             f4=dict(
#                 fmt=Code.U16,
#                 slice_=slice(-4, None),
#                 words_expected=2,
#             ),
#         ).items():
#             with self.subTest(field=field):
#                 validate_object(
#                     self,
#                     res[field].struct,
#                     **pars,
#                     wo_attrs=[
#                         "bytes_expected",
#                         "default",
#                         "has_default",
#                         "is_dynamic",
#                         "order",
#                         "start",
#                         "stop",
#                         "word_bytesize",
#                     ]
#                 )
