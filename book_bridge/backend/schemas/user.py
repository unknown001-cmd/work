"""
============================================================
用户模块 Pydantic 数据校验模型
============================================================
功能：定义用户相关接口的请求体和响应体数据结构
    - UserCreate: 注册请求体
    - UserLogin: 登录请求体
    - UserResponse: 用户信息响应体
    - CreditResponse: 信用分查询响应体
============================================================
"""

from datetime import datetime
from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    """
    用户注册请求体

    属性:
        username (str): 用户名，3-50字符
        password (str): 密码，6-50字符
        phone (str): 手机号，可选
        email (str): 邮箱，可选
    """
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=50, description="密码")
    phone: str | None = Field(None, max_length=20, description="手机号")
    email: str | None = Field(None, max_length=100, description="邮箱")


class UserLogin(BaseModel):
    """
    用户登录请求体

    属性:
        username (str): 用户名
        password (str): 密码
    """
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class UserResponse(BaseModel):
    """
    用户信息响应体

    属性:
        id (int): 用户ID
        username (str): 用户名
        phone (str): 手机号
        email (str): 邮箱
        credit_score (float): 信用分
        avatar (str): 头像URL
        created_at (datetime): 注册时间
    """
    id: int
    username: str
    phone: str | None = None
    email: str | None = None
    credit_score: float
    avatar: str | None = None
    created_at: datetime

    # 允许从 ORM 对象自动转换（从 SQLAlchemy 模型实例读取属性）
    model_config = {"from_attributes": True}


class CreditResponse(BaseModel):
    """
    信用分查询响应体

    属性:
        user_id (int): 用户ID
        username (str): 用户名
        credit_score (float): 信用分（0-100）
        level (str): 信用等级描述
    """
    user_id: int
    username: str
    credit_score: float
    level: str