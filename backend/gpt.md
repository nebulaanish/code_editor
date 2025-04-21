Great. I’ll research how to build a FastAPI-based service that accepts and securely executes Python code submitted via API requests from multiple hosts, distinguishing each host, and running the code in a secure, efficient sandboxed environment (without Docker). The system should support local and cloud deployment (AWS-friendly but not vendor-specific).

I’ll look into best practices for secure sandboxing alternatives, host identification strategies, and architecture design for FastAPI with concurrent request handling and isolation.

I’ll share back a proposed architecture, libraries/tools to use, and example implementation patterns.

# Secure FastAPI Architecture for Running Untrusted Python Code

## Architecture Overview

The service will be structured as a FastAPI application providing a POST endpoint (e.g., `/execute`) to receive Python code. Each request includes the code to run and a host identifier (such as an API token or custom header) to distinguish the calling client. The API server does not execute the code in its own process; instead, it launches a **separate sandboxed subprocess** for each request to run the untrusted code safely. Once execution is finished (or times out), the subprocess’s output (stdout/stderr) is captured and returned in the HTTP response. This design ensures that multiple hosts can call the API concurrently, each execution isolated in its own process.

Key components of the architecture:

- **FastAPI Endpoint:** Accepts a code payload via POST. Uses a Pydantic model or raw text body for the code. A custom header or token (e.g. `X-API-Key` or `Authorization` token) is used to identify the client host, allowing the server to log usage and apply per-host policies.
- **Request Handling:** Upon receiving a request, the FastAPI app spawns a new **sandbox process** to run the code. This can be done by invoking a Python interpreter or script in a restricted environment. The main server process **never directly executes the untrusted code** – it only manages subprocesses.
- **Concurrency:** Each request is handled in parallel. FastAPI will use an external thread or asyncio task to manage each incoming request without blocking others. In fact, if you define the endpoint as a normal `def` (synchronous function), FastAPI automatically runs it in a threadpool so that it doesn’t block the event loop ([python - FastAPI runs API calls in serial instead of parallel fashion - Stack Overflow](https://stackoverflow.com/questions/71516140/fastapi-runs-api-calls-in-serial-instead-of-parallel-fashion#:~:text=As%20per%20FastAPI%27s%20docs%3A)). This means multiple code executions can run simultaneously in separate sandbox processes. For CPU-bound code, you can also run multiple Uvicorn/Gunicorn worker processes to leverage multiple CPU cores – for example, the open-source *snekbox* sandbox uses two Gunicorn workers, meaning two code runs can happen at the same time by default ([GitHub - python-discord/snekbox: Easy, safe evaluation of arbitrary Python code](https://github.com/python-discord/snekbox#:~:text=Gunicorn)).
- **Result Delivery:** The sandbox process sends its output (standard output and errors) back to the FastAPI server (typically via pipes). The server collects this output, associates it with the requesting host ID, and returns it in the HTTP response (usually as JSON with `stdout` and `stderr` fields, or just raw text).

This architecture isolates execution per request. Even if two requests arrive from different hosts, their code runs in **separate processes** with no shared global state, preventing interference. The host identifier from each request can be used to implement logging, per-host rate limiting, or even routing to per-host sandboxes if needed (for example, one could maintain a persistent sandbox container per host for performance, though the default is to use ephemeral processes for each call).

## Host Identification and Multi-Client Handling

To distinguish among multiple client hosts, the API should require some form of authentication or identification in each request. A simple approach is to use API keys or tokens:

- **API Key Header:** Issue each authorized host a unique API key and require it in a header (e.g., `X-API-Key: <token>`). In FastAPI, you can use dependencies to verify this token and retrieve a host identity. For example, a dependency could look up the token in a database or in-memory dict to ensure it’s valid and map it to a host name/ID.
- **Host Isolation:** The host ID can be used to isolate runs if necessary. In the basic design, isolation is per request (process-level isolation), so one host’s code cannot affect another’s. If the use-case ever requires maintaining state per host (for instance, a persistent workspace or file storage between calls), you could implement a dedicated sandbox per host (e.g., each host gets its own container or persistent process). However, this adds complexity and state management – by default, the system will treat every execution as a one-off, stateless run. This statelessness is actually a security advantage, because each run starts fresh and any malicious side-effects (filesystem changes, memory consumption) are discarded when the sandbox process exits.
- **Logging and Limits per Host:** With host identification, you can log each execution with the host ID and perhaps the resource usage. This makes it easier to audit activity or to apply per-host limits (e.g., a particular host is only allowed N runs per minute or a lower CPU time limit, etc.). Such policies are enforced at the application level on top of the core sandboxing.

In summary, the FastAPI app will ensure each request includes valid credentials identifying the caller, and it will spawn isolated processes so that code from one host never runs in the same process as another host’s code. This separation naturally supports multi-tenant concurrent use.

## Concurrent Execution and FastAPI Patterns

FastAPI is built to handle many requests concurrently, and we leverage that for running multiple code executions in parallel. There are a few important patterns to ensure efficient and safe concurrency:

- **Threaded Execution:** Because running an external process is an I/O-bound operation (waiting on the process to complete), you can use a standard blocking call in a normal function. FastAPI will offload it to a thread so that other requests aren’t blocked ([python - FastAPI runs API calls in serial instead of parallel fashion - Stack Overflow](https://stackoverflow.com/questions/71516140/fastapi-runs-api-calls-in-serial-instead-of-parallel-fashion#:~:text=As%20per%20FastAPI%27s%20docs%3A)). For example, your endpoint can call `subprocess.run()` or `Popen.communicate()` to execute the code; FastAPI’s threadpool will handle it asynchronously under the hood. Each request will use one thread until its sandboxed process finishes.
- **Async Execution:** Alternatively, you can make the endpoint an `async def` and use `await asyncio.create_subprocess_exec()` (from Python’s asyncio) to launch the subprocess. This avoids occupying a thread per request by leveraging the event loop to await the process completion. Both approaches are fine – the threaded approach is simpler to implement, while the async subprocess approach may scale better if you expect **very high** concurrency with many idle/waiting periods.
- **Multiple Workers:** If the code being run is CPU-intensive, remember that Python’s GIL won’t be a bottleneck here since each code runs in a separate **process**. To utilize multiple CPU cores for truly parallel execution, you can run the FastAPI app with multiple worker processes (e.g., `uvicorn --workers 4`). Each worker can handle sandbox processes independently. This way, even if one user’s code saturates one CPU core, other workers on other cores can still serve additional requests. The number of workers effectively caps how many code executions run at the exact same time (for synchronous endpoints) ([GitHub - python-discord/snekbox: Easy, safe evaluation of arbitrary Python code](https://github.com/python-discord/snekbox#:~:text=Gunicorn)), but asynchronous subprocess calls could even overlap more tasks if the OS can schedule them.
- **Avoiding Bottlenecks:** Ensure that any coordination around starting the subprocess is not itself a bottleneck. For example, if you maintain a pool of sandbox processes, access to that pool should be thread-safe. However, a simpler model is to spawn a new process for each request and let it terminate after – this avoids needing a pool and is easier to reason about (the overhead of spawning a process for each request is usually acceptable for code execution use-cases, which tend to be heavier than a simple web request). If the volume of requests is extremely high, you might introduce a queue to rate-limit how many code processes run simultaneously (to avoid overload). This can be as simple as using an `asyncio.Semaphore` around process launches or as involved as a task queue system.

**FastAPI Implementation Example:** Below is a conceptual snippet showing how the endpoint might be implemented. It uses a blocking subprocess call inside a normal def route, which FastAPI will handle in a separate thread for concurrency:

```python
from fastapi import FastAPI, Header, HTTPException
import subprocess, tempfile, os

app = FastAPI()

@app.post("/execute")
def execute_code(code: str, x_api_key: str = Header(...)):
    # 1. Authenticate/authorize the host using the API key
    host_id = authenticate_api_key(x_api_key)
    if not host_id:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    
    # 2. Write code to a temporary file (isolated from other runs)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write(code)
        code_file = tmp.name

    try:
        # 3. Run the code in a sandboxed subprocess with security options
        result = subprocess.run(
            ["python3", "sandbox_runner.py", code_file],  # sandbox_runner will apply sandboxing
            capture_output=True, text=True, timeout=5  # impose a timeout for safety
        )
    except subprocess.TimeoutExpired:
        # If the code runs too long, kill the process
        result = None
        # (The sandbox_runner can also enforce an internal timeout)
    finally:
        os.remove(code_file)  # Clean up the temp file

    # 4. Prepare output
    if result is None:
        return {"error": "Execution timed out"}
    else:
        return {"stdout": result.stdout, "stderr": result.stderr}
```

In this example, `sandbox_runner.py` would be a helper script that sets up the sandbox (resource limits, etc., discussed below) and then executes the user’s code file. We use a temp file to avoid shell quoting issues and to have the code on disk for the sandbox process. We also ensure to delete the temp file after execution. The `timeout=5` in `subprocess.run` ensures we don’t wait forever on hung or long-running code – if the process doesn’t complete in 5 seconds, we treat it as a timeout (and `sandbox_runner.py` could also self-terminate after certain limits). The API key is checked at the start to recognize the host; `authenticate_api_key` would be your function to validate the token (not shown). 

In practice, you might refine this with an async approach or more robust management, but it illustrates the flow: receive request -> write code to file -> run sandboxed process -> capture output -> respond.

## Sandboxing and Security Measures

The most critical part of this system is the **sandbox**: the isolated environment in which the untrusted Python code will run. The goal is to prevent malicious or buggy code from affecting the host system or other users’ code. We achieve this by combining several techniques:

**1. Process Isolation with Resource Limits:**  
Each code execution runs in a separate OS process which we tightly control. We can leverage the POSIX `fork/exec` model and Linux resource limits to contain what the process can do:

- **Resource Limits (rlimit):** Before running the untrusted code, set strict limits on CPU time, memory usage, and output file size for the process. Python’s built-in `resource` module wraps the `setrlimit` system call ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=import%20resource)) ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=resource)). For example:
  - `RLIMIT_CPU`: Limit the CPU time (in seconds) the process can consume. This prevents endless loops from hogging a core indefinitely ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=As%20well%20as%20system%20calls%2C,eating%20up%20a%20CPU%20core)).
  - `RLIMIT_AS`: Limit the total memory (address space) the process can allocate ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=import%20resource)). This stops the code from consuming all RAM (e.g., via large lists or infinite recursion).
  - `RLIMIT_FSIZE`: Limit the size of any file that can be created by the process ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=resource)). This can effectively cap how much data the process can write to the disk or to its output streams. For instance, you might set this so that even if the code tries to `print` an enormous amount of text, it will be cut off after a certain number of bytes.
  - Other useful limits include `RLIMIT_NPROC` (number of child processes/threads – to prevent fork bombs) and `RLIMIT_NOFILE` (number of open file descriptors – to prevent the process from opening too many files or sockets). These ensure one sandboxed run can’t spawn dozens of processes or exhaust OS file handles.

  In practice, the sandbox runner (the child process) would call `resource.setrlimit` for each of these before executing user code. For example, one could set `resource.RLIMIT_AS` to a few hundred MB and `resource.RLIMIT_CPU` to a couple of seconds ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=import%20resource)) ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=resource)). Once set, these limits *cannot* be raised by the process itself (they are enforced by the kernel). This means if the Python code tries to use more CPU or memory than allowed, the kernel will terminate it (or the allocation will fail).

