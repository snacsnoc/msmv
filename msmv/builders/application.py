import logging
import os
import shlex
import tarfile

from msmv.util.host_command import run_command

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


"""Download and extract the application source code."""


def download_and_extract_app(
    app_details, app_dir, common_tarball_name="application.tar.gz"
):
    print(app_details)

    tar_path = os.path.join(app_dir, common_tarball_name)
    # Download the application tarball
    print(f"Downloading tarball to: {tar_path}")
    run_command(["wget", app_details["url"], "-O", common_tarball_name], cwd=app_dir)
    # Extract the application
    logger.info(f"Extracting tarball: {tar_path}. cwd is {app_dir}")
    # Check if the tarball file exists
    if not os.path.isfile(tar_path):
        logger.error("Tarball file does not exist.")
        return None

    run_command(["tar", "-xzf", common_tarball_name, "-C", "."], cwd=app_dir)

    logger.info("Automatically finding the directory name of extracted tarball")

    with tarfile.open(tar_path, "r:gz") as tar:
        top_dir = os.path.commonpath(tar.getnames())
        app_source_dir = os.path.join(app_dir, top_dir)

    return app_source_dir


"""Configure and build the application."""


def configure_and_build_app(app_details, app_dir, app_source_dir, install_dir):
    # Use shlex to split strings a shell would
    config_command = shlex.split(app_details["config_script"])

    # Run the configure script
    logger.info(
        f"Running config script: {' '.join(config_command)} in dir {app_source_dir}"
    )
    run_command(config_command, cwd=app_source_dir)

    logger.info("Config script completed.")

    logger.info("Building application...")
    # Build the application using make
    run_command(["make", "-j8"], cwd=app_source_dir)
    logger.info("Application built.")
    logger.info(f"Installing application to {install_dir}...")
    # Install the application using make
    # TODO: fix assumptions we will always use make
    run_command(["make", "install", f"DESTDIR={install_dir}"], cwd=app_source_dir)
    logger.info("Application installed.")
