import asyncio

import pytest

from escpos_api.config import PrinterConfig
from escpos_api.transport import GS_R_PAPER, PrinterTimeout, PrinterUnreachable, Transport

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
    printer discarded the unread tail of the job (end of image, feed, cut). Status bytes
    sent before the GS r request must not be taken for its answer either."""
    received = bytearray()
    events = []
    done = asyncio.Event()

    async def handler(reader, writer):
        writer.write(b"\x14\x00\x00\x0f")  # Automatic Status Back, before anything else
        await writer.drain()
        try:
            while chunk := await reader.read(512):  # slow printer
                received.extend(chunk)
                await asyncio.sleep(0.001)
                if received.endswith(GS_R_PAPER):
                    await asyncio.sleep(0.2)  # still printing
                    events.append("answered")
                    writer.write(b"\x00")
                    await writer.drain()
            events.append("eof")
        except ConnectionResetError:
            events.append("reset")
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
    assert bytes(received) == payload + GS_R_PAPER
    assert events == ["answered", "eof"]  # no FIN before the printer confirmed


async def test_next_job_waits_until_the_printer_has_processed_the_previous_one():
    """The end of a job (cut) must never be overtaken by the next job."""
    log = []

    async def handler(reader, writer):
        data = bytearray()
        while chunk := await reader.read(4096):
            data.extend(chunk)
            if data.endswith(GS_R_PAPER):
                await asyncio.sleep(0.3)  # printing a large image
                log.append(f"done {bytes(data[:5]).decode()}")
                writer.write(b"\x00")
                await writer.drain()
        writer.close()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    real_open = asyncio.open_connection

    async def tracked_open(*args, **kwargs):
        log.append("connect")
        return await real_open(*args, **kwargs)

    cfg = PrinterConfig(name="p", host="127.0.0.1", port=port)
    transport = Transport(5)
    import escpos_api.transport as transport_mod

    transport_mod.asyncio.open_connection = tracked_open
    try:
        await transport.send(cfg, b"first")
        await transport.send(cfg, b"secnd")
        await transport.aclose()
    finally:
        transport_mod.asyncio.open_connection = real_open
        server.close()
    assert log == ["connect", "done first", "connect", "done secnd"]


async def test_printer_not_answering_gs_r_releases_the_lock_after_done_timeout(caplog):
    async def handler(reader, writer):
        await reader.read()  # never answers, closes after our FIN
        writer.close()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    cfg = PrinterConfig(name="p", host="127.0.0.1", port=port)
    transport = Transport(5, done_timeout=0.3)
    loop = asyncio.get_running_loop()
    start = loop.time()
    await transport.send(cfg, b"first")
    await transport.send(cfg, b"second")
    assert loop.time() - start >= 0.3
    await transport.aclose()
    server.close()
    assert "did not confirm the end of the job" in caplog.text


async def test_wait_done_disabled_sends_no_status_request(printer):
    cfg = PrinterConfig(name="p", host="127.0.0.1", port=printer.port, wait_done=False)
    await Transport(2).send(cfg, b"hello")
    await wait_jobs(printer, 1)
    assert printer.jobs == [b"hello"]
    assert printer.status_requests == 0


async def test_printer_that_never_closes_releases_lock_after_grace():
    async def handler(reader, writer):
        await reader.read()  # reads until our FIN, then keeps the socket open
        await asyncio.sleep(5)

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    cfg = PrinterConfig(name="p", host="127.0.0.1", port=port, wait_done=False)
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
