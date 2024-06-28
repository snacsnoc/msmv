import logging
import os
import shutil
import subprocess

from msmv.util.host_command import HostCommand

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

"""Utility class to assist with application-related operations"""


class ApplicationHelpers:

    """
    This method compiles a statically linked init binary
    This init mounts the required filesystems and conditionally inserts network setup code
    It also boots the target program upon execution, allow users to directly start the target software
    without having to manually start it.

    """

    @staticmethod
    def compile_init_c(output_dir, start_program_path="/bin/sh", include_net=True):
        # Split the start_program_path into parts for argv
        program_parts = start_program_path.split()
        program_args = ", ".join(f'"{part}"' for part in program_parts) + ", NULL"

        # Network configuration with routing
        network_setup_code = """
        int sock = socket(AF_INET, SOCK_DGRAM, 0);
        if (sock >= 0) {
            struct ifreq ifr;
            strncpy(ifr.ifr_name, "eth0", IFNAMSIZ-1);
            if (ioctl(sock, SIOCGIFFLAGS, &ifr) == 0) {
                if (fork() == 0) {
                    // Child process: setup network
                    printf("Network interface eth0 found, configuring...\\n");
                    char *setnet_cmd = "/setnet_r";  // setnet is expected to be configured for eth0 with predefined settings
                    execl(setnet_cmd, setnet_cmd, NULL);
                    perror("Failed to configure network with setnet");
                    exit(1);  // Ensure the child exits if execv fails
                }
            } else {
                perror("Network interface eth0 not found");
            }
            close(sock);
        } else {
            perror("Failed to open socket");
        }
        """

        # Mount required filesystems
        mount_dev_code = """
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
        // Mount devtmpfs on /dev
        if (mount("devtmpfs", "/dev", "devtmpfs", 0, NULL) != 0) {
            perror("Failed to mount devtmpfs on /dev");
            return -1;  // Exit if mount fails
        }
        """

        # Main init code with conditional insertion of network setup
        init_c_code = f"""
        #include <unistd.h>
        #include <stdio.h>
        #include <stdlib.h>
        #include <string.h>
        #include <sys/mount.h> 
        #include <sys/types.h>
        #include <sys/socket.h>
        #include <net/if.h>
        #include <sys/ioctl.h>
        int main(void) {{
            printf("Starting the program...\\n");
            fflush(stdout);
            {mount_dev_code}
            setenv("TERM", "vt100", 1);
            {'// Network configuration' if include_net else '// No network configuration'}
            {network_setup_code if include_net else ''}
            // Start the specified program
            char *argv[] = {{{program_args}}};
            execv(argv[0], argv);
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
        logger.info(
            f"C init script written to {init_c_path} using {start_program_path}"
        )

        # Compile the init program
        init_executable_path = os.path.join(output_dir, "init")
        try:
            HostCommand.run_command(
                ["gcc", init_c_path, "-o", init_executable_path, "-static"],
                cwd=output_dir,
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

    @staticmethod
    def compile_network_standalone_utility(output_dir, file_name="setnet"):
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
            HostCommand.run_command(
                ["gcc", c_file_path, "-o", executable_path, "-static"], cwd=output_dir
            )
            logger.info(f"Compiled {executable_path} successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error compiling {file_name}.c: {str(e)}")

        # Make the binary executable
        os.chmod(executable_path, 0o755)

    """
    Compiles a network configuration utility that sets up an IP address, netmask and route for a given network interface
    """

    @staticmethod
    def compile_and_setup_net_route_utility(
        output_dir,
        file_name="setnet_r",
        interface="eth0",
        ip_address="192.168.0.100",
        netmask="255.255.255.0",
        gateway="192.168.0.1",
    ):
        c_code = f"""
    #include <stdio.h>
    #include <stdlib.h>
    #include <string.h>
    #include <sys/socket.h>
    #include <netinet/in.h>
    #include <net/if.h>
    #include <sys/ioctl.h>
    #include <linux/route.h>  
    #include <unistd.h>
    
    int main() {{
        int fd;
        struct ifreq ifr;
        struct rtentry route;
        struct sockaddr_in *addr;
    
        fd = socket(AF_INET, SOCK_DGRAM, 0);
        if (fd < 0) {{
            perror("Socket creation failed");
            return 1;
        }}
    
        // Setting the IP address
        memset(&ifr, 0, sizeof(ifr));
        strncpy(ifr.ifr_name, "{interface}", IFNAMSIZ);
        addr = (struct sockaddr_in *)&ifr.ifr_addr;
        addr->sin_family = AF_INET;
        inet_pton(AF_INET, "{ip_address}", &addr->sin_addr);
        if (ioctl(fd, SIOCSIFADDR, &ifr) < 0) {{
            perror("SIOCSIFADDR");
        }}
    
        // Set the Netmask
        addr = (struct sockaddr_in *)&ifr.ifr_netmask;
        addr->sin_family = AF_INET;
        inet_pton(AF_INET, "{netmask}", &addr->sin_addr);
        if (ioctl(fd, SIOCSIFNETMASK, &ifr) < 0) {{
            perror("SIOCSIFNETMASK");
        }}
    
        // Set the interface flags
        if (ioctl(fd, SIOCGIFFLAGS, &ifr) != -1) {{
            ifr.ifr_flags |= IFF_UP | IFF_RUNNING;
            if (ioctl(fd, SIOCSIFFLAGS, &ifr) == -1) {{
                perror("SIOCSIFFLAGS");
            }}
        }}
    
        // Setting the default gateway
        memset(&route, 0, sizeof(route));
        addr = (struct sockaddr_in *)&route.rt_dst;
        addr->sin_family = AF_INET;
        addr->sin_addr.s_addr = 0; // default route
    
        addr = (struct sockaddr_in *)&route.rt_gateway;
        addr->sin_family = AF_INET;
        inet_pton(AF_INET, "{gateway}", &addr->sin_addr);
    
        addr = (struct sockaddr_in *)&route.rt_genmask;
        addr->sin_family = AF_INET;
        addr->sin_addr.s_addr = 0;
    
        route.rt_flags = RTF_UP | RTF_GATEWAY;
        route.rt_dev = "{interface}"; // Interface to use
    
        if (ioctl(fd, SIOCADDRT, &route) < 0) {{
            perror("SIOCADDRT");
        }}
    
        close(fd);
        return 0;
    }}
    """

        c_file_path = os.path.join(output_dir, f"{file_name}.c")
        executable_path = os.path.join(output_dir, file_name)

        with open(c_file_path, "w") as c_file:
            c_file.write(c_code)
            logger.info(f"C source written to {c_file_path}")

        # Compile the C source code into a static binary
        try:
            subprocess.run(
                ["gcc", c_file_path, "-o", executable_path, "-static"],
                check=True,
                cwd=output_dir,
            )
            logger.info(f"Compiled {executable_path} successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error compiling {file_name}.c: {str(e)}")

        # Make the binary executable
        os.chmod(executable_path, 0o755)

        return executable_path

    """Find a terminal terminfo file and copy to target destination"""

    @staticmethod
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

    """
        Create /etc directory and add nameserver configuration to resolv.conf in the specified rootfs directory.
    
        Args:
        rootfs_dir (str): The path to the root file system directory where /etc will be created.
    """

    @staticmethod
    def setup_resolv_conf(rootfs_dir):
        etc_path = os.path.join(rootfs_dir, "etc")
        resolv_conf_path = os.path.join(etc_path, "resolv.conf")

        os.makedirs(etc_path, exist_ok=True)

        # Write nameserver configuration to resolv.conf
        with open(resolv_conf_path, "w") as file:
            file.write("nameserver 8.8.8.8\n")
        logger.info(
            f"Created resolv.conf at {resolv_conf_path} with nameserver 8.8.8.8"
        )