- **Subprocess Isolation:** By running code in a subprocess (and not in the main server process), we achieve a basic level of isolation. If the process crashes or is killed due to limits, the main server remains unaffected (aside from handling the error). This is far safer than something like `exec()` in the main process. As one developer noted, their approach was to **spin up a new Python process for each code execution** and apply limits *inside that process* before executing the guest code ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=When%20the%20API%20receives%20some,step%2C%20the%20process%20isn%27t%20trusted)). That way, “after this last step, the process isn’t trusted” ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=When%20the%20API%20receives%20some,step%2C%20the%20process%20isn%27t%20trusted)) – meaning if it does something nasty, it can only harm that sandbox process, which is disposable.

**2. System Call Filtering (seccomp):**  
Even with resource limits, a malicious script might try to perform syscalls to interact with the system (open files, create sockets, etc.). Linux **seccomp** (secure computing mode) allows us to filter which system calls the sandboxed process is permitted to use. In the strictest seccomp mode, a process can be limited to basically nothing except exiting or writing to already-open file descriptors ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=For%20my%20sandbox%2C%20the%20layer,to%20already%20open%20file%20descriptors)). We can use a seccomp **filter** (BPF rules) to create a whitelist of allowed syscalls:

- Using the Python library **pyseccomp**, the sandbox process can install a filter on itself. For example, one can initialize seccomp with a default action of denying calls (`EPERM` error) and then allow only specific syscalls. A minimal policy might allow `write()` to stdout/stderr and `exit()` and nothing else ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=filter%20%3D%20seccomp)) ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=seccomp.ALLOW%2C%20)). This means any attempt by the code to open files, fork processes, access the network, or do other syscalls will be blocked by the kernel with a permission error. The untrusted code will effectively be trapped in a small box – it can compute and write output, but not much else.
- In the sandbox runner, after setting rlimits, you would load such a seccomp filter. For instance, in Python:
  ```python
  import pyseccomp
  flt = pyseccomp.SyscallFilter(defaction=pyseccomp.Action.ERRNO(errno.EPERM))
  flt.add_rule(pyseccomp.Action.ALLOW, "write", arg0=pyseccomp.Arg(0, pyseccomp.CMP_EQ, sys.stdout.fileno()))
  flt.add_rule(pyseccomp.Action.ALLOW, "write", arg0=pyseccomp.Arg(0, pyseccomp.CMP_EQ, sys.stderr.fileno()))
  flt.add_rule(pyseccomp.Action.ALLOW, "exit")  # allow process to exit
  flt.load()
  ```
  This is illustrative – in practice you may need to allow a handful of other syscalls for Python to run without crashing (e.g., `futex` for threading, `mmap` for memory, etc., which can be determined and allowed in a limited way). The idea, however, is that we **block any syscall that isn’t absolutely necessary**. So even if the Python code tries something tricky like opening `/etc/passwd` or creating a socket, the kernel will prevent it. As Andrew Healey noted, when using a separate process as a sandbox, we want the process to *hit a permissions error rather than succeeding* if it tries something disallowed ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=When%20using%20a%20separate%20process,run%20into%20a%20permissions%20issue)) ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=the%20program%20and%20the%20system,run%20into%20a%20permissions%20issue)). Seccomp provides that: for example, deleting a system file from inside the sandbox will just yield an `EPERM: operation not permitted` error ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=When%20using%20a%20separate%20process,run%20into%20a%20permissions%20issue)).

