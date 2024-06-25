import logging

from msmv.util.host_command import HostCommand

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

"""Utility class to handle booting Qemu with supplied build files"""


class VMBooter:

    """Create a QEMU image"""

    @staticmethod
    def create_qemu_image(image_path, image_size="1G"):
        HostCommand.run_command(
            ["qemu-img", "create", "-f", "qcow2", image_path, image_size], cwd="."
        )

    """Setup boot parameters and run QEMU with an attached disk image"""

    # TODO: FIX THIS
    @staticmethod
    def setup_boot_parameters_with_image(kernel_path, initrd_path, image_path, cmdline):
        HostCommand.run_command(
            [
                "qemu-system-x86_64",
                "-kernel",
                kernel_path,
                "-initrd",
                initrd_path,
                "-hda",
                image_path,
                "-append",
                cmdline,
                "-nographic",
            ],
            cwd=".",
        )

    """Setup boot parameters and run QEMU."""

    @staticmethod
    def setup_boot_parameters(
        target_arch,
        kernel_path,
        initrd_path,
        cmdline,
        output_path,
        enable_network=False,
        network_interface="net0",
    ):
        # Determine the appropriate qemu binary based on target_arch
        qemu_binary = f"qemu-system-{target_arch}"

        # Base command setup
        command = [
            qemu_binary,
            "-M",
            "virt",
            "-cpu",
            "max",
            "-kernel",
            kernel_path,
            "-initrd",
            initrd_path,
            "-append",
            cmdline,
            "-serial",
            "mon:stdio",
            "-nographic",
            "-m",
            "128",
        ]

        # Add network options if networking is enabled
        if enable_network:
            command.extend(
                [
                    "-netdev",
                    f"user,id={network_interface}",
                    "-device",
                    f"virtio-net-device,netdev={network_interface}",
                ]
            )

        logger.info(f"Running QEMU with command: {' '.join(command)}")
        HostCommand.run_command(command, cwd=output_path)
