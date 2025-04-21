from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base

from src.db.connection import Base


class BaseModel(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class CodeExecutionJob(BaseModel):
    __tablename__ = "code_execution_jobs"
    code = Column(String, nullable=False)
    is_success = Column(Boolean, nullable=True)
    stdout = Column(String, nullable=True)
    stderr = Column(String, nullable=True)