- **No Docker Required:** Both the resource limits and seccomp approaches work at the OS level without needing full containerization. The sandboxed process is simply a normal Linux process with extra restrictions applied. This keeps things lightweight – no need to spin up a Docker container for each run. (Containers internally use similar mechanisms like cgroups and seccomp anyway.)

**3. Namespaces and Jail Tools (Filesystem & Network Isolation):**  
To further isolate the process, we can leverage Linux namespaces – either manually or via tools like **NsJail** or **Firejail**:

- **Filesystem Namespace:** We can give the process a different view of the filesystem. For example, using a mount namespace or chroot, the process could be restricted to an empty or limited directory tree. In practice, a simple way is to launch the process in a certain directory that contains only what’s needed (perhaps just a temp directory). The untrusted code should not be able to see the host’s filesystem aside from this sandbox directory. Tools like NsJail make this easy by letting you configure a **read-only filesystem** mapping for the process ([GitHub - python-discord/snekbox: Easy, safe evaluation of arbitrary Python code](https://github.com/python-discord/snekbox#:~:text=,home)). For instance, you might allow read-only access to the Python standard library (so that Python can import modules) but no access to sensitive paths. NsJail can also mount a fresh `tmpfs` (in-memory filesystem) as the working directory for each run ([GitHub - python-discord/snekbox: Easy, safe evaluation of arbitrary Python code](https://github.com/python-discord/snekbox#:~:text=,home)) ([GitHub - python-discord/snekbox: Easy, safe evaluation of arbitrary Python code](https://github.com/python-discord/snekbox#:~:text=Memory%20File%20System)) – meaning the code can create files only in an ephemeral in-memory space that disappears after execution ([GitHub - python-discord/snekbox: Easy, safe evaluation of arbitrary Python code](https://github.com/python-discord/snekbox#:~:text=On%20each%20execution%2C%20the%20host,access%20another%20instance%27s%20writeable%20directory)) ([GitHub - python-discord/snekbox: Easy, safe evaluation of arbitrary Python code](https://github.com/python-discord/snekbox#:~:text=access%20to%20other%20files%20or,access%20another%20instance%27s%20writeable%20directory)). This is exactly how the Python Discord “snekbox” sandbox operates: *“Restricted, read-only system filesystem and a memory-based read-write filesystem mounted as working directory `/home`”* ([GitHub - python-discord/snekbox: Easy, safe evaluation of arbitrary Python code](https://github.com/python-discord/snekbox#:~:text=,home)). Each code execution gets an isolated `/home` that no other execution can see ([GitHub - python-discord/snekbox: Easy, safe evaluation of arbitrary Python code](https://github.com/python-discord/snekbox#:~:text=On%20each%20execution%2C%20the%20host,access%20another%20instance%27s%20writeable%20directory)).
- **Network Namespace:** By default, we likely want to disable all network access for the untrusted code. This can be achieved by running the sandbox process in a network namespace with no external interfaces. Tools like Firejail and NsJail have flags to turn off networking. For example, Firejail can simply be invoked with `--net=none` to block network ([On using firejail for network isolation in tests | by George Shuklin](https://medium.com/@george.shuklin/on-using-firejail-for-network-isolation-in-tests-42f018ecdcac#:~:text=Shuklin%20medium,net%3Dnone%20py.test%20path_to_my_tests)), and NsJail’s config can disable networking as well ([GitHub - python-discord/snekbox: Easy, safe evaluation of arbitrary Python code](https://github.com/python-discord/snekbox#:~:text=,home)). This ensures the code cannot call out to external servers (or leak data).
- **User Namespace / Privileges:** Ideally, the sandbox process should run with as few privileges as possible. If your main server is running as a non-root user, the sandbox inherits that (which is good). If you need to use root to set up namespaces, then inside the sandbox you should drop privileges back to a nobody user. Firejail, for instance, will drop capabilities and can run the app as an unprivileged user within the sandbox. In summary, the process should not have the ability to do privileged actions. Even if someone somehow escaped the Python layer, they should find themselves as a non-privileged OS user in a minimal environment.

- **NsJail:** NsJail is a popular sandboxing tool that programmatically uses namespaces, cgroups, and seccomp behind the scenes. In the architecture of snekbox, the FastAPI-like service hands off the code to NsJail, which then spawns the Python process inside the jail ([GitHub - python-discord/snekbox: Easy, safe evaluation of arbitrary Python code](https://github.com/python-discord/snekbox#:~:text=actor%20Client%20participant%20Snekbox%20participant,participant%20Python%20as%20Python%20Subprocess)) ([GitHub - python-discord/snekbox: Easy, safe evaluation of arbitrary Python code](https://github.com/python-discord/snekbox#:~:text=Client%20,Client%3A%20JSON%20response)). NsJail allows setting a time limit, memory limit, process count limit, disabling network, and constraining filesystem, all via a config or command-line options ([GitHub - python-discord/snekbox: Easy, safe evaluation of arbitrary Python code](https://github.com/python-discord/snekbox#:~:text=,home)). For example, you might configure NsJail with a 2-second CPU limit, 100 MB memory limit, no networking, and only `/usr/lib/python3.x` mounted read-only plus an empty `/tmp` for writes. The Python subprocess is executed inside this jail and cannot escape these constraints. Once it finishes, NsJail collects the output and returns it. The overhead of NsJail is low (it’s a single process that uses Linux kernel features, not a full VM). The downside is you need to have NsJail installed and, typically, run the service with root privileges or certain capabilities to use it. If using NsJail, your FastAPI code would invoke it like:  
  ```bash
  nsjail --config snekbox.cfg -- /usr/bin/python3 /tmp/code.py
  ``` 
  (This assumes `snekbox.cfg` contains the namespace/seccomp settings and `/tmp/code.py` is the user code.) The Python Discord team notes that using NsJail, they truncate the output to ~1 MB by default to avoid overloading responses ([GitHub - python-discord/snekbox: Easy, safe evaluation of arbitrary Python code](https://github.com/python-discord/snekbox#:~:text=The%20code%20is%20executed%20in,for%20sandboxing%20the%20Python%20process)). This is a good practice to emulate – you can set a max output size to return to the client so that your service isn’t sending gigabytes of data if someone prints a huge loop.
- **Firejail:** Firejail is another sandbox tool that is easier to use via command line. It’s a lightweight SUID program that sets up a sandbox using Linux namespaces and seccomp internally ([netblue30/firejail: Linux namespaces and seccomp-bpf sandbox](https://github.com/netblue30/firejail#:~:text=netblue30%2Ffirejail%3A%20Linux%20namespaces%20and%20seccomp,potentially%20untrusted%29)) ([Security by sandboxing: Firejail vs bubblewrap vs other alternatives](https://www.reddit.com/r/linux/comments/knjzf2/security_by_sandboxing_firejail_vs_bubblewrap_vs/#:~:text=I%20use%20firejail%20to%20run,files%20and%20network)). Firejail can restrict network, filesystem, and capabilities easily. For example, you could run:  
  ```bash
  firejail --net=none --private cacldir --seccomp python3 /tmp/code.py
  ``` 
  This would run Python with no network, a private temporary home directory, and a default seccomp profile. Firejail *“creates lightweight sandboxes around applications, isolating them from the rest of the system and restricting their access to resources.”* ([Secure Your Applications with Firejail: A Linux Sandbox Tutorial - DEV Community](https://dev.to/vlythr/secure-your-applications-with-firejail-a-step-by-step-linux-sandbox-tutorial-4f9b#:~:text=Firejail%20is%20a%20powerful%20sandboxing,why%20you%20should%20use%20it)). It’s user-friendly and comes with profiles for common programs, though for a custom use like this you’d write a simple profile (or just use flags). Firejail’s advantage is ease of use; however, like NsJail it requires having the binary installed and possibly some privileges. 
- **Comparison and Choice:** Using **OS-level sandboxing** (namespaces + seccomp) via tools is generally more secure than trying to implement everything in Python, because these tools cover edge cases and are well-tested. NsJail offers fine-grained control and is designed for programmatic use (e.g., it can run as part of a server, as seen in snekbox). Firejail is more of an end-user tool but can be scripted as well. If Docker/containers are off the table per request, NsJail or Firejail are strong alternatives. Another alternative could be to run a *single* Docker container that is always running and accept code to execute inside it (to amortize startup cost), but that requires a more complex setup (you’d need an API inside the container to run code, akin to how you might manage a pool of worker containers). For simplicity, a new process with seccomp/rlimit (Andrew’s approach) or a jailed process via NsJail is recommended.

**4. Example: In-Process Sandboxing vs External:**  
One approach (as demonstrated by Andrew Healey ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=When%20the%20API%20receives%20some,step%2C%20the%20process%20isn%27t%20trusted))) is to perform the sandbox setup within the Python runner process itself (using `resource` and `pyseccomp`). Another approach is to call an external sandbox (like NsJail) from the FastAPI server. Both achieve similar isolation, but with different trade-offs:

- *Embedded Sandbox (Python-level):* The runner script starts, sets limits and seccomp, then uses Python’s `exec()` to run the untrusted code. This is relatively straightforward to implement in Python code. However, you have to be careful to allow just enough for Python to run. For instance, even basic operations might require certain syscalls (memory allocation, importing modules will open files, etc.). So you will fine-tune the seccomp filter to not break legitimate code. This approach is lightweight (no external dependencies besides `pyseccomp` and standard library). It runs with user privileges, meaning you don’t need root. **Important:** The sandbox code should be small and well-audited since it runs before seccomp is in place. (In the runner, you’d apply seccomp *before* executing user code, but the runner’s own setup code runs with normal privileges – keep that surface minimal).
- *External Sandbox (NsJail/Firejail):* This offloads the heavy lifting to a dedicated tool. You would prepare the code (maybe write to a file) and then invoke the tool to run that file. This requires the server to have sufficient permission (for NsJail, typically CAP_SYS_ADMIN and others to create namespaces; for Firejail, the binary is SUID root to create the sandbox). The advantage is these tools are designed to be secure and can be updated independently if vulnerabilities are found. The downside is an extra component to manage and configure. Still, many have taken this route for robust security.

Given the requirements (no full Docker per request, Linux environment), the recommended solution is to use a **sandboxed subprocess per request** with a combination of **`setrlimit`** and **seccomp**. You can implement that either entirely in Python (with `pyseccomp`) or by invoking a tool like NsJail which applies those restrictions for you. The end result is similar: the untrusted code runs with strict limits on CPU/memory, no ability to open arbitrary files or network connections, and is fully isolated from other executions.

## Implementation Snippets and Library Usage

To illustrate the implementation, let’s outline the two main parts: the **sandbox runner** and the **FastAPI integration**.

**Sandbox Runner Script (sandbox_runner.py):** This script will be executed in a new process to run user code. Its responsibilities are: set up resource limits, apply seccomp filters, execute the user code, then exit. For example:

```python
# sandbox_runner.py
import sys, resource
import pyseccomp as seccomp

# Constants for limits
CPU_TIME_LIMIT = 2       # seconds
MEMORY_LIMIT   = 100*1024*1024   # 100 MB
OUTPUT_LIMIT   = 5*1024*1024     # 5 MB (max stdout/ file size)

# 1. Set resource limits
resource.setrlimit(resource.RLIMIT_CPU, (CPU_TIME_LIMIT, CPU_TIME_LIMIT))
resource.setrlimit(resource.RLIMIT_AS,  (MEMORY_LIMIT, MEMORY_LIMIT))
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
exec(compile(code_source, code_file, 'exec'), {})
```

In this snippet, we set CPU, memory, and file size limits using `resource.setrlimit()` ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=import%20resource)) ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=resource)). Then we configure seccomp: the filter created will deny all syscalls by default (returning EPERM) except the ones we explicitly ALLOW – here we allow `write` calls to stdout and stderr file descriptors ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=filter%20%3D%20seccomp)) and the exit calls. We load the filter into the kernel, after which the process is severely restricted. Finally, we open the user’s code file and `exec()` it. The `exec(compile(...), {})` executes the code in an empty global namespace (we pass an empty dict for globals), which means the code doesn’t have access to our runner’s variables. We could also supply a restricted `__builtins__` if we wanted to remove some dangerous builtins (but note that purely removing builtins in Python is not sufficient for security on its own – there are ways around it ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=I%20have%20side,to%20parts%20of%20the%20runtime)) ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=But%20program%20languages%20,tree%20and%20dancing%20across%20frames)), which is why we rely on OS-level sandboxing as the real defense). The combination of no import capability (since open() is blocked by seccomp, any attempt to import a new module that isn’t already loaded will fail because Python’s import ultimately calls open() on files) and no system calls means the code is in a pretty tight cage.

