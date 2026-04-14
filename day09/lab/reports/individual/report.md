# Báo Cáo Cá Nhân — Day 09: Multi-Agent Orchestration

**Họ tên:** [Tên của bạn]  
**Vai trò:** Supervisor Owner + Worker Owner + MCP Owner + Trace & Docs Owner  
**Date:** 2026-04-14

---

## 1. Phần tôi phụ trách

Tôi phụ trách toàn bộ pipeline từ Sprint 1 đến Sprint 4:

**Sprint 1 — Supervisor (`graph.py`):**
- Implement `AgentState` TypedDict với 16 fields đầy đủ theo contract
- Viết `supervisor_node()` với routing logic keyword-based 2 nhóm (policy + retrieval)
- Implement multi-hop detection: khi cả 2 nhóm match → route sang `policy_tool_worker`
- `risk_high` flag khi phát hiện "2am", "khẩn cấp", "emergency"

**Sprint 2 — Workers:**
- `workers/retrieval.py`: `retrieve_dense()` với sentence-transformers + ChromaDB cosine
- `workers/policy_tool.py`: Exception rules (Flash Sale, digital, activated, temporal), access level detection
- `workers/synthesis.py`: LLM synthesis (gpt-4o-mini, temp=0.1), confidence scoring thực tế

**Sprint 3 — MCP (`mcp_server.py`):**
- 4 tools: `search_kb`, `get_ticket_info`, `check_access_permission`, `create_ticket`
- Policy worker gọi MCP 2-3 times cho câu phức tạp (access + ticket info)

**Sprint 4 — ChromaDB Index + Eval:**
- `build_index.py`: chunking theo sections, 41 chunks từ 5 docs
- `eval_trace.py`: chạy 15 test questions, lưu trace JSONL

---

## 2. Quyết định kỹ thuật: Route_reason bằng keyword matching thay vì LLM classifier

**Quyết định:** Supervisor dùng **keyword matching** (Python `in` operator) thay vì gọi LLM classifier để quyết định route.

**Lý do chọn:**
1. **Latency**: Keyword matching là O(n) string ops, < 1ms. LLM call thêm 1-2s mỗi query
2. **Predictability**: Routing deterministic, dễ debug khi sai
3. **Bằng chứng từ trace**: 3/3 test queries route đúng không cần LLM:
   - "SLA xử lý ticket P1" → `route_reason: "task contains retrieval keyword: ['p1', 'sla', 'ticket']"` ✓
   - "Flash Sale hoàn tiền" → `route_reason: "task contains policy/access keyword: ['hoàn tiền', 'flash sale']"` ✓
   - "Level 2 access + P1" → `route_reason: "multi-hop: policy + retrieval keywords..."` ✓

**Trade-off:**
- Mất khả năng xử lý paraphrase (VD: "trả lại tiền" không match "hoàn tiền")
- Giải pháp: keyword list có thể mở rộng dễ dàng, hoặc nâng cấp sang embedding-based routing sau

```python
# Từ graph.py — keyword routing thực tế
POLICY_KEYWORDS = ["hoàn tiền", "refund", "flash sale", "license", ...]
RETRIEVAL_KEYWORDS = ["p1", "sla", "ticket", "remote", ...]

# Multi-hop: cả 2 nhóm đều match
policy_hit = any(kw in task for kw in POLICY_KEYWORDS)
retrieval_hit = any(kw in task for kw in RETRIEVAL_KEYWORDS)
if policy_hit and retrieval_hit:
    route = "policy_tool_worker"
    route_reason = "multi-hop: policy + retrieval keywords"
```

---

## 3. Lỗi đã sửa: Windows Console Unicode Encoding

**Mô tả lỗi:**
```
UnicodeEncodeError: 'charmap' codec can't encode character '\u2192' in position 27: character maps to <undefined>
```

**Nguyên nhân:** Windows PowerShell dùng codepage cp1252 mặc định, không hiểu các ký tự `→`, `✅`, `📦`, `▶`.

**Cách sửa:**
1. Thêm vào đầu `graph.py`:
```python
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
```
2. Thay toàn bộ emoji/arrow trong print statements bằng ASCII: `✅` → `[DONE]`, `→` → `->`.

**Bằng chứng trước/sau:**
- Trước: `build_index.py` crash ngay sau "Loading model"
- Sau khi fix: Index chạy thành công, in ra `[ok] Model loaded`, `[ok] Created collection 'day09_docs'`, `41 chunks indexed`

**Lesson learned:** Khi code chạy trên Windows, luôn add `sys.stdout.reconfigure(encoding="utf-8")` hoặc dùng `PYTHONIOENCODING=utf-8` environment variable.

---

## 4. Tự đánh giá

**Làm tốt:**
- Routing logic đa cấp hoạt động chính xác cho cả simple và multi-hop queries
- MCP integration pipeline (search_kb → check_access_permission → get_ticket_info) cho câu gq09
- Confidence scoring thực tế từ chunk scores (không hard-code) → đáp ứng bonus criteria

**Yếu:**
- Latency còn cao (~20s query đầu do model load, ~10s query sau) — chưa cache model
- Policy analysis phụ thuộc keyword rules, có thể miss paraphrase
- Docs templates được viết trước khi có trace thực tế — cần update sau khi eval xong

**Nhóm phụ thuộc tôi ở:**
- Toàn bộ pipeline — tôi phụ trách 1 mình nên không có dependency conflict
- Mọi thay đổi core graph/workers đều qua tôi

---

## 5. Nếu có thêm 2 giờ

**Cách cải thiện cụ thể (dựa trên trace):**

Từ trace, câu `q01: "SLA xử lý ticket P1 là bao lâu?"` có `latency_ms: 20940ms` (21 giây) — quá chậm do model load mỗi lần query.

**Cải tiến:** Cache `SentenceTransformer` model như module-level singleton:
```python
# workers/retrieval.py — thêm module-level cache
_model_cache = None

def _get_embedding_fn():
    global _model_cache
    if _model_cache is None:
        from sentence_transformers import SentenceTransformer
        _model_cache = SentenceTransformer("all-MiniLM-L6-v2")
    return lambda text: _model_cache.encode([text])[0].tolist()
```

Kết quả dự kiến: Latency từ 20s → 2-3s (10x faster). Đây là cải tiến có impact lớn nhất từ trace evidence.
