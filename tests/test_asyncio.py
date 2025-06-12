import asyncio

async def hello():
    print("Hello")
    await asyncio.sleep(1)  # 模拟耗时操作，挂起协程执行
    print("World")

async def main():
    await asyncio.gather(
        hello(),
        hello()
    )

asyncio.run(main())
