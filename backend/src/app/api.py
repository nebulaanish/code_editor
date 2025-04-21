import os
import uuid
import tempfile
import subprocess
from fastapi import APIRouter
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from src.settings import logger
from src.app.schema import CodeRequest, CodeResponse
from src.services.user_group import UNPRIVILEGED_GROUP, UNPRIVILEGED_USER

router = APIRouter()


@router.post("/execute", response_model=CodeResponse)
async def execute_code(request: CodeRequest):
    logger.info("Received code execution request")

    # Create unique ID for this execution
    execution_id = str(uuid.uuid4())

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, f"{execution_id}.py")
            with open(file_path, "w") as f:
                f.write(request.code)

            nsjail_cmd = [
                "nsjail",
                "--quiet",
                "--mode",
                "o",  # Once-only mode
                "--time_limit",
                str(request.timeout),
                "--rlimit_cpu",
                str(request.timeout),
                "--rlimit_as",
                "100",  # space limit in MB
                "--chroot",
                "/",
                "--cwd",
                temp_dir,
                "--user",
                UNPRIVILEGED_USER,
                "--group",
                UNPRIVILEGED_GROUP,
                "--disable_proc",
                "--iface_no_lo",
                "--",
                "/usr/bin/python3",
                file_path,
            ]

            # Execute the code using nsjail
            logger.info(f"Executing code with ID: {execution_id}")
            logger.debug(f"nsjail command: {' '.join(nsjail_cmd)}")

            process = subprocess.Popen(
                nsjail_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            try:
                stdout, stderr = process.communicate(timeout=request.timeout + 1)
                exit_code = process.returncode

                logger.info(f"Code execution completed with exit code: {exit_code}")
                if stderr:
                    logger.debug(f"stderr: {stderr}")

            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = "", "Execution timed out"
                exit_code = -1
                logger.warning("Code execution timed out")

            return CodeResponse(output=stdout, error=stderr, exit_code=exit_code)

    except Exception as e:
        logger.error(f"Error executing code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/test")
async def test_endpoint():
    """Simple test endpoint that executes a hello world program"""
    test_code = 'print("Hello, World!")'
    try:
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as temp:
            temp_path = temp.name
            temp.write(test_code.encode())

        # Execute Python directly without nsjail first to check Python works
        process = subprocess.run(
            ["/usr/bin/python3", temp_path], capture_output=True, text=True, timeout=5
        )

        python_stdout = process.stdout
        python_stderr = process.stderr
        python_exit = process.returncode

        nsjail_cmd = [
            "nsjail",
            "--quiet",
            "--mode",
            "o",
            "--time_limit",
            "5",
            "--chroot",
            "/",
            "--cwd",
            os.path.dirname(temp_path),
            "--user",
            UNPRIVILEGED_USER,
            "--group",
            UNPRIVILEGED_GROUP,
            "--",
            "/usr/bin/python3",
            temp_path,
        ]

        process = subprocess.run(nsjail_cmd, capture_output=True, text=True, timeout=6)

        os.unlink(temp_path)

        return {
            "python_direct": {
                "stdout": python_stdout,
                "stderr": python_stderr,
                "exit_code": python_exit,
            },
            "nsjail": {
                "stdout": process.stdout,
                "stderr": process.stderr,
                "exit_code": process.returncode,
            },
            "config": {"user": UNPRIVILEGED_USER, "group": UNPRIVILEGED_GROUP},
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/health")
async def health_check():
    """Health check endpoint to verify the service is running"""
    return {"status": "healthy"}
