"""
生成自包含预览页面：用 TestClient 获取所有真实数据 + Agent 对话结果
嵌入到 HTML 中，无需后端服务器即可在浏览器中打开
"""
import json
import sys
sys.path.insert(0, '.')

from starlette.testclient import TestClient
from main import app

c = TestClient(app)

# ============================================================
# 1. 获取所有静态数据
# ============================================================
data = {}
data["stats"] = c.get("/api/match/stats").json()["data"]
data["realtime"] = c.get("/api/match/realtime?limit=2").json()["data"]
data["categories"] = c.get("/api/books/categories/all").json()["data"]
data["books_all"] = c.get("/api/books?page=1&page_size=50").json()["data"]
data["match_records"] = c.get("/api/match/records?page=1&page_size=10").json()["data"]

# ============================================================
# 2. 预计算 Agent 常见问题回复
# ============================================================
agent_questions = [
    "帮我找高等数学的教材",
    "平台统计数据",
    "查看撮合记录",
    "有哪些学科分类",
    "执行撮合",
    "帮我找数据结构",
    "列出所有计算机类的教材",
    "你好",
]
agent_replies = {}
for q in agent_questions:
    r = c.post("/api/agent/chat", json={"message": q, "session_id": "preview"}).json()
    agent_replies[q] = {"reply": r["reply"], "steps": r["steps"], "mode": r["mode"]}

data["agent_replies"] = agent_replies

# ============================================================
# 3. 读取 index.html 并替换为自包含模式
# ============================================================
html = open(r"E:\book_bridge\frontend\index.html", encoding="utf-8").read()
mock_json = json.dumps(data, ensure_ascii=False, default=str)

old_block = """        // 后端 API 基础地址
        // 整合部署：通过后端 8000 端口访问前端，port 为 '8000'，用同源（空字符串）
        // 直接打开 html 文件：port 为空字符串，也用同源
        // 前后端分离开发：前端在其它端口（如 5500），需指定后端地址
        const API_BASE = (window.location.port === '8000' || window.location.port === '') ? '' : 'http://localhost:8000';

        // 当前登录用户（模拟状态）
        let currentUser = null;

        // ============================================================
        // 工具函数：调用 API
        // ============================================================
        async function apiGet(path) {
            const res = await fetch(API_BASE + path);
            return res.json();
        }
        async function apiPost(path, body) {
            const res = await fetch(API_BASE + path, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            return res.json();
        }"""

