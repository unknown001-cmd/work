import json

html = open(r'E:\book_bridge\frontend\index.html', encoding='utf-8').read()
mock = open(r'E:\book_bridge\preview_data.json', encoding='utf-8').read()

old = """        // 后端 API 基础地址
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

new = """        // ============================================================
        // 自包含预览模式：数据内嵌，无需后端服务
        // ============================================================
        const MOCK_DATA = %s;

        // 当前登录用户（模拟状态）
        let currentUser = null;

        // ============================================================
        // 工具函数：从本地模拟数据返回（替代后端 API）
        // ============================================================
        async function apiGet(path) {
            const url = new URL(path, 'http://localhost');
            const p = url.pathname.replace(/\\/$/, '');
            const q = url.searchParams;
            if (p === '/api/match/stats') return {code:200, message:'success', data: MOCK_DATA.stats};
            if (p === '/api/match/realtime') {
                const limit = parseInt(q.get('limit')||'2');
                return {code:200, message:'success', data:{total:MOCK_DATA.realtime.total, items:MOCK_DATA.realtime.items.slice(0, limit*2)}};
            }
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
            if (p === '/api/health') return {code:200, message:'success', data:{status:'running', service:'BOOKBRIDGE preview'}};
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
            return {code:200, message:'success', data:body};
        }""" % mock

assert old in html, "未找到替换目标段"
html = html.replace(old, new)
open(r'E:\book_bridge\frontend\preview.html', 'w', encoding='utf-8').write(html)
print('preview.html 已生成')