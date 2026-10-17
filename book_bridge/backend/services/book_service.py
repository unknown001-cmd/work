"""
============================================================
教材模块业务服务层
============================================================
功能：封装教材相关的业务逻辑，供路由层调用
    - create_book: 发布教材（出售/求购）
    - get_book_detail: 查询教材详情
    - list_books: 教材列表查询（支持分页、分类筛选、类型筛选）
    - search_books: 关键词搜索（搜索教材名称、ISBN、课程名称）
    - get_categories: 获取所有学科分类
============================================================
"""

from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException

from models.book import Book
from models.user import User
from schemas.book import BookCreate, BookResponse, BookListResponse


def create_book(db: Session, book_data: BookCreate) -> BookResponse:
    """
    发布教材（出售或求购）

    业务流程：
        1. 校验发布者用户是否存在
        2. 创建教材记录并写入数据库
        3. 返回新教材信息

    Args:
        db (Session): 数据库会话
        book_data (BookCreate): 教材发布数据

    Returns:
        BookResponse: 发布成功的教材信息

    Raises:
        HTTPException: 用户不存在时抛出 404 错误
    """
    # 校验用户是否存在
    user = db.query(User).filter(User.id == book_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="发布者用户不存在")

    # 创建教材记录
    new_book = Book(
        user_id=book_data.user_id,
        title=book_data.title,
        author=book_data.author,
        isbn=book_data.isbn,
        course_name=book_data.course_name,
        category=book_data.category,
        price=book_data.price,
        book_type=book_data.book_type,
        condition=book_data.condition,
        description=book_data.description,
        status="active",
    )
    db.add(new_book)
    db.commit()
    db.refresh(new_book)

    # 组装响应（附带用户名）
    resp = BookResponse.model_validate(new_book)
    resp.username = user.username
    return resp


def get_book_detail(db: Session, book_id: int) -> BookResponse:
    """
    查询教材详情

    Args:
        db (Session): 数据库会话
        book_id (int): 教材ID

    Returns:
        BookResponse: 教材详情信息

    Raises:
        HTTPException: 教材不存在时抛出 404 错误
    """
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="教材不存在")

    # 关联查询用户名
    user = db.query(User).filter(User.id == book.user_id).first()
    resp = BookResponse.model_validate(book)
    resp.username = user.username if user else None
    return resp


def list_books(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    category: str | None = None,
    book_type: str | None = None,
    status: str = "active",
) -> BookListResponse:
    """
    教材列表查询（支持分页、分类筛选、类型筛选）

    业务流程：
        1. 构建基础查询（按状态过滤）
        2. 根据分类、类型追加过滤条件
        3. 计算总数和分页偏移量
        4. 查询当前页数据并关联用户名

    Args:
        db (Session): 数据库会话
        page (int): 页码，从1开始
        page_size (int): 每页数量
        category (str|None): 学科分类筛选
        book_type (str|None): 类型筛选（sell/buy）
        status (str): 状态筛选，默认 active

    Returns:
        BookListResponse: 含分页信息的教材列表
    """
    query = db.query(Book).filter(Book.status == status)

    # 分类筛选
    if category:
        query = query.filter(Book.category == category)

    # 类型筛选
    if book_type:
        query = query.filter(Book.book_type == book_type)

    # 计算总数
    total = query.count()

    # 分页查询
    offset = (page - 1) * page_size
    books = query.order_by(Book.created_at.desc()).offset(offset).limit(page_size).all()

    # 组装响应列表，关联用户名
    items = []
    for book in books:
        user = db.query(User).filter(User.id == book.user_id).first()
        resp = BookResponse.model_validate(book)
        resp.username = user.username if user else None
        items.append(resp)

    return BookListResponse(total=total, page=page, page_size=page_size, items=items)


def search_books(
    db: Session,
    keyword: str,
    page: int = 1,
    page_size: int = 10,
    book_type: str | None = None,
) -> BookListResponse:
    """
    关键词智能搜索教材

    搜索范围：教材名称、ISBN、课程名称、作者（模糊匹配）
    支持按类型进一步筛选

    Args:
        db (Session): 数据库会话
        keyword (str): 搜索关键词
        page (int): 页码
        page_size (int): 每页数量
        book_type (str|None): 类型筛选

    Returns:
        BookListResponse: 搜索结果列表
    """
    # 构建模糊搜索条件：在教材名称、ISBN、课程名称、作者中匹配
    search_pattern = f"%{keyword}%"
    query = db.query(Book).filter(
        or_(
            Book.title.ilike(search_pattern),
            Book.isbn.ilike(search_pattern),
            Book.course_name.ilike(search_pattern),
            Book.author.ilike(search_pattern),
        ),
        Book.status == "active",
    )

    # 类型筛选
    if book_type:
        query = query.filter(Book.book_type == book_type)

    total = query.count()
    offset = (page - 1) * page_size
    books = query.order_by(Book.created_at.desc()).offset(offset).limit(page_size).all()

    items = []
    for book in books:
        user = db.query(User).filter(User.id == book.user_id).first()
        resp = BookResponse.model_validate(book)
        resp.username = user.username if user else None
        items.append(resp)

    return BookListResponse(total=total, page=page, page_size=page_size, items=items)


def get_categories(db: Session) -> list[dict]:
    """
    获取所有学科分类及各分类下的教材数量

    用于前端「按学科浏览教材」模块展示

    Args:
        db (Session): 数据库会话

    Returns:
        list[dict]: 分类列表，每项包含 category（分类名）和 count（数量）
    """
    from sqlalchemy import func

    results = (
        db.query(Book.category, func.count(Book.id))
        .filter(Book.status == "active", Book.category.isnot(None))
        .group_by(Book.category)
        .all()
    )

    return [{"category": cat, "count": cnt} for cat, cnt in results]