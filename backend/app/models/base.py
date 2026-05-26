"""
Base Model Module.

This module provides the base SQLAlchemy model with common fields
and functionality used across all database models.

Example Usage:
    from app.models.base import BaseModel, TimestampMixin
    
    class MyModel(BaseModel, TimestampMixin):
        __tablename__ = "my_models"
        
        name = Column(String(100), nullable=False)
"""

from datetime import datetime
from typing import Any, Dict
import uuid

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declared_attr

from app.utils.database import Base


class TimestampMixin:
    """
    Mixin that adds created_at and updated_at columns.
    
    Automatically tracks when records are created and modified.
    
    Attributes:
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class BaseModel(Base):
    """
    Abstract base model with common functionality.
    
    Provides a UUID primary key and common methods for all models.
    
    Attributes:
        id: UUID primary key
        
    Example:
        >>> class User(BaseModel, TimestampMixin):
        ...     __tablename__ = "users"
        ...     email = Column(String(255), unique=True)
    """
    
    __abstract__ = True
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.
        
        Returns:
            Dict containing all column values
            
        Example:
            >>> user = User(email="test@example.com")
            >>> user_dict = user.to_dict()
            >>> print(user_dict["email"])
            'test@example.com'
        """
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def update(self, **kwargs: Any) -> None:
        """
        Update model attributes from keyword arguments.
        
        Args:
            **kwargs: Attributes to update
            
        Example:
            >>> user.update(email="new@example.com", name="New Name")
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def __repr__(self) -> str:
        """String representation of the model."""
        class_name = self.__class__.__name__
        return f"<{class_name}(id={self.id})>"