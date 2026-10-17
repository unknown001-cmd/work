@echo off
cd /d E:\book_bridge\backend
D:\anaconda\python.exe -c "import asyncio,sys; asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()); import uvicorn; uvicorn.run('main:app',host='127.0.0.1',port=8000,reload=False)" > server.log 2>&1