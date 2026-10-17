"""
============================================================
撮合模块业务服务层（核心算法）
============================================================
功能：实现智能撮合算法，封装撮合相关业务逻辑
    - calculate_course_similarity: 课程名称相似度计算
    - calculate_price_match: 价格区间匹配度计算
    - calculate_credit_factor: 信用分加权因子计算
    - calculate_match: 综合撮合算法（核心）
    - run_matching: 执行全量撮合，生成撮合记录
    - get_match_records: 查询撮合记录列表
    - get_realtime_matches: 首页实时撮合数据
    - get_stats: 首页核心统计数据

撮合算法说明：
    匹配度 = 0.40 × 课程相似度 + 0.35 × 价格匹配度 + 0.25 × 信用因子

    1. 课程相似度（权重0.40）：使用编辑距离算法计算课程名称的字符串相似度
    2. 价格匹配度（权重0.35）：出售价 ≤ 求购预算时匹配度高，超出预算按比例衰减
    3. 信用因子（权重0.25）：双方信用分归一化，信用越高撮合越优先

    建议成交价：以信用分为权重对求购预算和出售标价做加权平均，
               信用分高的一方议价能力更强，成交价更偏向其出价。
============================================================
"""

import time
from difflib import SequenceMatcher
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.book import Book
from models.user import User
from models.match import MatchRecord
from schemas.match import (
    MatchResult,
    MatchRecordResponse,
    RealtimeMatchItem,
    RealtimeMatchResponse,
    StatsResponse,
)


# ============================================================
# 撮合算法子函数
# ============================================================
def calculate_course_similarity(course_name_1: str | None, course_name_2: str | None) -> float:
    """
    计算两个课程名称的相似度

    算法：使用 Python 标准库 difflib.SequenceMatcher 计算字符串编辑距离相似度
          结果范围 [0, 1]，1 表示完全相同

    特殊处理：
        - 若任一课程名为空，返回 0.0（无法匹配）
        - 统一转为小写后比较，消除大小写差异

    Args:
        course_name_1 (str|None): 课程名称1（求购方）
        course_name_2 (str|None): 课程名称2（出售方）

    Returns:
        float: 相似度，范围 [0.0, 1.0]
    """
    if not course_name_1 or not course_name_2:
        return 0.0
    # 转小写后计算序列匹配相似度
    return SequenceMatcher(None, course_name_1.lower().strip(), course_name_2.lower().strip()).ratio()


def calculate_price_match(buy_budget: float, sell_price: float) -> float:
    """
    计算求购预算与出售标价的价格匹配度

    算法逻辑：
        - 出售价 ≤ 预算：匹配度高，出售价越接近预算（买家觉得划算）匹配度越高
          公式：0.7 + 0.3 × (出售价 / 预算)，结果范围 [0.7, 1.0]
        - 出售价 > 预算：超出预算，按超出比例衰减
          公式：max(0, 0.7 - 超出比例 × 0.5)，超出越多匹配度越低

    Args:
        buy_budget (float): 求购方预算上限
        sell_price (float): 出售方标价

    Returns:
        float: 价格匹配度，范围 [0.0, 1.0]
    """
    if buy_budget <= 0:
        return 0.0

    if sell_price <= buy_budget:
        # 出售价在预算内：越接近预算匹配度越高（买家觉得物有所值）
        ratio = sell_price / buy_budget
        return 0.7 + 0.3 * ratio
    else:
        # 出售价超出预算：按超出比例衰减
        overflow_ratio = (sell_price - buy_budget) / buy_budget
        return max(0.0, 0.7 - overflow_ratio * 0.5)


def calculate_credit_factor(buy_credit: float, sell_credit: float) -> float:
    """
    计算双方信用分的加权因子

    算法：双方信用分之和除以 200（满分100+100），归一化到 [0, 1]
          信用分越高，撮合优先级越高

    Args:
        buy_credit (float): 求购方信用分（0-100）
        sell_credit (float): 出售方信用分（0-100）

    Returns:
        float: 信用因子，范围 [0.0, 1.0]
    """
    return (buy_credit + sell_credit) / 200.0