**FastAPI Integration:** The FastAPI app will invoke this runner. We showed a basic example earlier with `subprocess.run(["python3", "sandbox_runner.py", code_file])`. In a more refined implementation, you might want to use `subprocess.Popen` for more control. For instance, to capture output and handle timeouts:

```python
proc = subprocess.Popen(
    [sys.executable, "sandbox_runner.py", code_file],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env={},  # provide a clean environment to the child
)
try:
    stdout, stderr = proc.communicate(timeout=5)  # wait for up to 5 seconds
except subprocess.TimeoutExpired:
    proc.kill()
    stdout, stderr = proc.communicate()  # get whatever output was produced before termination
```

Here we set `env={}` to ensure the sandbox process doesn’t inherit any environment variables from the server (for example, this avoids leaking AWS credentials or other secrets from host env). We then wait for up to 5 seconds. If the process runs longer, we kill it. The output captured in `stdout`/`stderr` can then be decoded and sent back. Using `communicate()` with a timeout is a straightforward way to enforce a wall-clock time limit from the outside ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=As%20well%20as%20system%20calls%2C,eating%20up%20a%20CPU%20core)) ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=try%3A)) – this complements the internal `RLIMIT_CPU` (which is CPU time, not wall time, and on a multi-core system a process could potentially use less CPU but still hang waiting on I/O; the wall timeout catches those cases).

