"""
============================================================
用户数据模型（User Model）
============================================================
对应数据库表：users
功能：存储平台注册用户的基本信息与信用评分

字段说明：
    - id: 主键，自增
    - username: 用户名（唯一）
    - password_hash: 密码哈希值（不存储明文）
    - phone: 手机号
    - email: 邮箱
    - credit_score: 信用分（0-100），影响撮合匹配度加权
    - avatar: 头像URL
    - created_at / updated_at: 创建/更新时间
============================================================
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Numeric
from database import Base


class User(Base):
    """
    用户模型类，映射到 users 表

    属性:
        id (int): 用户唯一标识，主键自增
        username (str): 用户名，唯一索引，最长50字符
        password_hash (str): 密码哈希值，最长255字符
        phone (str): 手机号，最长20字符
        email (str): 邮箱地址，最长100字符
        credit_score (float): 信用分，范围0-100，默认80分
        avatar (str): 头像图片URL，最长255字符
        created_at (datetime): 注册时间，默认当前时间
        updated_at (datetime): 信息更新时间，每次修改自动更新
    """

    __tablename__ = "users"

    # 主键ID，自增
    id = Column(Integer, primary_key=True, index=True, comment="用户唯一标识")

    # 用户名：唯一索引，用于登录
    username = Column(String(50), unique=True, index=True, nullable=False, comment="用户名")

    # 密码哈希：存储加密后的密码，不存储明文
    password_hash = Column(String(255), nullable=False, comment="密码哈希值")

    # 手机号
    phone = Column(String(20), nullable=True, comment="手机号")

    # 邮箱
    email = Column(String(100), nullable=True, comment="邮箱地址")

    # 信用分：0-100，用于撮合算法加权计算，新用户默认80分
    credit_score = Column(Numeric(5, 2), default=80.00, nullable=False, comment="信用评分(0-100)")

    # 头像URL
    avatar = Column(String(255), nullable=True, comment="头像URL")

    # 创建时间：用户注册时间
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="注册时间")

    # 更新时间：用户信息最后修改时间，每次更新自动刷新
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间")

    def __repr__(self):
        """对象的字符串表示，便于调试"""
        return f"<User(id={self.id}, username='{self.username}', credit_score={self.credit_score})>"