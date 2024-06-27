import subprocess

"""Utility class to execute shell commands in a subprocess on the host OS"""


class HostCommand:
    @staticmethod
    def run_command(
        command,
        cwd,
        timeout=None,
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        env=None,
        verbose=False,
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
                env=env,
            ) as process:
                try:
                    if verbose:
                        for line in process.stdout:
                            print(line, end="")
                    else:
                        # Wait for the process to complete and get stderr
                        stdout, stderr = process.communicate(timeout=timeout)
                        if stdout:
                            print(stdout)
                        if stderr:
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
