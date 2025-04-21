from pydantic import BaseModel


class CodeRequest(BaseModel):
    code: str
    timeout: int = 5  # Default timeout in seconds


class CodeResponse(BaseModel):
    output: str
    error: str
    exit_code: int
