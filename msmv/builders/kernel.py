import logging
import os
import shlex
import shutil
import tarfile

import requests
from tqdm import tqdm

from msmv.util.host_command import HostCommand

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class KernelBuilder:
    ARCH_MAPPING = {
        "aarch64": "arm64",
        "x86": "x86",
        "x86_64": "x86",
    }

    KERNEL_IMAGE_MAPPING = {
        "arm64": "Image",
        "x86": "bzImage",
    }

    def __init__(self, config):
        self.config = config
        self.make_command = os.getenv("MAKE_COMMAND", "make -j8")
        self.target_arch = self.config.get("general", {}).get("target_arch", "x86")
        self.kernel_arch = self.ARCH_MAPPING.get(self.target_arch, self.target_arch)
        self.kernel_image = self.KERNEL_IMAGE_MAPPING.get(self.kernel_arch, "Image")

        # Default to 'cc' if not set
        self.compiler = os.getenv("CC", "cc")

        # Set the environment variables
        self.env = os.environ.copy()
        self.env["CC"] = self.compiler
        self.env["ARCH"] = self.kernel_arch

    def setup_and_build_kernel(self, workspace):
        dir_paths = self.setup_directories(workspace)
        kernel_dir = self.handle_kernel_source(workspace)
        # TODO: refactor this
        dir_paths["kernel_build"] = kernel_dir
        dir_paths["kernel_image"] = os.path.join(
            dir_paths["output_dir"], self.kernel_image
        )

        self.configure_kernel(self.config["kernel"], kernel_dir)
        if "patches" in self.config["kernel"]:
            self.apply_patches(self.config["kernel"]["patches"], kernel_dir)
        self.apply_default_kernel_options(kernel_dir)
        self.build_kernel(kernel_dir)
        self.copy_kernel_to_output(kernel_dir, dir_paths["output_dir"])
        return dir_paths

    def setup_directories(self, workspace):
        dir_paths = {
            "kernel_dir": os.path.join(workspace, "kernel"),
            "output_dir": os.path.join(workspace, "output_vms"),
        }
        for dir_name, dir_path in dir_paths.items():
            os.makedirs(dir_path, exist_ok=True)
        return dir_paths

    def handle_kernel_source(self, workspace):
        kernel_version = self.config["kernel"]["version"]
        kernel_dir = os.path.join(workspace, "kernel")
        kernel_tar_path = os.path.join(kernel_dir, f"linux-{kernel_version}.tar.xz")

        if not os.path.exists(kernel_tar_path):
            logger.info("Kernel source tarball does not exist, downloading...")
            kernel_url = self.config["kernel"].get("url")
            self.download_kernel_source(kernel_version, kernel_tar_path, url=kernel_url)

        logger.info("Extracting tar")
        extracted_kernel_dir = self.extract_kernel_tarball(kernel_tar_path, kernel_dir)

        if os.path.exists(extracted_kernel_dir):
            logger.info("Extracted kernel directory exists....")
            return extracted_kernel_dir
        else:
            raise Exception("Failed to locate the extracted kernel source directory.")

    """Download the kernel source tarball, optionally with a specified URL"""

    def download_kernel_source(self, kernel_version, download_path, url=None):
        if url is None:
            url = f"https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-{kernel_version}.tar.xz"

        try:
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                total_size_in_bytes = int(response.headers.get("content-length", 0))
                chunk_size = 1024
                progress_bar = tqdm(
                    total=total_size_in_bytes, unit="iB", unit_scale=True
                )

                with open(download_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        progress_bar.update(len(chunk))
                        f.write(chunk)
                progress_bar.close()

                if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
                    logger.error(
                        "WARNING: Downloaded file size does not match expected content length."
                    )
            else:
                logger.error(
                    f"Error downloading kernel source: HTTP {response.status_code}"
                )
        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading kernel source: {e}")
            raise Exception(f"Failed to download kernel source due to: {str(e)}")

    """Extract the kernel source tarball to a specified directory"""

    def extract_kernel_tarball(self, tar_path, extract_to):
        if tar_path.endswith(".gz"):
            tar_open_mode = "r:gz"
        elif tar_path.endswith(".xz"):
            tar_open_mode = "r:xz"
        else:
            raise ValueError("Unsupported archive format. Please use .gz or .xz files.")

        # Try to predict the directory name from the tarball name
        base_name = os.path.basename(tar_path)
        if ".tar" in base_name:
            base_name = base_name.split(".tar")[0]
        predicted_dir = os.path.join(extract_to, base_name)
        logger.info(f"Predicted directory name: {predicted_dir}")

        # Skip extraction if the directory already exists
        if os.path.isdir(predicted_dir):
            logger.info(
                f"Directory {predicted_dir} already exists, skipping extraction."
            )
            return predicted_dir

        with tarfile.open(tar_path, tar_open_mode) as tar:
            total_length = sum(member.size for member in tar.getmembers())
            progress_bar = tqdm(total=total_length, unit="iB", unit_scale=True)

            # Extract and identify the kernel source directory
            tar.extractall(path=extract_to)
            progress_bar.close()

            # Assuming the kernel directory is the first directory in the tarball
            kernel_source_dir = [
                member.name.split("/")[0]
                for member in tar.getmembers()
                if member.isdir()
            ][0]
            return os.path.join(extract_to, kernel_source_dir)

    """ Set kernel kconfig options """

    def configure_kernel(self, kernel_config, kernel_dir):
        kernel_dir = os.path.abspath(kernel_dir)
        logger.info(f"Checking if directory exists: {kernel_dir}")
        if not os.path.exists(kernel_dir):
            raise FileNotFoundError(f"The directory {kernel_dir} does not exist.")

        logger.info(
            f'Running "{self.env["CC"]} {self.make_command} tinyconfig" in directory {kernel_dir} for arch {self.env["ARCH"]}'
        )

        make_kernel_command = shlex.split(self.make_command) + ["tinyconfig"]
        HostCommand.run_command(make_kernel_command, cwd=kernel_dir, env=self.env)
        logger.info("Applying kernel configs")

        # Apply custom configurations from TOML
        for option, raw_value in kernel_config["options"].items():
            # Remove both single and double quotes
            value = raw_value.strip("'\"")
            logger.info(f"Setting {option} to {value}")
            # Ensure the command is split into separate arguments
            kconfig_config_command = ["scripts/config", "--set-val", option, value]
            HostCommand.run_command(
                kconfig_config_command, cwd=kernel_dir, env=self.env
            )

    """Apply given patches to the kernel source."""

    def apply_patches(self, patches, kernel_dir):
        for patch in patches:
            HostCommand.run_command(
                ["git", "apply", patch], cwd=kernel_dir, shell=False
            )

    """"Apply default kconfig selections after applying the user's selections"""

    def apply_default_kernel_options(self, kernel_dir):
        # we need to run make olddefconfig to set default options after applying the user's TOML settings
        make_kernel_command = shlex.split(self.make_command) + ["olddefconfig"]
        HostCommand.run_command(make_kernel_command, cwd=kernel_dir, env=self.env)

    """Build the configured Linux kernel."""

    def build_kernel(self, kernel_dir):
        make_kernel_command = shlex.split(self.make_command) + [self.kernel_image]
        HostCommand.run_command(
            make_kernel_command, cwd=kernel_dir, timeout=3600, env=self.env
        )

    """"Copy the kernel to the output_vm directory"""

    def copy_kernel_to_output(self, kernel_dir, output_dir):
        kernel_image_path = os.path.join(
            kernel_dir, "arch", self.kernel_arch, "boot", self.kernel_image
        )
        logger.info(f"Copying kernel from {kernel_image_path} to {output_dir}")

        if not os.path.exists(kernel_image_path):
            raise FileNotFoundError(f"Kernel image not found at {kernel_image_path}")

        if not shutil.copy(kernel_image_path, output_dir):
            logger.error("Failed to copy kernel")
            exit(1)
        else:
            return self.kernel_image
