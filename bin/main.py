import argparse
import logging
import os
import shutil
import sys

# Append the directory above 'bin' to sys.path to find the 'msmv' package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from msmv.builders.application import (
    download_and_extract_app,
    configure_and_build_app,
)
from msmv.builders.kernel import (
    configure_kernel,
    apply_patches,
    build_kernel,
    download_kernel_source,
    extract_kernel_tarball,
    copy_kernel_to_output,
    apply_default_kernel_options,
)
from msmv.builders.rootfs import setup_rootfs, make_uncompressed_cpio
from msmv.config.parser import parse_config, get_first_application
from msmv.util.application_helpers import (
    compile_init_c,
    find_and_copy_vt,
    compile_and_setup_net_route_utility,
    setup_resolv_conf,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def setup_workspace(base_dir):
    workspace = os.path.join(base_dir, "workspace")
    os.makedirs(workspace, exist_ok=True)
    return workspace


def clean_workspace(workspace):
    shutil.rmtree(workspace)


def main():
    # Read config and setup build workspace
    parser = argparse.ArgumentParser(
        description="Build and create virtual machine images"
    )
    parser.add_argument(
        "--config-file", type=str, help="Path to the config file in lynx.toml format"
    )
    parser.add_argument(
        "-b",
        "--build-dir",
        type=str,
        help="Set the build directory, defaults to the current directory",
    )
    args = parser.parse_args()

    if not args.config_file:
        print("Please specify a configuration file using --config-file argument.")
        return

    # Read config and setup build workspace
    config = parse_config(args.config_file)
    vm_name = config["general"]["name"]

    base_dir = args.build_dir or f"./{vm_name}-build"
    workspace = setup_workspace(base_dir)

    kernel_dir = os.path.join(workspace, "kernel")
    apps_dir = os.path.join(workspace, "applications")
    rootfs_dir = os.path.join(workspace, "rootfs")
    output_dir = os.path.join(base_dir, "output_vms")
    os.makedirs(kernel_dir, exist_ok=True)
    os.makedirs(apps_dir, exist_ok=True)
    os.makedirs(rootfs_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    # Configuring the kernel
    # Handling kernel tarball and directory existence
    kernel_tar_path = os.path.join(
        workspace, f"linux-{config['kernel']['version']}.tar.xz"
    )
    kernel_version = config["kernel"]["version"]
    if not os.path.exists(kernel_tar_path):
        logger.info("Kernel source tarball does not exist, downloading...")
        kernel_url = config["kernel"].get("url")
        download_kernel_source(kernel_version, kernel_tar_path, url=kernel_url)

    logger.info("extracting tar")
    extracted_kernel_dir = extract_kernel_tarball(kernel_tar_path, workspace)

    if os.path.exists(extracted_kernel_dir):
        logger.info("extracted kernel dir exists....")
        kernel_dir = extracted_kernel_dir
    else:
        # If extraction fails or directory does not exist, throw an error
        # TODO: do something productive
        raise Exception("Failed to locate the extracted kernel source directory.")

    configure_kernel(config["kernel"], kernel_dir)
    if "patches" in config["kernel"]:
        apply_patches(config["kernel"]["patches"], kernel_dir)
    apply_default_kernel_options(kernel_dir)
    build_kernel(kernel_dir)

    # TODO: do something better than grabbing the first application
    app_details = get_first_application(config)

    # Download and extract the application
    app_source_dir = download_and_extract_app(app_details, apps_dir)

    image_name = config["output"].get("image_name", "output_image")
    image_path = os.path.join(output_dir, f"{image_name}.qcow2")
    # create_qemu_image(image_path)
    kernel_path = os.path.join(kernel_dir, "arch/arm64/boot/Image")
    initrd_path = os.path.join(output_dir, "rootfs.cpio")

    logger.info(f"Setting up rootfs in {rootfs_dir}")
    setup_rootfs(rootfs_dir)

    # Configure and build the application using the actual source directory path
    configure_and_build_app(app_details, apps_dir, app_source_dir, rootfs_dir)
    # Write a simple init executable and have it run out app's output executable upon VM start
    logger.info(
        f"Compiling init.c with start program {app_details['output_executable_path']}"
    )
    compile_init_c(rootfs_dir, app_details["output_executable_path"])

    # Compile and include an 'ifconfig' replacement in C
    #
    # This negates us from having to include additional common utils
    # in the target VM at the expense of having to...write C code
    if app_details["include_net"] and config["boot"]["network"]:
        # compile_network_config_utility(rootfs_dir)
        compile_and_setup_net_route_utility(
            rootfs_dir,
            ip_address=config["boot"]["network"]["ip_address"],
            netmask=config["boot"]["network"]["netmask"],
            gateway=config["boot"]["network"]["gateway"],
        )
        setup_resolv_conf(rootfs_dir)

    # Copy a vt100 compile terminfo entry to the build system
    #   Needed for any program needed to emulate a terminal
    # TODO: this is mostly a hack and subverts us from having to compile ncurses
    find_and_copy_vt(rootfs_dir)

    copy_kernel_to_output(kernel_dir, output_dir)
    logger.info("Creating uncompressed cpio")
    make_uncompressed_cpio(rootfs_dir, output_dir)
    # logger.info("Setting up boot params")
    # setup_boot_parameters("aarch64",
    #     kernel_path=kernel_path,
    #     initrd_path=initrd_path,
    #     cmdline="noshell initrd=/init root=/dev/ram console=ttyS0,115200",
    #     output_path=output_dir, enable_network=True
    # )
    logger.info("Built image! Done!")

    logger.info(f"Kernel output path {kernel_path}")
    logger.info(f"Initrd output path {initrd_path}")
    # Use script args to optionally clear the workspace after building
    # clean_workspace(workspace)


if __name__ == "__main__":
    main()
