"""
============================================================
用户模块 API 路由层
============================================================
功能：定义用户相关的 RESTful 接口
    - POST /api/users/register  用户注册
    - POST /api/users/login     用户登录
    - GET  /api/users/{user_id} 查询用户信息
    - GET  /api/users/{user_id}/credit 查询信用分

所有接口返回统一格式：{"code": 200, "message": "...", "data": {...}}
============================================================
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas.user import UserCreate, UserLogin
from services import user_service

# 创建路由器，前缀 /api/users
router = APIRouter(prefix="/api/users", tags=["用户模块"])


def ok(data, message: str = "success"):
    """
    统一成功响应格式封装

    Args:
        data: 响应数据
        message (str): 提示消息

    Returns:
        dict: {"code": 200, "message": ..., "data": ...}
    """
    return {"code": 200, "message": message, "data": data}


@router.post("/register")
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    用户注册接口

    请求体: UserCreate（username, password, phone, email）
    响应: 注册成功的用户信息
    """
    result = user_service.register_user(db, user_data)
    return ok(result.model_dump(mode="json"), "注册成功")


@router.post("/login")
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """
    用户登录接口

    请求体: UserLogin（username, password）
    响应: 登录成功信息（含 user_id, username, credit_score）
    """
    result = user_service.login_user(db, login_data)
    return ok(result, "登录成功")


@router.get("/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    """
    查询用户信息接口

    路径参数: user_id
    响应: 用户详细信息
    """
    result = user_service.get_user_info(db, user_id)
    return ok(result.model_dump(mode="json"), "查询成功")


@router.get("/{user_id}/credit")
def get_credit(user_id: int, db: Session = Depends(get_db)):
    """
    查询用户信用分接口

    路径参数: user_id
    响应: 信用分及信用等级
    """
    result = user_service.get_credit_info(db, user_id)
    return ok(result.model_dump(mode="json"), "查询成功")