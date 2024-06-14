# usage:
# qemu-system-x86_64 -drive file=image.qcow2,if=virtio -m 2048 -monitor unix:/tmp/qmp-socket,server,nowait -qmp unix:/tmp/qmp-socket,server,nowait


import asyncio
import sys

from qemu.qmp import QMPClient


class VMTool:
    def __init__(self, socket_path):
        self.socket_path = socket_path
        self.client = QMPClient()

    async def connect(self):
        await self.client.connect(self.socket_path)
        await self.client.execute("qmp_capabilities")

    async def start(self):
        await self.connect()
        print("VM started and QMP capabilities set.")

    async def pause(self):
        result = await self.client.execute("stop")
        print("VM paused:", result)

    async def resume(self):
        result = await self.client.execute("cont")
        print("VM resumed:", result)

    async def stop(self):
        result = await self.client.execute("system_powerdown")
        print("VM stopping:", result)
        await self.client.disconnect()

    async def query_status(self):
        status = await self.client.execute("query-status")
        print("Current VM status:", status["status"])


async def main():
    if len(sys.argv) < 3:
        print("Usage: python vmtool.py <socket_path> <command>")
        print("Commands: start, pause, resume, stop, status")
        sys.exit(1)

    socket_path = sys.argv[1]
    command = sys.argv[2]

    tool = VMTool(socket_path)
    command_map = {
        "start": tool.start,
        "pause": tool.pause,
        "resume": tool.resume,
        "stop": tool.stop,
        "status": tool.query_status,
    }

    cmd_func = command_map.get(command)
    if cmd_func:
        await cmd_func()
    else:
        print("Invalid command")


if __name__ == "__main__":
    asyncio.run(main())
