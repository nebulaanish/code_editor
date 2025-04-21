from fastapi import HTTPException
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_500_INTERNAL_SERVER_ERROR,
)


class CustomException(HTTPException):
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


class BadRequestException(CustomException):
    def __init__(self, detail: str):
        super().__init__(status_code=HTTP_400_BAD_REQUEST, detail=detail)


class UnauthorizedException(CustomException):
    def __init__(self, detail: str):
        super().__init__(status_code=HTTP_401_UNAUTHORIZED, detail=detail)


class ForbiddenException(CustomException):
    def __init__(self, detail: str):
        super().__init__(status_code=HTTP_403_FORBIDDEN, detail=detail)


class NotFoundException(CustomException):
    def __init__(self, detail: str):
        super().__init__(status_code=HTTP_404_NOT_FOUND, detail=detail)


class UnprocessableEntity(CustomException):
    def __init__(self, detail: str):
        super().__init__(status_code=HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


class InternalServerError(CustomException):
    def __init__(self, detail: str):
        super().__init__(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


class DuplicateValueException(UnprocessableEntity):
    def __init__(self, detail: str = "Duplicate value detected"):
        super().__init__(detail=detail)


class DatabaseErrorException(InternalServerError):
    def __init__(self, detail: str = "Database error occurred"):
        super().__init__(detail=detail)


class PayloadNotFoundException(CustomException):
    def __init__(self, detail: str = "Payload not found"):
        super().__init__(status_code=HTTP_400_BAD_REQUEST, detail=detail)