def calculate_match(buy_book: Book, sell_book: Book, buy_user: User, sell_user: User) -> MatchResult:
    """
    撮合算法核心函数：计算一对求购-出售教材的综合匹配度与建议成交价

    综合匹配度公式：
        match_score = 0.40 × 课程相似度 + 0.35 × 价格匹配度 + 0.25 × 信用因子

    建议成交价公式：
        以信用分为权重做加权平均，信用分高的一方议价能力更强
        buy_weight = 出售方信用 / 双方信用总和  （出售方信用高 → 成交价偏向求购预算，即低价）
        sell_weight = 求购方信用 / 双方信用总和  （求购方信用高 → 成交价偏向出售标价，即高价）
        suggested_price = 求购预算 × buy_weight + 出售标价 × sell_weight

    Args:
        buy_book (Book): 求购方教材记录
        sell_book (Book): 出售方教材记录
        buy_user (User): 求购方用户
        sell_user (User): 出售方用户

    Returns:
        MatchResult: 撮合结果，含匹配度、建议成交价、计算耗时
    """
    start_time = time.time()

    # 提取数值（SQLAlchemy Numeric 类型需转 float）
    buy_budget = float(buy_book.price)
    sell_price = float(sell_book.price)
    buy_credit = float(buy_user.credit_score)
    sell_credit = float(sell_user.credit_score)

    # ---- 步骤1：课程名称相似度（权重 0.40）----
    course_sim = calculate_course_similarity(buy_book.course_name, sell_book.course_name)

    # ---- 步骤2：价格区间匹配度（权重 0.35）----
    price_match = calculate_price_match(buy_budget, sell_price)

    # ---- 步骤3：信用分加权因子（权重 0.25）----
    credit_factor = calculate_credit_factor(buy_credit, sell_credit)

    # ---- 综合匹配度计算 ----
    match_score = 0.40 * course_sim + 0.35 * price_match + 0.25 * credit_factor

    # ---- 建议成交价计算（信用分加权平均）----
    total_credit = buy_credit + sell_credit
    if total_credit <= 0:
        # 信用分均为0的极端情况，取算术平均
        suggested_price = (buy_budget + sell_price) / 2.0
    else:
        # 信用分高的一方议价能力强，成交价偏向其出价
        # 出售方信用高 → buy_weight大 → 成交价偏向求购预算（对卖方有利，快速成交）
        # 求购方信用高 → sell_weight大 → 成交价偏向出售标价（对买方有利，体现诚意）
        buy_weight = sell_credit / total_credit
        sell_weight = buy_credit / total_credit
        suggested_price = buy_budget * buy_weight + sell_price * sell_weight

    # 保留两位小数
    suggested_price = round(suggested_price, 2)
    match_score = round(match_score, 4)

    # 计算耗时（毫秒）
    duration_ms = int((time.time() - start_time) * 1000)

    return MatchResult(
        buy_book_id=buy_book.id,
        sell_book_id=sell_book.id,
        match_score=match_score,
        suggested_price=suggested_price,
        duration_ms=duration_ms,
    )


# ============================================================
# 撮合执行与记录管理
# ============================================================
def run_matching(db: Session, min_score: float = 0.3) -> dict:
    """
    执行全量撮合：遍历所有有效的求购教材与出售教材，计算匹配度并保存撮合记录

    业务流程：
        1. 查询所有 status=active 的求购教材（book_type='buy'）
        2. 查询所有 status=active 的出售教材（book_type='sell'）
        3. 对每对（求购, 出售）计算匹配度
        4. 匹配度 >= min_score 的保存为撮合记录
        5. 返回撮合统计信息

    Args:
        db (Session): 数据库会话
        min_score (float): 最低匹配度阈值，低于此值不记录

    Returns:
        dict: 撮合执行结果统计，含 total_pairs（计算对数）、saved（保存记录数）
    """
    # 查询所有有效的求购和出售教材
    buy_books = db.query(Book).filter(Book.book_type == "buy", Book.status == "active").all()
    sell_books = db.query(Book).filter(Book.book_type == "sell", Book.status == "active").all()

    # 预加载所有相关用户，避免循环查询
    user_cache: dict[int, User] = {}
    all_user_ids = set(b.user_id for b in buy_books) | set(s.user_id for s in sell_books)
    for uid in all_user_ids:
        u = db.query(User).filter(User.id == uid).first()
        if u:
            user_cache[uid] = u

    saved_count = 0
    total_pairs = 0

    for buy_book in buy_books:
        buy_user = user_cache.get(buy_book.user_id)
        if not buy_user:
            continue

        for sell_book in sell_books:
            # 同一用户不与自己撮合
            if sell_book.user_id == buy_book.user_id:
                continue

            sell_user = user_cache.get(sell_book.user_id)
            if not sell_user:
                continue

            total_pairs += 1

            # 计算匹配度
            result = calculate_match(buy_book, sell_book, buy_user, sell_user)

            # 匹配度达到阈值才保存
            if result.match_score >= min_score:
                record = MatchRecord(
                    buy_book_id=result.buy_book_id,
                    sell_book_id=result.sell_book_id,
                    match_score=result.match_score,
                    suggested_price=result.suggested_price,
                    status="pending",
                    duration_ms=result.duration_ms,
                )
                db.add(record)
                saved_count += 1

    db.commit()

    return {"message": "撮合完成", "total_pairs": total_pairs, "saved": saved_count}


