"""
启动脚本：强制使用 SelectorEventLoop 解决 Windows asyncio 兼容性问题
"""
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.SelectorEventLoopPolicy())

import uvicorn
uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)