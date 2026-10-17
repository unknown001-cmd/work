"""
============================================================
教材模块 API 路由层
============================================================
功能：定义教材相关的 RESTful 接口
    - POST /api/books          发布教材（出售/求购）
    - GET  /api/books          教材列表查询（分页、分类、类型筛选）
    - GET  /api/books/search   关键词搜索教材
    - GET  /api/books/{book_id} 教材详情
    - GET  /api/books/categories/all 学科分类列表

所有接口返回统一格式：{"code": 200, "message": "...", "data": {...}}
============================================================
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from schemas.book import BookCreate
from services import book_service

# 创建路由器，前缀 /api/books
router = APIRouter(prefix="/api/books", tags=["教材模块"])


def ok(data, message: str = "success"):
    """统一成功响应格式封装"""
    return {"code": 200, "message": message, "data": data}


@router.post("")
def create_book(book_data: BookCreate, db: Session = Depends(get_db)):
    """
    发布教材接口

    请求体: BookCreate（含教材名称、课程、价格、类型等）
    响应: 发布成功的教材信息
    """
    result = book_service.create_book(db, book_data)
    return ok(result.model_dump(mode="json"), "发布成功")


@router.get("")
def list_books(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=50, description="每页数量"),
    category: str | None = Query(None, description="学科分类筛选"),
    book_type: str | None = Query(None, pattern="^(sell|buy)$", description="类型筛选"),
    db: Session = Depends(get_db),
):
    """
    教材列表查询接口

    查询参数: page, page_size, category, book_type
    响应: 含分页信息的教材列表
    """
    result = book_service.list_books(db, page, page_size, category, book_type)
    return ok(result.model_dump(mode="json"), "查询成功")


@router.get("/search")
def search_books(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=50, description="每页数量"),
    book_type: str | None = Query(None, pattern="^(sell|buy)$", description="类型筛选"),
    db: Session = Depends(get_db),
):
    """
    关键词搜索教材接口

    搜索范围: 教材名称、ISBN、课程名称、作者
    查询参数: keyword, page, page_size, book_type
    响应: 搜索结果列表
    """
    result = book_service.search_books(db, keyword, page, page_size, book_type)
    return ok(result.model_dump(mode="json"), "搜索成功")


@router.get("/categories/all")
def get_categories(db: Session = Depends(get_db)):
    """
    获取所有学科分类接口

    响应: 分类列表，每项含分类名和教材数量
    """
    result = book_service.get_categories(db)
    return ok(result, "查询成功")


@router.get("/{book_id}")
def get_book_detail(book_id: int, db: Session = Depends(get_db)):
    """
    教材详情查询接口

    路径参数: book_id
    响应: 教材详细信息
    """
    result = book_service.get_book_detail(db, book_id)
    return ok(result.model_dump(mode="json"), "查询成功")