def get_match_records(db: Session, page: int = 1, page_size: int = 10) -> dict:
    """
    查询撮合记录列表（按匹配度降序排列）

    Args:
        db (Session): 数据库会话
        page (int): 页码
        page_size (int): 每页数量

    Returns:
        dict: 含 total、page、page_size、items 的分页结果
    """
    query = db.query(MatchRecord)
    total = query.count()

    offset = (page - 1) * page_size
    records = query.order_by(MatchRecord.match_score.desc()).offset(offset).limit(page_size).all()

    items = []
    for record in records:
        # 关联查询教材和用户信息
        buy_book = db.query(Book).filter(Book.id == record.buy_book_id).first()
        sell_book = db.query(Book).filter(Book.id == record.sell_book_id).first()
        buy_user = db.query(User).filter(User.id == buy_book.user_id).first() if buy_book else None
        sell_user = db.query(User).filter(User.id == sell_book.user_id).first() if sell_book else None

        item = MatchRecordResponse(
            id=record.id,
            buy_book_id=record.buy_book_id,
            sell_book_id=record.sell_book_id,
            buy_book_title=buy_book.title if buy_book else None,
            sell_book_title=sell_book.title if sell_book else None,
            buy_username=buy_user.username if buy_user else None,
            sell_username=sell_user.username if sell_user else None,
            match_score=float(record.match_score),
            suggested_price=float(record.suggested_price),
            status=record.status,
            duration_ms=record.duration_ms,
            created_at=record.created_at,
        )
        items.append(item)

    return {"total": total, "page": page, "page_size": page_size, "items": items}


def get_realtime_matches(db: Session, limit: int = 2) -> RealtimeMatchResponse:
    """
    获取首页实时撮合展示数据

    业务流程：
        1. 查询最新的撮合记录（按创建时间降序）
        2. 对每条记录组装展示信息（用户、教材、价格、匹配度等）
        3. 求购记录和出售记录分别展示

    Args:
        db (Session): 数据库会话
        limit (int): 返回记录数量

    Returns:
        RealtimeMatchResponse: 实时撮合展示数据
    """
    total = db.query(MatchRecord).count()
    records = (
        db.query(MatchRecord)
        .order_by(MatchRecord.created_at.desc())
        .limit(limit)
        .all()
    )

    items = []
    for record in records:
        buy_book = db.query(Book).filter(Book.id == record.buy_book_id).first()
        sell_book = db.query(Book).filter(Book.id == record.sell_book_id).first()
        buy_user = db.query(User).filter(User.id == buy_book.user_id).first() if buy_book else None
        sell_user = db.query(User).filter(User.id == sell_book.user_id).first() if sell_book else None

        if not buy_book or not sell_book or not buy_user or not sell_user:
            continue

        # 求购方展示项
        items.append(RealtimeMatchItem(
            match_id=record.id,
            match_type="求购",
            username=buy_user.username,
            book_title=buy_book.title,
            course_name=buy_book.course_name,
            price=float(buy_book.price),
            price_label="预算",
            match_score=float(record.match_score),
            suggested_price=float(record.suggested_price),
            duration_ms=record.duration_ms or 0,
            credit_score=float(buy_user.credit_score),
        ))

        # 出售方展示项
        items.append(RealtimeMatchItem(
            match_id=record.id,
            match_type="出售",
            username=sell_user.username,
            book_title=sell_book.title,
            course_name=sell_book.course_name,
            price=float(sell_book.price),
            price_label="标价",
            match_score=float(record.match_score),
            suggested_price=float(record.suggested_price),
            duration_ms=record.duration_ms or 0,
            credit_score=float(sell_user.credit_score),
        ))

    return RealtimeMatchResponse(total=total, items=items)


def get_stats(db: Session) -> StatsResponse:
    """
    获取首页核心统计数据

    统计指标：
        1. total_books: 在售教材总数（status=active 的出售教材数量）
        2. match_success_rate: 撮合成功率（已成交记录数 / 撮合记录总数 × 100）
        3. avg_deal_price: 平均成交价（所有撮合记录的建议成交价平均值）

    Args:
        db (Session): 数据库会话

    Returns:
        StatsResponse: 核心统计数据
    """
    # 在售教材总数
    total_books = db.query(Book).filter(Book.book_type == "sell", Book.status == "active").count()

    # 撮合记录总数
    total_matches = db.query(MatchRecord).count()

    # 已成交记录数
    completed_matches = db.query(MatchRecord).filter(MatchRecord.status == "completed").count()

    # 撮合成功率（百分比）
    if total_matches > 0:
        match_success_rate = round((completed_matches / total_matches) * 100, 1)
    else:
        match_success_rate = 0.0

    # 平均成交价（取所有撮合记录的建议成交价平均值）
    avg_price_result = db.query(func.avg(MatchRecord.suggested_price)).scalar()
    avg_deal_price = round(float(avg_price_result), 2) if avg_price_result else 0.0

    return StatsResponse(
        total_books=total_books,
        match_success_rate=match_success_rate,
        avg_deal_price=avg_deal_price,
    )