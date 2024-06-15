MuStack MicroVM 
======================

MuStack MicroVM (msmv) is a specialized container build system designed to create and manage minimal, secure, and isolated Linux virtual machine images for microVM environments. 

Using QEMU's [microvm](https://www.qemu.org/docs/master/system/i386/microvm.html) machine type, msmv provides rapid boot times, enhanced security through isolation, and efficient resource management, for developers and hobbyists who require lightweight virtual testing environments.

Imagine Docker, except requiring a lot more effort. It’s like building a ship in a bottle — complex, rewarding, frustrating, and yes, a bit intense!

# Usage
## Configuration

Start by creating a TOML configuration file for your VM. Below is an example configuration for a VM designed to run [Lynx](https://lynx.invisible-island.net/), a text-based web browser:

```toml
[general]
name = "LynxVM"
description = "Lightweight VM running the Lynx text-based web browser"
target_arch = "x86_64"

[kernel]
version = "6.9.4"
url = "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.9.4.tar.xz"
options = { INET = "y", SERIAL = "y", BLOCK = "y", EXPERT="y",PRINTK = "y", SERIAL_AMBA_PL011 = "y", SERIAL_AMBA_PL011_CONSOLE = "y", SERIAL_CORE = "y", SERIAL_CORE_CONSOLE = "y", TTY = "y",  ARM_AMBA = "y", EARLYCON = "y", EARLY_PRINTK = "y",DEV_MEM="y",VIRTIO_CONSOLE="y", BINFMT_ELF="y", CONFIG_BINFMT_SCRIPT="y", VT_CONSOLE="y",VT="y",HW_CONSOLE="y",SERIO_SERPORT="y",ELFCORE="y",CC_OPTIMIZE_FOR_SIZE="y",NO_BOOTMEM="y",SLOB="y",BLK_DEV_INITRD="y",BLK_DEV_RAM="y",SERIAL_DEV_BUS="y",SERIAL_DEV_CTRL_TTYPORT="y",INPUT_MOUSE="n",PROC_FS="y",SYSFS="y",STRIP_ASM_SYMS="y" }


[applications.lynx]
name = "lynx"
version = "2.9.2"
url = "https://invisible-island.net/archives/lynx/tarballs/lynx2.9.2.tar.gz"
config_script = "./configure --disable-ssl CFLAGS=-static LDFLAGS=-static "

[boot]
cmdline = "console=ttyS0"
initramfs = true

[output]
format = "qemu_image"
image_name = "LynxVM.img"

```

For other software, please see the `recipes/` directory for examples.

# Building the Virtual Machine Image
Note: it is recommended to use a virtual environment (venv)

Run the build script with your configuration file:

```bash
python bin/main.py --config-file msvm_config.toml
```
This script will:

* Set up the workspace
* Download and extract the Linux kernel
* Configure and build the kernel
* Download and build the specified applications
* Set up the root filesystem
* Put a smile on your face
* Create the final VM image

# Running the Virtual Machine

After building, you can run the VM with QEMU:


```bash
qemu-system-x86_64 -M microvm -drive file=output_vms/output_image.qcow2,if=virtio -m 128 -nographic -append "console=ttyS0" -qmp unix:/tmp/qmp-socket,server,nowait
```
# VM Management with VMTool

msmv includes `VMTool`, a script for managing the VM lifecycle through the QEMU Machine Protocol (QMP):

```bash
python vmtool.py /tmp/qmp-socket start   # Starts the VM
python vmtool.py /tmp/qmp-socket stop    # Sends a shutdown signal to the VM
python vmtool.py /tmp/qmp-socket status  # Queries the current status of the VM
```

# TODO
* Use build commands defined in recipe versus assuming `make`
* Simplify Linux kernel downloading and optionally specify the download URL
* Create `init` script framework to boot into desired application upon VM start
* Use script argument to use ccache
* Pass cross-compiler env vars (`CC`, etc) to build processes
* Use architecture defined in recipe TOML versus host OS's arch

# Contributing

Please fork the repository, make your changes, and submit a pull request.
# License

This project is licensed under the GPL v3 license.