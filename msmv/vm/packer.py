import logging

from msmv.util.host_command import run_command

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

"""Create a QEMU image."""


def create_qemu_image(image_path, image_size="1G"):
    run_command(["qemu-img", "create", "-f", "qcow2", image_path, image_size])


"""Setup boot parameters and run QEMU with an attached disk image"""


# TODO: FIX THIS
def setup_boot_parameters_with_image(kernel_path, initrd_path, image_path, cmdline):
    run_command(
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


def setup_boot_parameters(kernel_path, initrd_path, cmdline, output_path):
    run_command(
        [
            "qemu-system-aarch64",
            "-M",
            "microvm",
            "-kernel",
            kernel_path,
            "-initrd",
            initrd_path,
            "-append",
            cmdline,
            "-nographic",
        ],
        cwd=output_path,
    )
