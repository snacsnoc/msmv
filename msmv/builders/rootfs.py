import logging
import os
import stat
import subprocess

from msmv.util.host_command import HostCommand

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# DEBUG switch
USE_C_INIT = True


class RootFSBuilder:
    def __init__(self, rootfs_path):
        self.rootfs_path = rootfs_path

    """Check if the device node exists and is of the correct type"""

    def device_node_exists(self, path, type_):
        try:
            if os.path.exists(path):
                st = os.stat(path)
                if (type_ == "c" and stat.S_ISCHR(st.st_mode)) or (
                    type_ == "b" and stat.S_ISBLK(st.st_mode)
                ):
                    return True
        except Exception as e:
            logger.error(f"Error checking device at {path}: {str(e)}")
        return False

    def setup_rootfs(self):
        # root_dir = os.path.join(output_dir, "root")
        # os.makedirs(root_dir, exist_ok=True)
        output_dir = self.rootfs_path
        # Create the essential directories
        essential_dirs = [
            "tmp",
            "proc",
            "sys",
            "bin",
            "dev",
            os.path.join("usr", "bin"),
        ]
        for dir_name in essential_dirs:
            logger.info(f"Creating directory {dir_name} in {output_dir}")
            os.makedirs(os.path.join(output_dir, dir_name), exist_ok=True)

        if not USE_C_INIT:
            # Create init script
            with open(os.path.join(output_dir, "init"), "w") as f:
                f.write(
                    """#!/bin/sh
    echo 'Initializing root filesystem...'
    mount -t proc none /proc
    mount -t sysfs none /sys
    mount -t devtmpfs none /dev
    echo 'Root filesystem initialized.'
    # Start a shell
    exec /bin/sh -i

    # Infinite loop to prevent the script from exiting
    while true; do
        sleep 1
    done
    EOF
    """
                )
                logger.info("Writing init script")
            os.chmod(os.path.join(output_dir, "init"), 0o775)

        self.create_device_nodes(output_dir)

    def create_device_nodes(self, output_dir):
        # Create device nodes
        # need root privileges to create device nodes
        # does not work otherwise lol
        device_nodes = [
            ("console", "c", "5", "1"),
            ("ttyS0", "c", "4", "64"),
            ("tty", "c", "5", "0"),
            ("ram0", "b", "1", "0"),
        ]
        for node, type_, major, minor in device_nodes:
            device_path = os.path.join("dev", node)
            o_device_path = os.path.join(output_dir, "dev", node)
            if not self.device_node_exists(o_device_path, type_):
                logger.info(
                    f"Creating device nodes in {output_dir} with path {device_path}"
                )
                HostCommand.run_command(
                    ["sudo", "mknod", device_path, type_, major, minor], output_dir
                )
                HostCommand.run_command(
                    ["sudo", "chmod", "666", device_path], output_dir
                )
                logger.info("Finished creating device nodes")
            else:
                logger.info(f"Device node {device_path} already exists")

    def make_compressed_cpio(self, output_dir):
        # Create cpio archive without compression
        HostCommand.run_command(
            [
                "find",
                output_dir,
                "-print0",
                "|",
                "cpio",
                "--null",
                "-ov",
                "--format=newc",
                ">",
                f"{output_dir}/rootfs.cpio",
            ]
        )

        # Compress the cpio archive
        HostCommand.run_command(
            ["gzip", "-9", f"{output_dir}/rootfs.cpio"], cwd=output_dir
        )

    def make_uncompressed_cpio(self, rootfs_path, output_dir):
        # Save the current directory before changing it
        current_dir = os.getcwd()

        # Ensure the output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Define the path for the cpio file
        cpio_path = os.path.join(current_dir, output_dir, "rootfs.cpio")

        # Change directory to the rootfs path to ensure relative paths in the cpio archive
        os.chdir(rootfs_path)

        # Command to find files and output null-separated names
        find_command = ["find", ".", "-print0"]

        # Command to create cpio archive, with output directed to a file
        cpio_command = ["cpio", "--null", "-ov", "--format=newc"]

        # Run find and pipe to cpio
        stdout, stderr = HostCommand.run_command(
            find_command,
            cwd=self.rootfs_path,
            next_command=cpio_command,
            stdout=open(cpio_path, "wb"),
            binary_mode=True,
        )

        # Restore the original working directory
        os.chdir(current_dir)

        # Check if the cpio operation was successful
        if stderr:
            logger.error(f"Error in creating the CPIO archive: {stderr}")
            raise Exception("Failed to create the CPIO archive.")
        else:
            logger.info(f"CPIO archive created successfully at: {cpio_path}")
