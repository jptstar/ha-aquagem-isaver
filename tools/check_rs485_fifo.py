"""Validate the explicit FIFO RS485 bus manager without Home Assistant imports."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path


TRANSPORT_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "aquagem_isaver"
    / "transport.py"
)


def _load_bus_manager_class():
    spec = importlib.util.spec_from_file_location("aquagem_transport_test", TRANSPORT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load Aquagem transport module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Rs485BusManager


async def _validate_fifo() -> None:
    bus_manager = _load_bus_manager_class()("test:fifo")
    order: list[str] = []
    first_entered = asyncio.Event()
    release_first = asyncio.Event()

    async def worker(name: str, *, hold: bool = False) -> None:
        async with bus_manager.transaction():
            order.append(name)
            if hold:
                first_entered.set()
                await release_first.wait()

    first = asyncio.create_task(worker("A", hold=True))
    await first_entered.wait()

    second = asyncio.create_task(worker("B"))
    await asyncio.sleep(0)
    third = asyncio.create_task(worker("C"))
    await asyncio.sleep(0)

    release_first.set()
    await asyncio.gather(first, second, third)

    if order != ["A", "B", "C"]:
        raise AssertionError(f"RS485 transactions are not FIFO: {order!r}")


async def _validate_cancelled_waiter() -> None:
    bus_manager = _load_bus_manager_class()("test:cancel")
    order: list[str] = []
    first_entered = asyncio.Event()
    release_first = asyncio.Event()

    async def worker(name: str, *, hold: bool = False) -> None:
        async with bus_manager.transaction():
            order.append(name)
            if hold:
                first_entered.set()
                await release_first.wait()

    first = asyncio.create_task(worker("A", hold=True))
    await first_entered.wait()

    cancelled = asyncio.create_task(worker("B"))
    await asyncio.sleep(0)
    third = asyncio.create_task(worker("C"))
    await asyncio.sleep(0)

    cancelled.cancel()
    try:
        await cancelled
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError("Cancelled FIFO waiter unexpectedly completed")

    release_first.set()
    await asyncio.gather(first, third)

    if order != ["A", "C"]:
        raise AssertionError(f"Cancelled waiter blocked FIFO queue: {order!r}")


async def main() -> None:
    await _validate_fifo()
    await _validate_cancelled_waiter()
    print("RS485 FIFO validation passed")


if __name__ == "__main__":
    asyncio.run(main())