If you use an external tool like **NsJail**, your FastAPI code instead would build the command for NsJail. For example:

```python
result = subprocess.run(
    ["nsjail", "-Mo", "--disable_clone_newcgroup",
     "--time_limit", "5", "--max_cpus", "1", 
     "--rlimit_as", str(100*1024*1024),
     "--rlimit_fsize", str(5*1024*1024),
     "--disable_network", 
     "--chroot", "/path/to/readonly/python_env", 
     "--", "/usr/bin/python3", code_file],
    capture_output=True, text=True
)
```

This rather long command tells NsJail to create a *mineral* (mini jail) with: 5s time limit, 1 CPU core, 100MB memory, 5MB file size, no network, chroot to a limited Python environment (you’d prepare a chroot with Python stdlib), then execute Python on the code file. The flags may vary; typically one would use a config file to keep this manageable. The concept, however, is that the FastAPI server doesn’t do seccomp itself – it asks NsJail to do it.

**Python Libraries:** In summary, the Python libraries and tools involved in this design include:

- **FastAPI** – for the web framework and request handling.
- **subprocess (std library)** – to spawn and manage sandbox processes.
- **asyncio (std library)** – if using async subprocess or managing concurrency in an async way.
- **resource (std library)** – to set POSIX resource limits (CPU, memory, etc.) ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=import%20resource)).
- **pyseccomp (third-party)** – to apply seccomp system call filters in Python ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=import%20pyseccomp%20as%20seccomp)).
- **tempfile (std library)** – to safely handle temporary files for code.
- **os and pathlib (std library)** – for file operations and cleanup.
- **NsJail or Firejail (external)** – not Python libraries, but external tools you can call from Python for sandboxing. NsJail doesn’t have an official Python API, but wrapping calls with subprocess is straightforward. Firejail similarly is used via subprocess call.
- **multiprocessing or ThreadPool (optional)** – not strictly needed, but if you wanted to manage a pool of pre-forked worker processes that stay alive to execute multiple code snippets (to avoid process startup cost each time), you could use Python’s multiprocessing. However, that approach is complex to isolate properly (you’d have to reset the process state after each run), so the simpler and safer route is one-process-per-request.

