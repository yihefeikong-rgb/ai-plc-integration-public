"""机器人离线测试的事件循环隔离。"""
import asyncio

import pytest


@pytest.fixture(autouse=True)
def event_loop():
    """旧式同步测试调用 get_event_loop() 时也得到一个独立循环。"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        yield loop
    finally:
        loop.close()
        asyncio.set_event_loop(None)
