"""
============================================================
数据库连接与会话管理模块
============================================================
功能说明：
    1. 创建 SQLAlchemy 数据库引擎（默认 SQLite，预留 MySQL 切换入口）
    2. 提供数据库会话工厂 SessionLocal
    3. 定义所有 ORM 模型的基类 Base
    4. 提供 FastAPI 依赖注入函数 get_db，用于在每个请求中获取数据库会话

切换 MySQL 方式：
    将 DATABASE_URL 改为 "mysql+pymysql://用户名:密码@主机:端口/数据库名"
    并在 requirements.txt 中添加 pymysql 依赖即可
============================================================
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ============================================================
# 数据库连接配置
# ============================================================
# 默认使用 SQLite，数据库文件为 book_bridge.db，零配置开箱即用
# 支持通过环境变量 DATABASE_URL 配置（Docker 部署用）
# 如需切换 MySQL，设置 DATABASE_URL 或取消下方注释：
# DATABASE_URL = "mysql+pymysql://root:password@localhost:3306/book_bridge"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./book_bridge.db")

# 创建数据库引擎
# connect_args 仅对 SQLite 生效，允许多线程访问
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,  # 设为 True 可在控制台打印 SQL 语句，便于调试
)

# 创建会话工厂：每个请求创建独立的数据库会话
# autocommit=False 表示需要手动提交事务
# autoflush=False 表示需要手动刷新会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 声明性基类：所有 ORM 模型都继承自 Base
Base = declarative_base()


def get_db():
    """
    FastAPI 依赖注入函数：获取数据库会话

    工作原理：
        - 在每个 API 请求开始时创建一个数据库会话
        - 请求处理完成后自动关闭会话，释放数据库连接
        - 使用 yield 语法确保会话在任何情况下都会被正确关闭

    使用方式（在路由函数参数中）：
        def some_endpoint(db: Session = Depends(get_db)):
            ...

    Yields:
        Session: SQLAlchemy 数据库会话对象
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()