## Security Considerations and Best Practices

When running untrusted code, **security is paramount**. Here are additional considerations and potential limitations of the system:

- **Drop Permissions:** If possible, run the sandbox process under a **different Unix user account** that has no privileges. For example, create a user `sandboxuser` with no special permissions, and have the subprocess run as that user. This can be done by launching the FastAPI app as root and using `os.setuid()` in the child, or by using tools (NsJail can enter a new user namespace as an unprivileged user). The idea is that even if the code escapes the Python sandbox, it’s running as a low-privilege user who cannot modify system files. Combining this with seccomp (which blocks most syscalls) provides defense in depth.
- **No Shared State:** Ensure that each execution starts fresh. Don’t reuse the same process for different code without a thorough reset. The safest approach is to spawn a new process every time (as we have done). This prevents one run from leaving malicious hooks or altered state that a subsequent run (possibly from a different host) could exploit.
- **Limit Output Size:** As noted, untrusted code might try to dump massive output to overwhelm your API or just use up bandwidth. Implement a cap on how much output you’ll read and return. Snekbox, for instance, truncates output around 1 MB by default ([GitHub - python-discord/snekbox: Easy, safe evaluation of arbitrary Python code](https://github.com/python-discord/snekbox#:~:text=The%20code%20is%20executed%20in,for%20sandboxing%20the%20Python%20process)). You can enforce this by reading from the pipe in chunks or using `RLIMIT_FSIZE`. In our Python sandbox example, we set `RLIMIT_FSIZE` which should prevent the process from generating files (including the stdout buffer) larger than a certain size. Additionally, after the process ends, you can post-process the output: if `len(stdout) > MAX_RETURN_SIZE`, truncate it and perhaps indicate that it was truncated.
- **Network Security:** We already plan to disable network access for the code. This is important not only to prevent data exfiltration or illicit access, but also to stop the code from launching attacks (like DDoS or port scanning) from your server. By using network namespaces or simply not allowing any network-related syscalls (`socket`, `connect`, etc.) via seccomp, the code cannot use the network at all.
- **Filesystem Security:** Similar to network, ensure the code cannot write to the server’s filesystem except perhaps a designated temp area. If using our pure-Python approach, the seccomp filter by default will block `open()` syscalls, meaning the code can’t open or create files. If you do allow some filesystem access (maybe you allow reading a specific input file or writing to a temp directory), carefully constrain it (e.g., use AppArmor or an allow-list of file paths). Generally, it’s safest to allow no file access. The code can still perform computations and print results without needing to open files.
- **Timeouts and Infinite Loops:** A tricky scenario is an infinite loop or a computation that never yields (like `while True: pass`). The CPU time limit (`RLIMIT_CPU`) will ensure the process is killed after, say, 2 seconds of CPU time ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=As%20well%20as%20system%20calls%2C,eating%20up%20a%20CPU%20core)). Additionally, the wall-clock `timeout` in the parent ensures that even if the process is somehow sleeping or waiting (not consuming CPU), we don’t wait forever. The combination helps cover both CPU-bound and I/O-bound hangs.
- **Memory Exploits:** By limiting memory, you reduce the risk of certain exploits and also prevent the host from swapping or OOM if someone tries to consume huge memory. Keep the memory limit strict but high enough for typical code needs. For reference, simple scripts might run in a few MB, but things like `import numpy` or other libraries might need tens of MB. Adjust according to use-case.
- **Python Standard Library Access:** With the approach of blocking file opens, one side effect is that the user code cannot import modules beyond those already in memory. If you need to allow imports of some libraries, you might preload them in the runner before applying seccomp (for example, import `math`, `json`, etc., then apply seccomp, then exec user code – the user code would then be able to use those modules). By default, our sandbox will allow usage of Python built-ins and any modules that don’t require opening new files. (The Python interpreter opens files when importing new modules, but since we block file I/O, imports of modules not already loaded will fail with an ImportError.) This is actually another security layer: it prevents the code from loading arbitrary libraries or code from disk. Only a curated set of modules could be provided if needed.
- **Untrusted Code Execution Safety:** Despite all these measures, running arbitrary code is inherently risky. Sandboxes can have escape vulnerabilities, especially if misconfigured. It’s important to keep the sandboxing tools up to date and treat the whole execution environment as potentially compromised. Monitor the sandbox processes – if one exits unexpectedly or triggers a seccomp violation, log it. Ideally, the sandbox should be locked down so tightly that even if the code tries to break out, it simply gets killed or errors out. The philosophy, as noted in an LWN article, is to keep the sandboxing mechanism as small and simple as possible, and not attempt to filter Python at the language level (past attempts like `pysandbox` failed because the Python runtime is too complex to secure from within ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=As%20part%20of%20my%20Python,about%20The%20failure%20of%20pysandbox))). Our approach avoids relying on Python’s internal restrictions and instead trusts the operating system’s security features, which have a smaller and more auditable attack surface ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=As%20part%20of%20my%20Python,about%20The%20failure%20of%20pysandbox)) ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=Which%20prompted%20me%20to%20just,wrap%20it%20in%20seccomp)).
- **Deploying on AWS or Other Platforms:** The solution is mostly OS-dependent (Linux) but not cloud-specific. On AWS EC2 or Lightsail (or any VM/bare metal), you can install the required tools and run the FastAPI app normally. On AWS Lambda (if one attempted that), you might be more limited – Lambda wouldn’t allow running `nsjail` and such. But since the requirement is not to tie to AWS specifically, deploying on a Linux server or container is fine. If deploying in a container (e.g., a Kubernetes pod), ensure the container has the needed Linux capabilities (`SYS_ADMIN` if using nsjail, etc.). One interesting option AWS offers is Firecracker microVMs (used in Lambda) – one could spawn microVMs per request for maximal isolation ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=I%20would%20usually%20sandbox%20untrusted,microVM%20or%20a%20V8%20isolate)), but that indeed would be closer to “Docker per request” in overhead, which we want to avoid. So stick to lightweight containment.
- **Testing the Sandbox:** It’s crucial to test your sandbox with malicious inputs to ensure it holds up. Try things like code that opens files, spawns threads, uses a lot of memory, etc. A well-designed sandbox will respond by terminating those attempts (for example, trying to open a file should result in an `PermissionError` due to seccomp, trying to use too much memory will get killed by the OOM or rlimit, etc.). As an example, Andrew Healey deployed his sandbox publicly and invited people to break out, specifically because there are many creative ways people will try to bypass restrictions ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=I%20will%20update%20this%20post,a%20security%20hole%20in%20it)). Being proactive in hardening (and perhaps using proven configurations like those in snekbox) is recommended.

