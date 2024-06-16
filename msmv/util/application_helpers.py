import logging
import os
import shutil
import subprocess

from msmv.util.host_command import run_command

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


""" DEBUG: A simple C init to run upon VM start"""


def compile_init_c(output_dir, start_program_path="/bin/sh", include_net=True):
    # Network configuration
    network_setup_code = """
    char *setnet_args[] = {"/setnet", "eth0", "192.168.0.100", "255.255.255.0", NULL};
    printf("Configuring network...\\n");
    execv("/setnet", setnet_args);
    perror("Failed to configure network with setnet");
    """

    # Mount required filesystems
    mount_dev_code = """
    // Mount devtmpfs on /dev
    if (mount("devtmpfs", "/dev", "devtmpfs", 0, NULL) != 0) {
        perror("Failed to mount devtmpfs on /dev");
        return -1;  // Exit if mount fails
    }
    // Mount proc filesystem
    if (mount("proc", "/proc", "proc", 0, NULL) != 0) {
        perror("Failed to mount proc on /proc");
        return -1;  
    }
    // Mount sysfs filesystem
    if (mount("sysfs", "/sys", "sysfs", 0, NULL) != 0) {
        perror("Failed to mount sysfs on /sys");
        return -1;  
    }
    """

    # Main init code with conditional insertion of network setup
    init_c_code = f"""
    #include <unistd.h>
    #include <stdio.h>
    #include <stdlib.h>
    #include <sys/mount.h> 
    int main(void) {{
        printf("Starting the program...\\n");
        fflush(stdout);
        {mount_dev_code}
        setenv("TERM", "vt100", 1);
        {'// Network configuration' if include_net else '// No network configuration'}
        {network_setup_code if include_net else ''}
        // Start the specified program
        char *argv[] = {{"{start_program_path}", NULL}};
        execv("{start_program_path}", argv);
        perror("Failed to start the specified program");
        while (1) {{
            sleep(1);
        }}
        return 0;
    }}
"""
    init_c_path = os.path.join(output_dir, "init.c")
    with open(init_c_path, "w") as file:
        file.write(init_c_code)
    logger.info(f"C init script written to {init_c_path} using {start_program_path}")

    # Compile the init program
    init_executable_path = os.path.join(output_dir, "init")
    try:
        run_command(
            ["gcc", init_c_path, "-o", init_executable_path, "-static"], cwd=output_dir
        )
        logger.info(f"Compiled init executable to {init_executable_path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to compile init.c: {e}")

    # Make sure the init executable is executable
    os.chmod(init_executable_path, 0o755)


"""
Compiles a network configuration utility that sets up IP address and netmask for a given network interface
Use with: setnet eth0 192.168.0.10 255.255.255.0
"""


def compile_network_config_utility(output_dir, file_name="setnet"):
    c_code = """
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <net/if.h>
#include <sys/ioctl.h>
#include <unistd.h>

int main(int argc, char *argv[]) {
    int fd;
    struct ifreq ifr;
    struct sockaddr_in* addr;

    if (argc != 4) {
        printf("Usage: %%s <interface> <ip address> <netmask>\\n", argv[0]);
        return 1;
    }

    fd = socket(AF_INET, SOCK_DGRAM, 0);
    if(fd < 0) {
        perror("Socket");
        return 1;
    }

    // Get interface name
    strncpy(ifr.ifr_name, argv[1], IFNAMSIZ);

    // Set IP address
    addr = (struct sockaddr_in *)&ifr.ifr_addr;
    addr->sin_family = AF_INET;
    inet_pton(AF_INET, argv[2], &addr->sin_addr);
    if (ioctl(fd, SIOCSIFADDR, &ifr) < 0) {
        perror("SIOCSIFADDR");
    }

    // Set Netmask
    inet_pton(AF_INET, argv[3], &addr->sin_addr);
    if (ioctl(fd, SIOCSIFNETMASK, &ifr) < 0) {
        perror("SIOCSIFNETMASK");
    }

    // Bring interface up
    ifr.ifr_flags |= (IFF_UP | IFF_RUNNING);
    if (ioctl(fd, SIOCSIFFLAGS, &ifr) < 0) {
        perror("SIOCSIFFLAGS");
    }

    close(fd);
    return 0;
}
"""
    c_file_path = os.path.join(output_dir, file_name + ".c")
    executable_path = os.path.join(output_dir, file_name)

    with open(c_file_path, "w") as c_file:
        c_file.write(c_code)
        logger.info(f"C source written to {c_file_path}")

    # Compile the C source code into a static binary
    try:
        run_command(
            ["gcc", c_file_path, "-o", executable_path, "-static"], cwd=output_dir
        )
        logger.info(f"Compiled {executable_path} successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error compiling {file_name}.c: {str(e)}")

    # Make the binary executable
    os.chmod(executable_path, 0o755)


"""Find a terminal terminfo file and copy to target destination"""


def find_and_copy_vt(dest_dir):
    # Define the terminfo name we are looking for
    terminfo_name = "vt100"

    # Locate the vt100 file from a common base directory
    try:
        result = subprocess.run(
            ["find", "/usr/share/terminfo", "-name", terminfo_name],
            capture_output=True,
            text=True,
            check=True,
        )
        files = result.stdout.strip().split("\n")
    except subprocess.CalledProcessError as e:
        print(f"Failed to find terminfo files: {str(e)}")
        return

    terminfo_base_dir = os.path.join(dest_dir, "usr", "share", "terminfo", "v")
    os.makedirs(terminfo_base_dir, exist_ok=True)
    # Copy located files to the target directory
    for file_path in files:
        if file_path:
            dest_path = os.path.join(terminfo_base_dir, "vt100")
            shutil.copy(file_path, dest_path)
            logger.info(f"Copied {file_path} to {dest_path}")
        else:
            logger.debug("No vt100 terminfo files found on the system.")
