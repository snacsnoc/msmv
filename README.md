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
name = "NanoVM"
description = "MicroVM environment with customized nano text editor"
target_arch = "aarch64"

[kernel]
version = "6.9.4"
url = "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.9.4.tar.xz"
[kernel.options]
BINFMT_ELF = "y"
BINFMT_SCRIPT = "y"
EXPERT = "y"
SWAP = "n"
UNIX = "y"
TMPFS = "y"
DEVTMPFS = "y"
DEVTMPFS_MOUNT = "y"
PROC_FS = "y"
SYSFS = "y"
BLOCK = "y"
PRINTK = "y"
VT = "y"
VT_CONSOLE = "y"
TTY = "y"
HID_SUPPORT = "n"
UNIX98_PTYS = "y"
SERIO = "y"
DEBUG_INFO_NONE = "y"
PREEMPT_NONE_BUILD = "y"
TINY_RCU = "y"
BLK_DEV_INITRD = "y"
CC_OPTIMIZE_FOR_SIZE = "y"
SERIAL_AMBA_PL011 = "y"
SERIAL_AMBA_PL011_CONSOLE = "y"
SERIAL_CORE = "y"
SERIAL_CORE_CONSOLE = "y"
SERIAL_DEV_BUS = "y"
SERIAL_DEV_CTRL_TTYPORT = "y"



[applications.nano]
name = "Nano"
version = "8.0"
url = "https://www.nano-editor.org/dist/v8/nano-8.0.tar.gz"
config_script = "./configure CFLAGS=-static LDFLAGS=-static"
output_executable_path = "/usr/local/bin/nano"

[boot]
cmdline = "console=ttyAMA0"
initramfs = true

[output]
format = "qemu_image"
image_name = "NanoVM.img"

```

For other software, please see the `recipes/` directory for examples.

# Building the Virtual Machine Image
Note: it is recommended to use a virtual environment (venv)
```bash
python3 -m venv venv
pip install -r requirements.txt 
```

Run the build script with your configuration file:

```bash
python -m msmv.bin.msmv --config-file msvm_config.toml
```
__Options:__
* `-c` or `--config-file` - sets the build (recipe) configuration file
* `-b` or `--build-dir` - sets the build workspace and output directory

__Environment variables:__
* `MAKE_COMMAND` - specify the `make` command, defaults to `make`
  * For Mac OS, I would recommend `lkmake` https://github.com/markbhasawut/mac-linux-kdk
* `CC` - specify the compiler `cc` to be used, defaults to `cc`

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

Examples:
```bash
qemu-system-x86_64 -M microvm -drive file=output_vms/output_image.qcow2,if=virtio -m 128 -nographic -append "console=ttyS0" -qmp unix:/tmp/qmp-socket,server,nowait
```

The `microvm` machine type is not supported for aarch64, so we must use `virt`:
```bash
qemu-system-aarch64 -M virt -cpu max -kernel Image -initrd rootfs.cpio  -append "init=/init rdinit=/init console=ttyAMA0" -serial mon:stdio -nographic 
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
* Apply predefined kernel config sets (serial only, framebuffer, debugging etc) before user's config 
  * To reduce requirement for the user to supply all necessary kconfig options in the recipe file

# Contributing

Please fork the repository, make your changes, and submit a pull request.
# License

This project is licensed under the GPL v3 license.