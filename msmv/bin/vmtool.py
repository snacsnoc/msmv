# usage:
# qemu-system-x86_64 -drive file=image.qcow2,if=virtio -m 2048 -monitor unix:/tmp/qmp-socket,server,nowait -qmp unix:/tmp/qmp-socket,server,nowait

import asyncio
import sys

from qemu.qmp import QMPClient


class VMTool:
    def __init__(self, socket_path):
        self.socket_path = socket_path
        self.client = QMPClient()
        self.connected = False
        self.capabilities_set = False

    async def connect(self):
        if not self.connected:
            try:
                await self.client.connect(self.socket_path)
                self.connected = True
                if not self.capabilities_set:
                    try:
                        await self.client.execute("qmp_capabilities")
                        self.capabilities_set = True
                        print("QMP capabilities set successfully.")
                    except Exception as e:
                        if "Capabilities negotiation is already complete" in str(e):
                            self.capabilities_set = True
                            print("Capabilities were already set.")
                        else:
                            print(f"Error setting capabilities: {e}")
            except Exception as e:
                print(f"Failed to connect: {e}")
                self.connected = False

    async def start(self):
        await self.connect()
        if self.connected:
            print("VM started and QMP capabilities set.")

    async def pause(self):
        await self.connect()
        if self.connected:
            result = await self.client.execute("stop")
            print("VM paused:", result)

    async def resume(self):
        await self.connect()
        if self.connected:
            result = await self.client.execute("cont")
            print("VM resumed:", result)

    async def stop(self):
        await self.connect()
        if self.connected:
            result = await self.client.execute("system_powerdown")
            print("VM stopping:", result)
            await self.client.disconnect()
            self.connected = False

    async def query_status(self):
        await self.connect()
        if self.connected:
            status = await self.client.execute("query-status")
            print("Current VM status:", status["status"])


async def main():
    if len(sys.argv) < 3:
        print("Usage: python vmtool.py <socket_path> <command>")
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
