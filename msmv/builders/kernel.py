import logging
import os
import shutil
import tarfile

import requests
from tqdm import tqdm

from msmv.util.host_command import run_command

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

"""Download the kernel source tarball from the specified URL with a progress bar."""


def download_kernel_source(url, download_path):
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            total_size_in_bytes = int(response.headers.get("content-length", 0))
            # 1 kilobyte
            chunk_size = 1024
            progress_bar = tqdm(total=total_size_in_bytes, unit="iB", unit_scale=True)

            with open(download_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    progress_bar.update(len(chunk))
                    f.write(chunk)
            progress_bar.close()

            if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
                logger.error(
                    "WARNING: Downloaded file size does not match expected content length."
                )
    except requests.exceptions.RequestException as e:
        logger.info(f"Error downloading kernel source: {e}")
        raise Exception(f"Failed to download kernel source: {response.status_code}")


"""Extract the kernel source tarball to a specified directory"""


def extract_kernel_tarball(tar_path, extract_to):
    # Check the file extension and open accordingly
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
        logger.info(f"Directory {predicted_dir} already exists, skipping extraction.")
        return predicted_dir

    with tarfile.open(tar_path, tar_open_mode) as tar:
        total_length = sum(member.size for member in tar.getmembers())
        progress_bar = tqdm(total=total_length, unit="iB", unit_scale=True)

        # Extract and identify the kernel source directory
        tar.extractall(path=extract_to)
        progress_bar.close()

        # Assuming the kernel directory is the first directory in the tarball
        kernel_source_dir = [
            member.name.split("/")[0] for member in tar.getmembers() if member.isdir()
        ][0]
        return os.path.join(extract_to, kernel_source_dir)


""" Set kernel kconfig options """


def configure_kernel(kernel_config, kernel_dir):
    kernel_dir = os.path.abspath(kernel_dir)
    logger.info(f"Checking if directory exists: {kernel_dir}")
    if not os.path.exists(kernel_dir):
        raise FileNotFoundError(f"The directory {kernel_dir} does not exist.")

    logger.info(f"Running 'make tinyconfig' in directory {kernel_dir}")
    # TODO: all kernel clean behaviour
    # run_command(["make", "clean"], cwd=kernel_dir, timeout=3600)  # Timeout in seconds

    run_command(["make", "tinyconfig"], cwd=kernel_dir)
    logger.info("applying kernel configs")
    # Apply custom configurations from TOML
    for option, raw_value in kernel_config["options"].items():
        # Remove both single and double quotes
        value = raw_value.strip("'\"")
        logger.info(f"Setting {option} to {value}")
        # Ensure the command is split into separate arguments
        config_command = ["scripts/config", "--set-val", option, value]
        run_command(config_command, cwd=kernel_dir)


"""Apply given patches to the kernel source."""


def apply_patches(patches, kernel_dir):
    for patch in patches:
        run_command(["git", "apply", patch], cwd=kernel_dir, shell=False)


""""Apply default kconfig selections after applying the user's selections"""


def apply_default_kernel_options(kernel_dir):
    # we need to run make olddefconfig to set default options after applying the user's TOML settings
    run_command(["make", "olddefconfig"], cwd=kernel_dir)


"""Build the configured Linux kernel."""


def build_kernel(kernel_dir):
    run_command(["make", "-j8", "Image"], cwd=kernel_dir, timeout=3600)


""""Copy the kernel to the output_vm directory"""


def copy_kernel_to_output(kernel_dir, output_dir):
    # TODO: determine build arch to determine output kernel image
    # Copy the kernel from arch/arm64/boot/Image to the specified dir
    shutil.copy(f"{kernel_dir}/arch/arm64/boot/Image", output_dir)
