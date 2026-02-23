# 🤖 AI Co-Worker Engine — Bao Cao Ky Thuat (Tieng Viet)

> He thong AI Co-Worker Engine mo phong dong nghiep ao cho bai tap dao tao lanh dao.
> Tap trung vao kha nang phan vai, bo nho, va ngon ngu theo ngu canh doanh nghiep.

**Nguoi thuc hien:** [Ten cua ban]

---

## 📋 Tong Quan

AI Co-Worker Engine la he thong NPC (dong nghiep ao) cho bai tap mo phong cong viec. Nguoi dung tro chuyen voi nhieu nhan vat AI co tinh cach, bo nho, va muc tieu rieng, ho tro thiet ke chuong trinh phat trien lanh dao.

**Ngu canh mo phong:** Gucci Group HRM Talent & Leadership Development 2.0

| AI Co-worker | Vai tro | Tinh cach chinh |
|---|---|---|
| **CEO** | Bao ve Group DNA, brand autonomy | Tam nhin, quyet doan |
| **CHRO** | Dan dat khung nang luc | Dong cam, co cau truc |
| **Regional Manager** | Rollout chau Au, van hanh | Thuc te, chi tiet |

---

## 🧠 Cach Toi Xay Dung Multi-Agent

### 1) Mo hinh dieu phoi 2 lop: Supervisor + Director

- **Supervisor** phan loai cau hoi theo noi dung de chon dung agent.
- **Director** giam sat tien do, phat hien khi nguoi dung bi "mac ket", va kich hoat Mentor neu can.
- Moi agent chi tra loi 1 luot, sau do ket thuc vong (one-turn per invoke) de de duyet va luu state.

**Files chinh:**
- [app/engine/supervisor.py](app/engine/supervisor.py)
- [app/engine/director.py](app/engine/director.py)
- [app/engine/graph.py](app/engine/graph.py)

### 2) Bo nho chung AgentState (Shared State)

Tat ca agent cung doc va ghi vao mot bo nho chung, bao gom:
- lich su hoi thoai
- sentiment score
- task progress
- emotional memory (cam xuc cua agent voi nguoi dung)
- user approach style

**File:** [app/engine/state.py](app/engine/state.py)

### 3) RAG theo agent (context thong minh)

He thong su dung FAISS de tim kiem tai lieu va chi phan phoi context lien quan den agent do. Vi du:
- CEO nhan context ve Group DNA, brand autonomy
- CHRO nhan context ve competency framework
- Regional Manager nhan context ve rollout chau Au

**Files:**
- [app/knowledge/retriever.py](app/knowledge/retriever.py)
- [app/db/vector/faiss_store.py](app/db/vector/faiss_store.py)

---

## 🤖 Cach Lam Cho Agent "Thong Minh"

### 1) System Prompt ro rang + rang buoc an

Moi agent co prompt rieng voi tinh cach va quy tac an (hidden constraints). Vi du CEO khong bao gio chap nhan chuan hoa tat ca brand.

**File:** [app/personas/prompts.py](app/personas/prompts.py)

### 2) Bo nho cam xuc (Emotional Memory)

Neu nguoi dung gay kho chiu o Turn 1, agent se giu thai do can trong o Turn 5. Dieu nay giup hoi thoai tu nhien va co tinh lien tuc.

### 3) Task Progress Tracking

He thong tu dong danh dau cac buoc hoan thanh (consult CEO, consult CHRO, draft competency model...) dua tren keywords trong hoi thoai.

**File:** [app/engine/director.py](app/engine/director.py)

### 4) Safety & Guardrails

Co bo loc an toan cho jailbreak, prompt extraction, off-topic. Khi vi pham, he thong tu dong chuyen ve SafetyBlock.

**File:** [app/api/middleware/safety.py](app/api/middleware/safety.py)

---

## 🧱 Kien Truc He Thong

```
Client UI
   │
FastAPI API + Safety Middleware
   │
LangGraph Orchestrator
   ├─ Supervisor (router)
   ├─ Director (progress monitor)
   └─ Agents (CEO / CHRO / Regional / Mentor)
   │
Shared State + RAG + Cache
   │
PostgreSQL + MongoDB + FAISS
```

---

## 🧪 Cach Chay Du An

```bash
pip install -r requirements.txt
python -m app.knowledge.ingest
uvicorn app.main:app --reload
```
