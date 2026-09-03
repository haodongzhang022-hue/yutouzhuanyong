# V2 框架蓝本 · 04 · 细纲：REST API 契约

> 统一约定：响应体一律 `{ "code":0, "data":... }` 或 `{ "code":非0, "message":..., "detail":... }`；
> 错误语义一致，边界输入返回 4xx 而非 500。健康分级见 M6。

---

## 1. 通用约定

- Base：`/api`
- 统一响应：成功 `code=0`；失败 `code` 见下表。
- 时间戳统一 `YYYY-MM-DD HH:MM:SS`（本地时区，后端 Asia/Shanghai）。
- 分页参数：`limit`(默认10,上限100) / `offset`。

### 错误码表

| code | HTTP | 含义 |
|------|------|------|
| 0 | 200 | 成功 |
| 4001 | 400 | 参数错误（可带 detail 字段说明） |
| 4041 | 404 | 资源不存在 |
| 4291 | 429 | 触发限流 |
| 5001 | 500 | 内部错误（不含敏感信息） |
| 5031 | 503 | 依赖未就绪（DB 不可用等） |

---

## 2. 健康与运维

```
GET /api/health/live       → {"status":"up"}                       # 进程存活
GET /api/health/ready      → {"status":"ready","checks":{...}}     # DB/目录/调度就绪
GET /api/metrics           → Prometheus 文本                      # 指标
GET /api/logs?limit=20     → 最近采集/事件日志
```

---

## 3. 题库查询（保留 V1 + 增补）

```
GET /api/questions
  ?exam_type=ap_physics_1
  &kp_code=KP01            # ★ v2：按知识点筛选（走 kp_code 索引）
  &type=mc                 # ★ v2：按题型筛选
  &difficulty=medium
  &limit=10 &offset=0
→ data:{ total, questions:[{...含 kp_code, norm_qid...}] }

GET /api/questions/{id}            # 单题详情
GET /api/stats                     # 库内统计 + 近况
```

---

## 4. 专项卷读取（★ v2，M3 产物寻址）

```
GET /api/papers
  ?exam_type=ap_physics_1          # 该考试卷目录
  &kp_code=KP01                    # 可选：指定知识点
→ data:{ papers:[{ kp_code, name, version, question_file, answer_file }] }

GET /api/papers/{exam}/{kp_code}   # 读取一份专项卷题目卷(markdown/文本)
GET /api/papers/{exam}/{kp_code}/answer   # 解析卷
  ?format=markdown|html            # v2 渐进支持 html
```

> 实现：卷先落盘为文件（`data/papers/`），API 读取并登记于 `paper_runs`；
> 寻址键 = `{exam}/{kp_code}` + version。

---

## 5. 练习闭环（★ v2，M4）

```
POST /api/practice/session          # 开一个作答会话
  body:{ exam_type, kp_code?, type?, difficulty?, count }
→ data:{ session_id, questions:[题干(不含答案)] }

POST /api/practice/session/{sid}/submit
  body:{ answers:[{ question_id, user_answer }] }
→ data:{ results:[{ question_id, correct, correct_answer }], score, mistakes:[ids] }

GET  /api/practice/mistakes         # 错题本
  ?user_key=&exam_type=
POST /api/practice/mistakes/{id}/review   # 标记复习/掌握
GET  /api/practice/stats            # 进度统计（正确率/覆盖/连续天数）
     ?user_key=
GET/POST /api/study/plans           # 学习计划
```

---

## 6. 采集触发

```
POST /api/fetch        { exam_types:[...], count? }   # 手动每日采集
POST /api/fetch/all                                     # 全量拉取
POST /api/rebuild/papers  { exam_type?, kp_code? }     # ★ 手动触发专项卷重建
```

---

## 7. 变更记录

| 端点 | V1 | V2 |
|------|----|----|
| /api/health | 单一 | live/ready 分级 |
| /api/questions | topic 筛选 | +kp_code/type/difficulty 结构化筛选 |
| /api/papers/* | ❌ | ✅ 卷寻址读取 |
| /api/practice/* | ❌ | ✅ 练习闭环 |
| /api/rebuild | ❌ | ✅ 卷重建触发 |
