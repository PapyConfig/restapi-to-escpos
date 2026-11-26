"""Asynchronous raw-TCP delivery of a rendered ESC/POS stream."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import defaultdict

from .config import PrinterConfig
from .errors import ApiError

log = logging.getLogger("escpos_api")


class PrinterUnreachable(ApiError):
    def __init__(self, printer: str) -> None:
        super().__init__(502, "printer_unreachable", f"Printer {printer!r} is unreachable.")


class PrinterTimeout(ApiError):
    def __init__(self, printer: str) -> None:
        super().__init__(504, "printer_timeout", f"Printer {printer!r} did not respond in time.")


GS_R_PAPER = b"\x1dr\x01"  # "transmit status": answered once everything before it is processed


class Transport:
    """Sends whole jobs to printers, one job at a time per printer.

    A printer acknowledges TCP data long before it has printed it. Closing too early loses or
    delays the end of a job (the end of a large image, the feed, the cut), which some printers
    only process when the next connection arrives: the cut then happens at the start of the
    next ticket. So, after sending a job:

    1. with `wait_done`, we send `GS r 1` and keep the connection open until the printer
       answers: it does so only after processing everything sent before (`done_timeout`);
    2. we half-close (FIN) and keep reading until the printer closes or `close_grace`
       expires: closing with unread incoming bytes would make the kernel send a TCP RST,
       and the printer would discard what it has not read yet.

    This happens after the HTTP response, but the printer stays locked until it ends, so the
    next job never overtakes the end of the previous one.
    """

    def __init__(
        self, timeout: float, close_grace: float = 5.0, done_timeout: float = 30.0
    ) -> None:
        self.timeout = timeout
        self.close_grace = close_grace
        self.done_timeout = done_timeout
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._lingering: set[asyncio.Task[None]] = set()

    async def send(self, printer: PrinterConfig, data: bytes) -> None:
        lock = self._locks[printer.name]
        await lock.acquire()
        writer: asyncio.StreamWriter | None = None
        try:
            async with asyncio.timeout(self.timeout):
                reader, writer = await asyncio.open_connection(printer.host, printer.port)
                incoming = _Incoming(reader)
                writer.write(data)
                await writer.drain()
        except BaseException as exc:
            if writer is not None:
                incoming.stop()
                writer.close()
            lock.release()
            if isinstance(exc, TimeoutError):
                raise PrinterTimeout(printer.name) from exc
            if isinstance(exc, OSError):
                raise PrinterUnreachable(printer.name) from exc
            raise
        task = asyncio.create_task(self._finish(printer, incoming, writer, lock))
        self._lingering.add(task)
        task.add_done_callback(self._lingering.discard)

    async def _finish(
        self,
        printer: PrinterConfig,
        incoming: _Incoming,
        writer: asyncio.StreamWriter,
        lock: asyncio.Lock,
    ) -> None:
        """Wait for the printer to process the job, then close gracefully."""
        try:
            if printer.wait_done:
                await self._wait_done(printer, incoming, writer)
            with contextlib.suppress(OSError):
                if writer.can_write_eof():
                    writer.write_eof()
            with contextlib.suppress(TimeoutError):
                async with asyncio.timeout(self.close_grace):
                    await incoming.closed.wait()
            incoming.stop()
            writer.close()
            with contextlib.suppress(OSError):
                await writer.wait_closed()
        finally:
            lock.release()

    async def _wait_done(
        self, printer: PrinterConfig, incoming: _Incoming, writer: asyncio.StreamWriter
    ) -> None:
        started = time.perf_counter()
        mark = incoming.count  # bytes received so far (e.g. Automatic Status Back) don't count
        try:
            writer.write(GS_R_PAPER)
            await writer.drain()
            async with asyncio.timeout(self.done_timeout):
                await incoming.more_than(mark)
        except TimeoutError:
            log.warning(
                "printer=%s did not confirm the end of the job within %ss; if it does not "
                "answer GS r, set wait_done=false (PRINTER_WAIT_DONE=false)",
                printer.name,
                self.done_timeout,
            )
            return
        except OSError:
            return
        log.info(
            "printer=%s processed the job in %d ms",
            printer.name,
            (time.perf_counter() - started) * 1000,
        )

    async def aclose(self) -> None:
        """Wait for lingering connections (used at shutdown and in tests)."""
        if self._lingering:
            await asyncio.gather(*self._lingering, return_exceptions=True)

    async def probe(self, printer: PrinterConfig, within: float = 2.0) -> bool:
        """True when a TCP connection to the printer can be opened."""
        try:
            async with asyncio.timeout(within):
                _, writer = await asyncio.open_connection(printer.host, printer.port)
        except (OSError, TimeoutError):
            return False
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()
        return True


class _Incoming:
    """Reads (and discards) whatever the printer sends, counting the bytes."""

    def __init__(self, reader: asyncio.StreamReader) -> None:
        self.count = 0
        self.closed = asyncio.Event()
        self._changed = asyncio.Event()
        self._task = asyncio.create_task(self._read(reader))

    async def _read(self, reader: asyncio.StreamReader) -> None:
        try:
            while chunk := await reader.read(4096):
                self.count += len(chunk)
                self._changed.set()
        except OSError:
            pass
        finally:
            self.closed.set()
            self._changed.set()

    async def more_than(self, mark: int) -> None:
        """Wait until more than `mark` bytes were received, or the connection closed."""
        while True:
            self._changed.clear()  # cleared before the check: no wake-up can be missed
            if self.count > mark or self.closed.is_set():
                return
            await self._changed.wait()

    def stop(self) -> None:
        self._task.cancel()
