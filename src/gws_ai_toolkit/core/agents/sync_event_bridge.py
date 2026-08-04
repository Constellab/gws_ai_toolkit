"""Bridge between async event producers and the synchronous generators the callers expect.

pydantic-ai is async, while this brick's agents expose ``call_agent()`` as a synchronous
generator consumed both from Reflex background events (which already run inside an event
loop) and from plain synchronous code such as tasks. ``pydantic_ai.Agent.run_stream_sync``
cannot be used from inside a running loop, so the bridge runs the async producer on its own
loop in a worker thread and hands events back through a queue.

Events therefore stay streamed rather than buffered: a caller sees each event as soon as the
producer emits it.
"""

import asyncio
import queue
import threading
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from typing import Any, Generic, TypeVar

T = TypeVar("T")

# Emit callback handed to the async producer so it can push events out as they happen.
EmitCallback = Callable[[T], None]
ProducerFactory = Callable[[EmitCallback], Awaitable[None]]


class SyncEventBridge(Generic[T]):
    """Runs an async event producer and exposes its events synchronously."""

    _ITEM = "item"
    _DONE = "done"
    _ERROR = "error"

    @classmethod
    def iterate(cls, producer: ProducerFactory) -> Generator[T, None, None]:
        """Run an async producer on a worker thread and yield its events synchronously.

        Args:
            producer: Callable receiving an ``emit`` callback and returning the awaitable
                that drives the run. Every value passed to ``emit`` is yielded by this
                generator, in emission order.

        Yields:
            Each event emitted by the producer.

        Raises:
            BaseException: Whatever the producer raised, re-raised on the calling thread so
                that callers keep the error handling they had with the synchronous loop.
        """
        events: queue.Queue[tuple[str, Any]] = queue.Queue()

        def emit(event: T) -> None:
            events.put((cls._ITEM, event))

        def run() -> None:
            try:
                asyncio.run(producer(emit))
                events.put((cls._DONE, None))
            except BaseException as exception:  # noqa: BLE001 - forwarded to the caller
                events.put((cls._ERROR, exception))

        # Daemon so an abandoned generator can never keep the interpreter alive.
        thread = threading.Thread(target=run, daemon=True, name="gws-agent-stream")
        thread.start()

        try:
            while True:
                kind, payload = events.get()
                if kind == cls._ITEM:
                    yield payload
                elif kind == cls._DONE:
                    return
                else:
                    raise payload
        finally:
            thread.join(timeout=0)

    @classmethod
    async def aiterate(cls, producer: ProducerFactory) -> AsyncGenerator[T, None]:
        """Run an async producer on the current loop and yield its events asynchronously.

        The async counterpart of :meth:`iterate`, for callers that are already async and do
        not need the worker thread.

        Args:
            producer: Callable receiving an ``emit`` callback and returning the awaitable
                that drives the run.

        Yields:
            Each event emitted by the producer.

        Raises:
            BaseException: Whatever the producer raised.
        """
        events: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

        def emit(event: T) -> None:
            events.put_nowait((cls._ITEM, event))

        async def run() -> None:
            try:
                await producer(emit)
                await events.put((cls._DONE, None))
            except BaseException as exception:  # noqa: BLE001 - forwarded to the caller
                await events.put((cls._ERROR, exception))

        task = asyncio.create_task(run())
        try:
            while True:
                kind, payload = await events.get()
                if kind == cls._ITEM:
                    yield payload
                elif kind == cls._DONE:
                    return
                else:
                    raise payload
        finally:
            if not task.done():
                task.cancel()
