import logging
import os
import shlex
import tarfile

from msmv.util.host_command import HostCommand

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ApplicationBuilder:
    def __init__(self, config, rootfs_path):
        self.config = config
        self.rootfs_path = rootfs_path
        self.default_make_command = os.getenv("MAKE_COMMAND", "make -j8")

        # Default to 'cc' if not set
        self.compiler = os.getenv("CC", "cc")

        self.linker = os.getenv("LD", "ld")

        # Read from config or use defaults
        self.build_command = self.config.get("build_command", self.default_make_command)
        logger.info(self.config)
        self.install_command = (
            self.config["install_command"] + f" DESTDIR={self.rootfs_path}"
        )

        # Set the environment variables
        self.env = os.environ.copy()
        self.env["CC"] = self.compiler
        self.env["LD"] = self.linker

    """Download and extract the application source code."""

    def download_and_extract_app(
        self, app_details, app_dir, common_tarball_name="application.tar.gz"
    ):
        tar_path = os.path.join(app_dir, common_tarball_name)

        # Check if the tarball file exists and skip downloading if it does
        if not os.path.isfile(tar_path):
            logger.info(f"Tarball not found at {tar_path}. Downloading...")
            HostCommand.run_command(
                ["wget", app_details["url"], "-O", common_tarball_name], cwd=app_dir
            )
        else:
            logger.info(f"Tarball already exists at {tar_path}. Skipping download.")

        # Extract the application
        logger.info(f"Extracting tarball: {tar_path}. cwd is {app_dir}")
        # Check if the tarball file exists
        if not os.path.isfile(tar_path):
            logger.error("Tarball file does not exist.")
            return None

        HostCommand.run_command(
            ["tar", "-xzf", common_tarball_name, "-C", "."], cwd=app_dir
        )

        logger.info("Automatically finding the directory name of extracted tarball")

        with tarfile.open(tar_path, "r:gz") as tar:
            top_dir = os.path.commonpath(tar.getnames())
            app_source_dir = os.path.join(app_dir, top_dir)

        return app_source_dir

    """Configure and build the application."""

    def setup_and_build_app(self, app_dir):
        app_source_dir = self.download_and_extract_app(self.config, app_dir)

        # Check if the recipe has a config script (pre-compilation) command
        if self.config.get("config_script") is not None:
            self.configure_app(self.config, app_source_dir)

        # TODO: check if compilation is successful before installing
        self.compile_app(app_source_dir)
        self.install_app_to_output(app_source_dir)
        self.check_compiled_app()

    def configure_app(self, app_details, app_source_dir):
        # Use shlex to split strings a shell would
        config_command = shlex.split(app_details["config_script"])

        # Run the configure script
        logger.info(
            f"Running config script: {' '.join(config_command)} in dir {app_source_dir}  with {self.linker} {self.compiler}"
        )
        HostCommand.run_command(config_command, cwd=app_source_dir, env=self.env)

        logger.info("Config script completed.")

    def compile_app(self, app_source_dir):
        logger.info(f"Building application")

        # Use the build command from the TOML file or the default if not specified
        HostCommand.run_command(
            shlex.split(self.build_command), cwd=app_source_dir, env=self.env
        )
        logger.info("Application built.")

    def check_compiled_app(self):
        # Get the first component of the path before any spaces
        output_executable = self.config["output_executable_path"].split()[0]
        output_executable_path = output_executable.lstrip("/")

        # Construct the full path to the executable within the root filesystem
        built_app = os.path.join(self.rootfs_path, output_executable_path)
        # Check if the output file exists
        if not os.path.exists(built_app):
            logger.error(
                f"Application not found at {built_app} in rootfs {self.rootfs_path}"
            )
            exit(1)

    def install_app_to_output(self, app_source_dir):
        logger.info(self.config.get("application", {}))
        logger.info(f"Installing application with {self.install_command}")

        HostCommand.run_command(
            shlex.split(self.install_command), cwd=app_source_dir, env=self.env
        )
