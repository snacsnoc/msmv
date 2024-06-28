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
        binary_mode=False,
        next_command=None,
    ):
        print(f"Running command: {' '.join(command)} in dir {cwd}")
        try:
            # Setup the first process
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE if next_command else stdout,
                stderr=stderr,
                stdin=stdin,
                cwd=cwd,
                shell=shell,
                env=env,
                text=not binary_mode,
            )

            # If there's a next command, set it up to receive input from the first process
            if next_command:
                next_process = subprocess.Popen(
                    next_command,
                    stdin=process.stdout,
                    stdout=stdout,
                    stderr=stderr,
                    cwd=cwd,
                    shell=shell,
                    env=env,
                    text=not binary_mode,
                )
                # Allow process to receive a SIGPIPE if next_process exits
                process.stdout.close()
                output, error = next_process.communicate(timeout=timeout)
                exit_code = next_process.returncode
            else:
                output, error = process.communicate(timeout=timeout)
                exit_code = process.returncode

            if verbose and output:
                print(output.decode() if not binary_mode else output)

            if exit_code != 0:
                error_msg = error.decode() if not binary_mode else error
                print(f"Error executing command: {error_msg}")
                exit(1)

            return output, error
        except subprocess.TimeoutExpired as e:
            process.kill()
            if next_command:
                next_process.kill()
            print(f"Process timed out with error: {e}")
            exit(1)
        except subprocess.CalledProcessError as e:
            print(f"An error occurred: {e}")
            exit(1)
