"""
============================================================
用户模块业务服务层
============================================================
功能：封装用户相关的业务逻辑，供路由层调用
    - register_user: 用户注册（密码哈希存储）
    - login_user: 用户登录验证
    - get_user_info: 查询用户详细信息
    - get_credit_info: 查询用户信用分及等级
============================================================
"""

from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException

from models.user import User
from schemas.user import UserCreate, UserLogin, UserResponse, CreditResponse


# ============================================================
# 密码哈希工具函数
# ============================================================
def _hash_password(password: str) -> str:
    """
    对明文密码进行哈希加密

    采用简单的盐值+哈希方案（生产环境建议使用 passlib bcrypt）：
        hash = sha256(盐 + 密码)

    Args:
        password (str): 明文密码

    Returns:
        str: 哈希后的密码字符串
    """
    import hashlib
    salt = "book_bridge_2024_salt"
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def _verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    校验明文密码与哈希密码是否匹配

    Args:
        plain_password (str): 用户输入的明文密码
        hashed_password (str): 数据库存储的哈希密码

    Returns:
        bool: 匹配返回 True，否则返回 False
    """
    return _hash_password(plain_password) == hashed_password


# ============================================================
# 信用等级计算
# ============================================================
def _get_credit_level(score: float) -> str:
    """
    根据信用分返回信用等级描述

    评分标准：
        - 90-100: 极优信用
        - 80-89:  良好信用
        - 70-79:  一般信用
        - 60-69:  较低信用
        - 0-59:   风险用户

    Args:
        score (float): 信用分（0-100）

    Returns:
        str: 信用等级描述文本
    """
    if score >= 90:
        return "极优信用"
    elif score >= 80:
        return "良好信用"
    elif score >= 70:
        return "一般信用"
    elif score >= 60:
        return "较低信用"
    else:
        return "风险用户"


# ============================================================
# 业务服务函数
# ============================================================
def register_user(db: Session, user_data: UserCreate) -> UserResponse:
    """
    用户注册

    业务流程：
        1. 检查用户名是否已存在
        2. 对密码进行哈希加密
        3. 创建用户记录并写入数据库
        4. 返回新用户信息

    Args:
        db (Session): 数据库会话
        user_data (UserCreate): 注册请求数据

    Returns:
        UserResponse: 注册成功的用户信息

    Raises:
        HTTPException: 用户名已存在时抛出 400 错误
    """
    # 检查用户名是否已存在
    existing = db.query(User).filter(User.username == user_data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在，请更换用户名")

    # 创建用户对象，密码哈希存储
    new_user = User(
        username=user_data.username,
        password_hash=_hash_password(user_data.password),
        phone=user_data.phone,
        email=user_data.email,
        credit_score=80.00,  # 新用户默认信用分80
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return UserResponse.model_validate(new_user)


def login_user(db: Session, login_data: UserLogin) -> dict:
    """
    用户登录

    业务流程：
        1. 根据用户名查询用户
        2. 校验密码哈希
        3. 返回登录成功信息（含用户ID和信用分）

    Args:
        db (Session): 数据库会话
        login_data (UserLogin): 登录请求数据

    Returns:
        dict: 包含 token、user_id、username、credit_score 的字典

    Raises:
        HTTPException: 用户名或密码错误时抛出 401 错误
    """
    user = db.query(User).filter(User.username == login_data.username).first()
    if not user or not _verify_password(login_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    return {
        "message": "登录成功",
        "user_id": user.id,
        "username": user.username,
        "credit_score": float(user.credit_score),
    }


def get_user_info(db: Session, user_id: int) -> UserResponse:
    """
    查询用户详细信息

    Args:
        db (Session): 数据库会话
        user_id (int): 用户ID

    Returns:
        UserResponse: 用户信息

    Raises:
        HTTPException: 用户不存在时抛出 404 错误
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserResponse.model_validate(user)


def get_credit_info(db: Session, user_id: int) -> CreditResponse:
    """
    查询用户信用分及信用等级

    Args:
        db (Session): 数据库会话
        user_id (int): 用户ID

    Returns:
        CreditResponse: 信用分及等级信息

    Raises:
        HTTPException: 用户不存在时抛出 404 错误
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    return CreditResponse(
        user_id=user.id,
        username=user.username,
        credit_score=float(user.credit_score),
        level=_get_credit_level(float(user.credit_score)),
    )