In conclusion, the system will consist of a FastAPI web service that delegates code execution to tightly controlled subprocesses. By using OS-level sandboxing features – **separate processes, resource limits, seccomp system call filters, and namespace isolation** – we ensure that each host’s Python code runs securely and efficiently. This design allows concurrent use by multiple hosts, gives clear separation between users, and avoids the heavy overhead of container-per-request by using lighter-weight Linux security primitives. All these measures together create a robust sandbox for executing untrusted Python code while minimizing the risk to the server and other clients.

**Sources:**

- Healey, A. *Running Untrusted Python Code* – Describes using a separate process with seccomp and rlimits to sandbox Python code ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=When%20the%20API%20receives%20some,step%2C%20the%20process%20isn%27t%20trusted)) ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=setrlimit)) ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=import%20resource)).  
- Python Discord Snekbox – An open-source service using NsJail for safe code execution. Notably disables networking and limits time, memory, and processes ([GitHub - python-discord/snekbox: Easy, safe evaluation of arbitrary Python code](https://github.com/python-discord/snekbox#:~:text=,home)).  
- FastAPI Documentation – Concurrency model explanation that sync def endpoints run in threadpool for parallelism ([python - FastAPI runs API calls in serial instead of parallel fashion - Stack Overflow](https://stackoverflow.com/questions/71516140/fastapi-runs-api-calls-in-serial-instead-of-parallel-fashion#:~:text=As%20per%20FastAPI%27s%20docs%3A)).  
- Firejail Project – Linux sandbox tool for isolating applications, enabling resource restrictions and network/file system limits ([Secure Your Applications with Firejail: A Linux Sandbox Tutorial - DEV Community](https://dev.to/vlythr/secure-your-applications-with-firejail-a-step-by-step-linux-sandbox-tutorial-4f9b#:~:text=Firejail%20is%20a%20powerful%20sandboxing,why%20you%20should%20use%20it)) ([Secure Your Applications with Firejail: A Linux Sandbox Tutorial - DEV Community](https://dev.to/vlythr/secure-your-applications-with-firejail-a-step-by-step-linux-sandbox-tutorial-4f9b#:~:text=2,of%20defense%20against%20potential%20threats)).  
- Linux man pages for seccomp and rlimit – background on seccomp filtering of syscalls ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=For%20my%20sandbox%2C%20the%20layer,to%20already%20open%20file%20descriptors)) and resource limit constants ([Running Untrusted Python Code — Andrew Healey](https://healeycodes.com/running-untrusted-python-code#:~:text=import%20resource)).