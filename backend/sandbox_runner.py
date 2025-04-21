import sys, resource
import pyseccomp as seccomp

# Constants for limits
CPU_TIME_LIMIT = 2  # seconds
MEMORY_LIMIT = 100 * 1024 * 1024  # 100 MB
OUTPUT_LIMIT = 5 * 1024 * 1024  # 5 MB (max stdout/ file size)

# 1. Set resource limits
resource.setrlimit(resource.RLIMIT_CPU, (CPU_TIME_LIMIT, CPU_TIME_LIMIT))
resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
resource.setrlimit(resource.RLIMIT_FSIZE, (OUTPUT_LIMIT, OUTPUT_LIMIT))
# (optional: set RLIMIT_NPROC, RLIMIT_NOFILE as needed)

# 2. Apply seccomp filter: only allow write() to stdout/stderr and exit
flt = seccomp.SyscallFilter(defaction=seccomp.ERRNO(seccomp.errno.EPERM))
# Allow write(fd=stdout)
flt.add_rule(seccomp.ALLOW, "write", seccomp.Arg(0, seccomp.EQ, sys.stdout.fileno()))
# Allow write(fd=stderr)
flt.add_rule(seccomp.ALLOW, "write", seccomp.Arg(0, seccomp.EQ, sys.stderr.fileno()))
# Allow exit (to let the program terminate itself)
flt.add_rule(seccomp.ALLOW, "exit_group")  # exit_group for Python's exit
flt.add_rule(seccomp.ALLOW, "exit")
flt.load()

# 3. Execute the user code
code_file = sys.argv[1]  # the first argument is the path to the user code file
with open(code_file, "r") as f:
    code_source = f.read()

# Run the code in a restricted namespace (no builtins except safe ones, if desired)
# Here we use an empty globals dict (so the code can't access our vars)
# and a minimally populated builtins if extra safety is needed.
exec(compile(code_source, code_file, "exec"), {})
