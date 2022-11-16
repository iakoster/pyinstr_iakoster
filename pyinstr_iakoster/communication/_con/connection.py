import logging
import datetime as dt
from typing import Any

from .._message import (
    Message,
    AsymmetricResponseField,
    MessageContentError
)
from ...core import Code


# todo: check type annotation
__all__ = [
    "Connection"
]


class Connection(object):  # todo: description and tests
    """
    Represents base class for messaging with devices via ethernet, UART etc.

    Parameters
    ----------
    hapi: Any
        High-level API (e.g. socket, Serial etc.).
    address: Any or None, default=None
        connection address. If specified call .bind method with address.
    logger: logging.Logger or str or None, default=None
        logger for logging transmitted and received messages. Log to
        transferred logger or create new logger if is equal to 'self'.
        Raises ValueError if transferred string that not equal to 'self'.
    """

    def __init__(
            self,
            hapi: Any,
            address: Any | None = None,
            logger: logging.Logger | str | None = None
    ):
        if isinstance(logger, str) and logger != "self":
            raise ValueError("invalid logger: %s != 'self'" % logger)

        self._hapi = hapi
        self._logger = logging.getLogger(
            __name__
        ) if isinstance(logger, str) else logger

        if address is None:
            self._addr = None
        else:
            self.bind(address)

        self._tx_to = dt.timedelta(seconds=15)
        self._rx_to = dt.timedelta(seconds=5)

    def close(self) -> None:
        """
        Close the connection (hapi).
        """
        raise NotImplementedError()

    def receive(self) -> tuple[bytes, Any]:
        """
        Receive message from hapi.

        Returns
        -------
        tuple[bytes, Any]
            received message and the address where the message came from.
        """
        raise NotImplementedError()

    def setup(self, *args: Any, **kwargs: Any) -> "Connection":
        """
        Setup hapi.

        Parameters
        ----------
        args: Any
            some arguments for setup.
        kwargs: Any
            some keyword arguments for setup.

        Returns
        -------
        Connection
            self instance.
        """
        raise NotImplementedError()

    def transmit(self, message: Message) -> None:
        """
        Transmit message to hapi.

        Information for transmit can be taken from the message
        (e.g. destination address).

        Parameters
        ----------
        message: Message
            transmission message.
        """
        raise NotImplementedError()

    def _bind(self, address: Any) -> None:
        """
        Bind address to hapi.

        Parameters
        ----------
        address: Any
            destination address.
        """
        raise NotImplementedError()

    def bind(self, address: Any) -> "Connection":
        """
        Bind address.

        Also call ._bind method.

        Parameters
        ----------
        address: Any
            destination address.

        Returns
        -------
        Connection
            self instance.
        """
        self._addr = address
        self._bind(address)
        return self

    def send(
            self,
            message: Message,
            emark: AsymmetricResponseField = AsymmetricResponseField()
    ) -> Message:
        """
        Send message to dst (see Message.dst).

        Parameters
        ----------
        message: Message
            transmitted message.
        emark: MessageErrorMark, default=MessageErrorMark()
            error mark for asymmetric response. Can be obtained from
            the current message format.

        Returns
        -------
        Message
            response message
        """
        if self._addr is None:
            raise ConnectionError("no address specified")
        if message.src != self._addr:
            raise ConnectionError(
                "addresses in message and connection is not equal: "
                f"{message.src} != {self._addr}"
            )

        if message.operation.base == "w":
            answer = self._write(message, emark)
        elif message.operation.base == "r":
            answer = self._read(message, emark)
        else:
            raise MessageContentError(
                message.__class__.__name__,
                message.operation.name,
                clarification="unknown base"
            )
        return answer

    def set_timeouts(
            self,
            transmit_timeout: dt.timedelta | int = 15,
            receive_timeout: dt.timedelta | int = 5,
    ) -> None:
        """
        Set timeouts for waiting for a reply and sending a message.

        Parameters
        ----------
        transmit_timeout: datetime.timedelta or int, default=15
            the time for which the message transmission will be attempted
            until a response is received.
        receive_timeout: datetime.timedelta or int, default=15
            the time in which you expect to receive an answer.
        """
        if isinstance(transmit_timeout, int):
            transmit_timeout = dt.timedelta(seconds=transmit_timeout)
        if isinstance(receive_timeout, int):
            receive_timeout = dt.timedelta(seconds=receive_timeout)

        self._tx_to = transmit_timeout
        self._rx_to = receive_timeout

    def _log_info(self, entry: str) -> None:
        """
        Log entry to logger if logger is not None.

        Parameters
        ----------
        entry: str
            log entry.
        """
        if self._logger is not None:
            self._logger.info(entry)

    def _read(self, msg: Message, emark: AsymmetricResponseField) -> Message:
        """
        Send message with read operation.

        Splits source message into several via .split method.

        Parameters
        ----------
        msg: Message
            source message.
        emark: AsymmetricResponseField
            error mark for asymmetric response.

        Returns
        -------
        Message
            response with the sum of all data from all responses
            (when sending multiple messages using .split).
        """
        if not msg.splitable:
            return self._send(msg, emark)

        msg_gen = msg.split()
        answer = self._send(next(msg_gen), emark)
        for tx_msg in msg_gen:
            answer += self._send(tx_msg, emark)
        answer.set(data_length=msg.data_length.content)  # todo: .set in write. There is not needed?
        return answer

    def _send(self, msg: Message, emark: AsymmetricResponseField) -> Message:
        """
        Send message and get response.

        Uses .transmit for transmit message and .receive for receive message.

        Log every received message. Ignore messages received not from
        the expected address.

        Parameters
        ----------
        msg: Message
            message for sending.
        emark: AsymmetricResponseField
            asymmetric error field.

        Returns
        -------
        Message
            response message.

        Raises
        ------
        ConnectionError
            if the timeout (transmit timeout) is reached.
        """

        received = 0
        invalid_received = 0
        transmitted = 0
        transmit_start = dt.datetime.now()

        while (dt.datetime.now() - transmit_start) < self._tx_to:

            self.transmit(msg)
            transmitted += 1
            self._log_info(repr(msg))
            receive_start = dt.datetime.now()

            while (dt.datetime.now() - receive_start) < self._rx_to:

                try:
                    ans, rec_from = self.receive()
                    if len(ans) == 0:
                        continue
                    received += 1
                    self._log_info("{}, src={}, dst={}".format(
                        ans.hex(" "), rec_from, self._addr
                    ))

                except TimeoutError as exc:
                    self._log_info(repr(exc))

                else:
                    if msg.dst != rec_from:
                        invalid_received += 1
                        self._log_info(
                            f"message received from {rec_from}, "
                            f"but expected from {msg.dst}"
                        )
                        continue

                    ans, code = self._validate_bytes_message(msg, ans, emark)
                    if code == Code.ERROR:  # todo: if error transmit again
                        continue

                    code = self._validate_message(ans, emark)
                    self._log_info(repr(ans))

                    if code == Code.OK:
                        return ans
                    elif code == Code.WAIT:
                        receive_start = dt.datetime.now()
                    else:
                        invalid_received += 1
                        self._log_info(f"receive with code(s): %r" % code)

        raise ConnectionError(
            "time is up: "
            "received={}, invalid_received={}, transmitted={}".format(
                received, invalid_received, transmitted
            )
        )

    def _validate_bytes_message(
            self,
            tx_msg: Message,
            rx_msg: bytes,
            emark: AsymmetricResponseField,
    ) -> tuple[Message, Code]:
        """
        Validate raw received message.

        Code is OK if there is no errors and ERROR instead.

        Parameters
        ----------
        tx_msg: Message
            transmitted message.
        rx_msg: bytes
            raw received message.
        emark: AsymmetricResponseField
            asymmetric error mark.

        Returns
        -------
        tuple[Message, Code]
            message and code converted to a class (validation result).
        """
        emark_exists = False
        if emark.bytes_required:
            rx_msg, emark_exists = emark.match(rx_msg)
        # todo: check that bytes can be reformatted into a message
        rx_msg = tx_msg.get_same_instance().extract(rx_msg)\
            .set_src_dst(src=tx_msg.dst, dst=self._addr)

        if emark_exists:
            return rx_msg, Code.ERROR
        return rx_msg, Code.OK

    def _validate_message(
            self, rx_msg: Message, emark: AsymmetricResponseField
    ) -> Code | list[Code]:
        """
        validate converted to a class message.

        Parameters
        ----------
        rx_msg: Message
            received message.
        emark: AsymmetricResponseField
            asymmetric error mark.

        Returns
        -------
        Code | list[Code]
            validation result in code. If message have ResponseField returns
            code from it. Returns all codes if there are several
            ResponseField and not all equal.
        """

        codes = list(rx_msg.response_codes.values())
        if len(codes):
            if len(codes) == 1:
                return codes[0]

            ref_code = codes[0]
            for code in codes[1:]:
                if code != ref_code:
                    return codes
            return ref_code

        # else:
        #     return Code.OK  # todo: uncomment after fix emark

        emark_exists = False
        if not emark.bytes_required:
            _, emark_exists = emark.match(rx_msg)  # todo: remove, response codes do it

        if emark_exists:
            return Code.ERROR
        return Code.OK

    def _write(self, msg: Message, emark: AsymmetricResponseField) -> Message:
        """
        Send message with write operation.

        Splits source message into several via .split method.

        Parameters
        ----------
        msg: Message
            source message.
        emark: AsymmetricResponseField
            asymmetric error mark.

        Returns
        -------
        Message
            first response message with source data length.
        """
        if not msg.splitable:
            return self._send(msg, emark)

        msg_gen = msg.split()
        answer = self._send(next(msg_gen), emark)
        for tx_msg in msg_gen:
            self._send(tx_msg, emark)
        return answer

    @property
    def address(self) -> Any:
        """
        Returns
        -------
        Any
            connection address.
        """
        return self._addr

    @property
    def hapi(self) -> Any:
        """
        Returns
        -------
        Any
            high-level API (e.g. socket)
        """
        return self._hapi

    @property
    def receive_timeout(self) -> dt.timedelta:
        """
        Returns
        -------
        datetime.timedelta
            receive timeout.
        """
        return self._rx_to

    @property
    def transmit_timeout(self) -> dt.timedelta:
        """
        Returns
        -------
        datetime.timedelta
            transmit timeout.
        """
        return self._tx_to
