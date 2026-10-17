"""
数据模型包初始化文件
导入所有模型，确保 SQLAlchemy 能正确创建所有数据表
"""
from .user import User
from .book import Book
from .match import MatchRecord

__all__ = ["User", "Book", "MatchRecord"]