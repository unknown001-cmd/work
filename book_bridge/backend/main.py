"""
============================================================
书桥 BOOKBRIDGE 后端项目入口
============================================================
功能：
    1. 创建 FastAPI 应用实例
    2. 配置 CORS 跨域支持（前后端分离开发）
    3. 挂载前端静态文件目录（前后端整合部署）
    4. 注册所有 API 路由
    5. 启动时自动初始化模拟数据（零配置开箱即用）

启动方式：
    前后端分离开发：uvicorn main:app --reload --port 8000
    整合部署：       uvicorn main:app --port 8000（前端通过 / 访问）

访问地址：
    前端页面：    http://localhost:8000/
    接口文档：    http://localhost:8000/docs
    API 根路径：  http://localhost:8000/api/
============================================================
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database import engine, Base, SessionLocal
from models import User, Book, MatchRecord
from routers import user, book, match, agent
from services import match_service

# ============================================================
# 创建 FastAPI 应用实例
# ============================================================
app = FastAPI(
    title="书桥 BOOKBRIDGE API",
    description="校园二手教材智能撮合平台后端接口文档",
    version="3.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ============================================================
# CORS 跨域配置
# ============================================================
# 允许前端开发服务器跨域访问，支持前后端分离开发模式
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 允许所有来源（生产环境应限制具体域名）
    allow_credentials=True,       # 允许携带 Cookie
    allow_methods=["*"],          # 允许所有 HTTP 方法
    allow_headers=["*"],          # 允许所有请求头
)


# ============================================================
# 模拟数据初始化
# ============================================================
def init_mock_data():
    """
    初始化模拟数据，确保项目启动即可看到完整页面效果

    数据内容：
        - 5个模拟用户（不同信用分）
        - 6本出售教材 + 4本求购教材（覆盖数学、计算机、经济学、物理等学科）
        - 自动执行撮合算法生成撮合记录

    安全机制：仅在数据库为空时初始化，避免重复插入
    """
    db = SessionLocal()
    try:
        # 检查是否已有数据，避免重复初始化
        if db.query(User).count() > 0:
            return

        # ---- 创建模拟用户 ----
        users_data = [
            ("张明轩", "95", "13800138001", "zhang@example.com", 95.00),
            ("李思琪", "95", "13800138002", "li@example.com", 88.00),
            ("王浩然", "95", "13800138003", "wang@example.com", 76.00),
            ("赵雨桐", "95", "13800138004", "zhao@example.com", 92.00),
            ("陈嘉怡", "95", "13800138005", "chen@example.com", 85.00),
        ]
        users = []
        for username, pwd, phone, email, credit in users_data:
            import hashlib
            password_hash = hashlib.sha256(("book_bridge_2024_salt" + pwd).encode()).hexdigest()
            u = User(username=username, password_hash=password_hash, phone=phone, email=email, credit_score=credit)
            db.add(u)
            users.append(u)
        db.commit()
        for u in users:
            db.refresh(u)

        # ---- 创建出售教材 ----
        sell_books_data = [
            # (user_idx, title, author, isbn, course, category, price, condition)
            (0, "高等数学（第七版）", "同济大学数学系", "9787040396631", "高等数学", "数学", 35.00, "九成新"),
            (1, "数据结构（C语言版）", "严蔚敏", "9787302023645", "数据结构", "计算机", 28.00, "八成新"),
            (3, "线性代数（第六版）", "同济大学数学系", "9787040507541", "线性代数", "数学", 20.00, "全新"),
            (4, "微观经济学", "高鸿业", "9787300252857", "微观经济学", "经济学", 30.00, "九成新"),
            (0, "大学物理（第三版）", "程守洙", "9787040265688", "大学物理", "物理", 25.00, "八成新"),
            (1, "离散数学", "屈婉玲", "9787040270223", "离散数学", "计算机", 22.00, "七成新"),
        ]
        for idx, title, author, isbn, course, cat, price, cond in sell_books_data:
            b = Book(
                user_id=users[idx].id, title=title, author=author, isbn=isbn,
                course_name=course, category=cat, price=price,
                book_type="sell", condition=cond,
                description=f"{title}，{cond}，有少量笔记，内容完整无缺页。",
            )
            db.add(b)

        # ---- 创建求购教材 ----
        buy_books_data = [
            # (user_idx, title, author, isbn, course, category, budget, condition)
            (2, "高等数学（第七版）", "同济大学数学系", "9787040396631", "高等数学", "数学", 40.00, "不限"),
            (3, "数据结构（C语言版）", "严蔚敏", "9787302023645", "数据结构", "计算机", 30.00, "八成新以上"),
            (4, "线性代数（第六版）", "同济大学数学系", "9787040507541", "线性代数", "数学", 25.00, "不限"),
            (2, "大学物理（第三版）", "程守洙", "9787040265688", "大学物理", "物理", 20.00, "不限"),
        ]
        for idx, title, author, isbn, course, cat, budget, cond in buy_books_data:
            b = Book(
                user_id=users[idx].id, title=title, author=author, isbn=isbn,
                course_name=course, category=cat, price=budget,
                book_type="buy", condition=cond,
                description=f"急需{title}，预算{budget}元以内，{cond}。",
            )
            db.add(b)

        db.commit()

        # ---- 执行撮合算法，生成撮合记录 ----
        match_service.run_matching(db, min_score=0.3)

        # 将部分撮合记录标记为已成交，用于统计撮合成功率
        records = db.query(MatchRecord).order_by(MatchRecord.match_score.desc()).all()
        for record in records[:3]:
            record.status = "completed"
        db.commit()

        print("✅ 模拟数据初始化完成：5个用户、10本教材、撮合记录已生成")
    finally:
        db.close()


# ============================================================
# 应用启动事件：创建数据表 + 初始化模拟数据
# ============================================================
@app.on_event("startup")
def on_startup():
    """
    应用启动时执行：
        1. 创建所有数据库表（如不存在）
        2. 初始化模拟数据
    """
    Base.metadata.create_all(bind=engine)
    init_mock_data()


# ============================================================
# 注册 API 路由
# ============================================================
app.include_router(user.router)
app.include_router(book.router)
app.include_router(match.router)
app.include_router(agent.router)


# ============================================================
# 根路径健康检查
# ============================================================
@app.get("/api/health")
def health_check():
    """健康检查接口，用于确认后端服务是否正常运行"""
    return {"code": 200, "message": "success", "data": {"status": "running", "service": "BOOKBRIDGE API v3.2"}}


# ============================================================
# 挂载前端静态文件（支持整合部署模式）
# ============================================================
# 前端文件位于 backend 同级的 frontend 目录
# 使用绝对路径计算前端目录，确保从任何位置启动都能正确找到
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.join(os.path.dirname(BASE_DIR), "frontend")

if os.path.exists(frontend_dir):
    # 挂载前端静态资源目录（如 css/js/images 子目录）
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    def serve_index():
        """
        根路径返回前端 index.html，实现前后端整合部署
        访问 http://localhost:8000/ 即可看到完整前端页面
        """
        return FileResponse(os.path.join(frontend_dir, "index.html"))


# ============================================================
# 应用入口
# ============================================================
if __name__ == "__main__":
    import uvicorn
    # 启动服务，监听 0.0.0.0:8000
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)