new_block = """        // ============================================================
        // 自包含预览模式：数据内嵌，无需后端服务
        // ============================================================
        const MOCK_DATA = """ + mock_json + """;

        let currentUser = null;

        async function apiGet(path) {
            const url = new URL(path, 'http://localhost');
            const p = url.pathname.replace(/\\/$/, '');
            const q = url.searchParams;
            if (p === '/api/match/stats') return {code:200, message:'success', data: MOCK_DATA.stats};
            if (p === '/api/match/realtime') {
                const limit = parseInt(q.get('limit')||'2');
                return {code:200, message:'success', data:{total:MOCK_DATA.realtime.total, items:MOCK_DATA.realtime.items.slice(0, limit*2)}};
            }
            if (p === '/api/match/records') return {code:200, message:'success', data: MOCK_DATA.match_records};
            if (p === '/api/books/categories/all') return {code:200, message:'success', data: MOCK_DATA.categories};
            if (p === '/api/books/search') {
                const kw = (q.get('keyword')||'').toLowerCase();
                const ps = parseInt(q.get('page_size')||'10');
                let items = MOCK_DATA.books_all.items.filter(b =>
                    (b.title||'').toLowerCase().includes(kw) ||
                    (b.isbn||'').toLowerCase().includes(kw) ||
                    (b.course_name||'').toLowerCase().includes(kw) ||
                    (b.author||'').toLowerCase().includes(kw)
                );
                return {code:200, message:'success', data:{total:items.length, page:1, page_size:ps, items:items.slice(0, ps)}};
            }
            const m = p.match(/^\\/api\\/books\\/(\\d+)$/);
            if (m) {
                const b = MOCK_DATA.books_all.items.find(x => x.id === parseInt(m[1]));
                return b ? {code:200, message:'success', data:b} : {code:404, message:'教材不存在', data:null};
            }
            if (p === '/api/books') {
                const page = parseInt(q.get('page')||'1');
                const ps = parseInt(q.get('page_size')||'10');
                const cat = q.get('category');
                const bt = q.get('book_type');
                let items = MOCK_DATA.books_all.items.filter(b => b.status==='active');
                if (cat) items = items.filter(b => b.category === cat);
                if (bt) items = items.filter(b => b.book_type === bt);
                return {code:200, message:'success', data:{total:items.length, page, page_size:ps, items:items.slice((page-1)*ps, (page-1)*ps+ps)}};
            }
            if (p === '/api/health') return {code:200, message:'success', data:{status:'running'}};
            if (p === '/api/agent/status') return {code:200, message:'success', data:{mode:'rule_engine', llm_available:false, tool_count:10, active_sessions:1, description:'离线规则引擎模式'}};
            if (p === '/api/agent/tools') return {code:200, message:'success', data:{tools:[], count:10}};
            return {code:404, message:'not found', data:null};
        }
        async function apiPost(path, body) {
            if (path === '/api/users/login') {
                if (body.username === '张明轩' && body.password === '95')
                    return {code:200, message:'登录成功', data:{user_id:1, username:'张明轩', credit_score:95.0}};
                return {code:400, message:'用户名或密码错误', data:null};
            }
            if (path === '/api/books') {
                const nb = Object.assign({}, body, {id: Date.now(), username:'张明轩', status:'active', created_at:new Date().toISOString()});
                MOCK_DATA.books_all.items.unshift(nb);
                if (nb.book_type === 'sell') MOCK_DATA.stats.total_books += 1;
                return {code:200, message:'发布成功', data:nb};
            }
            if (path === '/api/agent/chat') {
                return {code:200, reply: agentLocalReply(body.message), steps: agentLocalSteps(body.message), mode:'rule_engine', rounds:1};
            }
            if (path === '/api/agent/clear') return {code:200, message:'success', data:{session_id:body.session_id}};
            return {code:200, message:'success', data:body};
        }
        function agentLocalReply(msg) {
            const replies = MOCK_DATA.agent_replies;
            for (const q in replies) {
                if (msg.includes(q) || q.includes(msg)) return replies[q].reply;
            }
            if (msg.includes('搜索')||msg.includes('找')||msg.includes('搜')) {
                for (const q in replies) { if (q.includes('找')) return replies[q].reply; }
            }
            if (msg.includes('统计')||msg.includes('数据')||msg.includes('概况')) {
                for (const q in replies) { if (q.includes('统计')) return replies[q].reply; }
            }
            if (msg.includes('撮合记录')||msg.includes('匹配记录')) {
                for (const q in replies) { if (q.includes('撮合记录')) return replies[q].reply; }
            }
            if (msg.includes('分类')||msg.includes('学科')) {
                for (const q in replies) { if (q.includes('分类')) return replies[q].reply; }
            }
            if (msg.includes('撮合')||msg.includes('执行')) {
                for (const q in replies) { if (q.includes('执行')) return replies[q].reply; }
            }
            if (msg.includes('你好')||msg.includes('hello')||msg.includes('在吗')) {
                for (const q in replies) { if (q.includes('你好')) return replies[q].reply; }
            }
            return '我是书桥 AI 助手，可以帮你搜索教材、查看撮合、了解平台数据等。\\n试试问我：\"帮我找高等数学\"、\"平台统计数据\"、\"查看撮合记录\"';
        }
        function agentLocalSteps(msg) {
            const replies = MOCK_DATA.agent_replies;
            for (const q in replies) {
                if (msg.includes(q) || q.includes(msg)) return replies[q].steps || [];
            }
            return [{type:'think', content:'匹配预设回复'}];
        }"""

assert old_block in html, "未找到替换目标段"
html = html.replace(old_block, new_block)

out_path = r"E:\book_bridge\frontend\preview.html"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"✅ 预览页面已生成: {out_path}")
print(f"   数据量: {len(mock_json)} 字符")
print(f"   Agent预设回复: {len(agent_replies)} 条")