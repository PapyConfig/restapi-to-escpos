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
