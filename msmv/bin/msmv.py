import argparse
import asyncio
import logging
import os

from qemu.qmp import QMPClient


from msmv.builders.application import ApplicationBuilder
from msmv.builders.kernel import KernelBuilder
from msmv.builders.rootfs import RootFSBuilder
from msmv.config.parser import ConfigParser
from msmv.util.application_helpers import ApplicationHelpers
from msmv.util.workspace_helpers import WorkspaceHelpers

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Stub: run target software with a non-root user
RUN_WITH_UNPRIV_USER_DEBUG = False


class VMManager:
    def __init__(self, config_file="config.toml", build_dir="./"):
        self.build_dir = build_dir
        self.config_file = config_file
        self.config = ConfigParser.parse_config(self.config_file)
        self.workspace = os.path.join(
            build_dir, self.config["general"]["name"] + "-build"
        )
        self.kernel_path = os.path.join(self.workspace, "kernel", "Image")
        self.initrd_path = os.path.join(self.workspace, "rootfs.cpio")
        self.qmp_client = QMPClient()
        self.socket_path = "/tmp/qmp-socket"
        self.connected = False
        self.capabilities_set = False

    async def connect_qmp(self):
        if not self.qmp_client.is_connected():
            await self.qmp_client.connect(self.socket_path)
            try:
                await self.qmp_client.execute("qmp_capabilities")
            except Exception as e:
                if "Capabilities negotiation is already complete" not in str(e):
                    raise

    async def connect(self):
        if not self.connected:
            try:
                await self.qmp_client.connect(self.socket_path)
                self.connected = True
                if not self.capabilities_set:
                    try:
                        await self.qmp_client.execute("qmp_capabilities")
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
        if not os.path.exists(self.kernel_path) or not os.path.exists(self.initrd_path):
            print(
                "Error: VM not built. Please build the VM first using 'build' command."
            )
            return
        await self.connect_qmp()
        print("VM started and QMP capabilities set.")

    async def stop(self):
        await self.connect_qmp()
        await self.qmp_client.execute("system_powerdown")
        print("VM stopping.")
        await self.qmp_client.disconnect()

    async def pause(self):
        await self.connect_qmp()
        await self.qmp_client.execute("stop")
        print("VM paused.")

    async def resume(self):
        await self.connect_qmp()
        await self.qmp_client.execute("cont")
        print("VM resumed.")

    async def query_status(self):
        await self.connect_qmp()
        status = await self.qmp_client.execute("query-status")
        print("Current VM status:", status["status"])

    def build(self):
        config = ConfigParser.parse_config(self.config_file)
        vm_name = config["general"]["name"]
        workspace = WorkspaceHelpers.setup_workspace(
            os.path.join(self.build_dir, f"{vm_name}-build")
        )

        self.perform_build(config, workspace)

    def perform_build(self, config, workspace):
        dir_paths = {
            "kernel_dir": os.path.join(workspace, "kernel"),
            "apps_dir": os.path.join(workspace, "applications"),
            "rootfs_dir": os.path.join(workspace, "rootfs"),
            "output_dir": os.path.join(workspace, "output_vms"),
        }

        for dir_name, dir_path in dir_paths.items():
            os.makedirs(dir_path, exist_ok=True)

        kernel_builder = KernelBuilder(config)
        kernel_path = kernel_builder.setup_and_build_kernel(workspace)
        logger.info(
            f"Kernel built successfully. Build directory: {kernel_path['kernel_build']}"
        )

        # TODO: do something better than grabbing the first application
        first_app_details = ConfigParser.get_first_application(config)
        app_builder = ApplicationBuilder(first_app_details, dir_paths["rootfs_dir"])
        # Download and extract the application
        # app_source_dir = app_builder.download_and_extract_app(
        #     first_app_details, dir_paths["apps_dir"]
        # )

        # image_name = config["output"].get("image_name", "output_image")
        # image_path = os.path.join(output_dir, f"{image_name}.qcow2")
        # create_qemu_image(image_path)
        # kernel_path = os.path.join(dir_paths["kernel_dir"], "arch/arm64/boot/Image")
        initrd_path = os.path.join(dir_paths["output_dir"], "rootfs.cpio")

        logger.info(f'Setting up rootfs in {dir_paths["rootfs_dir"]}')
        rootfs_builder = RootFSBuilder(dir_paths["rootfs_dir"])
        rootfs_builder.setup_rootfs()

        # Configure and build the application using the actual source directory path
        app_builder.setup_and_build_app(
            dir_paths["apps_dir"],
        )
        # Write a simple init executable and have it run out app's output executable upon VM start
        logger.info(
            f"Compiling init.c with start program {first_app_details['output_executable_path']}"
        )
        ApplicationHelpers.compile_init_c(
            dir_paths["rootfs_dir"], first_app_details["output_executable_path"]
        )

        if RUN_WITH_UNPRIV_USER_DEBUG:
            ApplicationHelpers.create_etc_files(dir_paths["rootfs_dir"])
        # Compile and include an 'ifconfig' replacement in C
        #
        # This negates us from having to include additional common utils
        # in the target VM at the expense of having to...write C code
        if (
            "include_net" in first_app_details
            and first_app_details["include_net"]
            and config["boot"].get("network")
        ):
            # compile_network_config_utility(rootfs_dir)
            ApplicationHelpers.compile_and_setup_net_route_utility(
                dir_paths["rootfs_dir"],
                ip_address=config["boot"]["network"]["ip_address"],
                netmask=config["boot"]["network"]["netmask"],
                gateway=config["boot"]["network"]["gateway"],
            )
            ApplicationHelpers.setup_resolv_conf(dir_paths["rootfs_dir"])

        # Copy a vt100 compile terminfo entry to the build system
        #   Needed for any program needed to emulate a terminal
        # TODO: this is mostly a hack and subverts us from having to compile ncurses
        ApplicationHelpers.find_and_copy_vt(dir_paths["rootfs_dir"])

        logger.info("Creating uncompressed cpio")
        rootfs_builder.make_uncompressed_cpio(
            dir_paths["rootfs_dir"], dir_paths["output_dir"]
        )
        # logger.info("Setting up boot params")
        # setup_boot_parameters("aarch64",
        #     kernel_path=kernel_path,
        #     initrd_path=initrd_path,
        #     cmdline="noshell initrd=/init root=/dev/ram console=ttyS0,115200",
        #     output_path=output_dir, enable_network=True
        # )
        logger.info("Built image! Done!")

        logger.info(f"Kernel build path {kernel_path['kernel_build']}")
        logger.info(f"Kernel output path {kernel_path['kernel_image']}")
        logger.info(f"Initrd output path {initrd_path}")
        # Use script args to optionally clear the workspace after building
        # clean_workspace(workspace)


def main():
    parser = argparse.ArgumentParser(description="Manage and Build MicroVMs")
    parser.add_argument(
        "-c", "--config-file", default="config.toml", help="Path to the config file"
    )
    parser.add_argument(
        "-b", "--build-dir", default="./", help="Directory to build VMs in"
    )
    parser.add_argument(
        "command", choices=["build", "start", "stop", "pause", "resume", "status"]
    )
    args = parser.parse_args()

    manager = VMManager(args.config_file, args.build_dir)

    if args.command == "build":
        manager.build()
    else:
        asyncio.run(getattr(manager, args.command)())


if __name__ == "__main__":
    main()
