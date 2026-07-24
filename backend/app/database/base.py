"""Base declarativa común para los modelos de persistencia."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Metadatos compartidos sin crear conexiones ni tablas al importarse."""
