import subprocess

"""Execute shell commands in a subprocess on the host OS"""


def run_command(
    command,
    cwd,
    timeout=None,
    shell=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    stdin=subprocess.PIPE,
):
    print(f"Running command: {' '.join(command)} in dir {cwd}")
    try:
        with subprocess.Popen(
            command,
            stdout=stdout,
            stderr=stderr,
            stdin=stdin,
            text=True,
            cwd=cwd,
            shell=shell,
        ) as process:
            try:
                for line in process.stdout:
                    # Real-time feedback from stdout
                    print(line, end="")
                # Wait for the process to complete and get stderr
                stderr = process.communicate(timeout=timeout)[1]
                print(stderr)
                if process.returncode != 0:
                    print("Error executing command:", stderr)
                    exit(1)
            except subprocess.TimeoutExpired:
                process.kill()
                _, stderr = process.communicate()
                print(f"Process timed out with error: {stderr}")
                exit(1)
    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")
        exit(1)
