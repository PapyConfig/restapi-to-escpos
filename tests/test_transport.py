import asyncio

import pytest

from escpos_api.config import PrinterConfig
from escpos_api.transport import PrinterTimeout, PrinterUnreachable, Transport

from .conftest import FakePrinter, free_port, wait_jobs


async def test_send_whole_payload(printer):
    cfg = PrinterConfig(name="p", host="127.0.0.1", port=printer.port)
    await Transport(2).send(cfg, b"hello" * 10000)
    await wait_jobs(printer, 1)
    assert printer.jobs == [b"hello" * 10000]


async def test_unreachable():
    cfg = PrinterConfig(name="p", host="127.0.0.1", port=free_port())
    with pytest.raises(PrinterUnreachable):
        await Transport(2).send(cfg, b"x")


async def test_timeout_when_printer_never_reads():
    # Accept the connection but never read: the send buffer fills up.
    async def handler(reader, writer):
        await asyncio.sleep(10)

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    cfg = PrinterConfig(name="p", host="127.0.0.1", port=port)
    try:
        with pytest.raises(PrinterTimeout):
            await Transport(0.5).send(cfg, b"x" * 50_000_000)
    finally:
        server.close()


async def test_jobs_are_serialized_per_printer(monkeypatch):
    """Never more than one open connection per printer on the client side."""
    import escpos_api.transport as transport_mod

    slow = FakePrinter(delay=0.005)
    await slow.start()
    real_open = asyncio.open_connection
    state = {"active": 0, "max": 0}

    class Tracked:
        def __init__(self, writer):
            self._w = writer

        def __getattr__(self, name):
            return getattr(self._w, name)

        def close(self):
            if not self._w.is_closing():
                state["active"] -= 1
            self._w.close()

    async def tracked_open(*args, **kwargs):
        reader, writer = await real_open(*args, **kwargs)
        state["active"] += 1
        state["max"] = max(state["max"], state["active"])
        await asyncio.sleep(0.01)  # give other sends a chance to overlap
        return reader, Tracked(writer)

    monkeypatch.setattr(transport_mod.asyncio, "open_connection", tracked_open)
    cfg = PrinterConfig(name="p", host="127.0.0.1", port=slow.port)
    other = PrinterConfig(name="q", host="127.0.0.1", port=slow.port)
    transport = Transport(5)
    payloads = [bytes([65 + i]) * 200_000 for i in range(5)]
    await asyncio.gather(*(transport.send(cfg, p) for p in payloads))
    assert state["max"] == 1
    # Different printers are not blocked by each other.
    state["max"] = 0
    await asyncio.gather(transport.send(cfg, b"x"), transport.send(other, b"y"))
    assert state["max"] == 2
    await wait_jobs(slow, 7)
    await slow.stop()
    assert set(payloads) <= set(slow.jobs)


async def test_probe(printer):
    t = Transport(2)
    assert await t.probe(PrinterConfig(name="p", host="127.0.0.1", port=printer.port))
    assert not await t.probe(PrinterConfig(name="p", host="127.0.0.1", port=free_port()))


async def test_printer_sending_status_bytes_gets_the_whole_job():
    """Regression: unread status bytes used to turn our close into a TCP RST, and the
    printer discarded the unread tail of the job (end of image, feed, cut)."""
    received = bytearray()
    done = asyncio.Event()

    async def handler(reader, writer):
        writer.write(b"\x14\x00\x00\x0f")  # Automatic Status Back
        await writer.drain()
        try:
            while chunk := await reader.read(512):  # slow printer
                received.extend(chunk)
                await asyncio.sleep(0.001)
        except ConnectionResetError:
            pass
        done.set()
        writer.close()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    payload = b"\x1b@" + b"\xaa" * 53712 + b"\n" * 5 + b"\x1bd\x06\x1dV\x00"
    transport = Transport(10)
    await transport.send(PrinterConfig(name="p", host="127.0.0.1", port=port), payload)
    await asyncio.wait_for(done.wait(), 10)
    await transport.aclose()
    server.close()
    assert bytes(received) == payload


async def test_printer_that_never_closes_releases_lock_after_grace():
    async def handler(reader, writer):
        await reader.read()  # reads until our FIN, then keeps the socket open
        await asyncio.sleep(5)

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    cfg = PrinterConfig(name="p", host="127.0.0.1", port=port)
    transport = Transport(5, close_grace=0.3)
    loop = asyncio.get_running_loop()
    start = loop.time()
    await transport.send(cfg, b"first")
    assert loop.time() - start < 0.2  # the caller does not wait for the grace period
    await transport.send(cfg, b"second")  # waits for the first job to linger out
    assert loop.time() - start >= 0.3
    await transport.aclose()
    server.close()


async def test_lock_released_after_failure():
    cfg = PrinterConfig(name="p", host="127.0.0.1", port=free_port())
    transport = Transport(1)
    for _ in range(2):  # would deadlock if the first failure kept the lock
        with pytest.raises(PrinterUnreachable):
            await asyncio.wait_for(transport.send(cfg, b"x"), 2)
