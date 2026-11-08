"""Start the curator host with pipes for its output and relay them to this process's output.

Under the curator sandbox, node aborts while starting when its standard output is a file the
profile does not allow it to read: it calls fstat on descriptors 0 to 2, and the profile refuses
the metadata of the session record's `host-output.log`. A pipe is not refused. Python starts with
a file as output, so this relay is the sandbox's argv and node's output reaches the log through it.
Usage: python -I launch.py NODE run.mjs --config CONFIG
"""
import subprocess
import sys

child = subprocess.Popen(sys.argv[1:], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
try:
    while chunk := child.stdout.read1(65536):
        sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush()
finally:
    sys.exit(child.wait())
