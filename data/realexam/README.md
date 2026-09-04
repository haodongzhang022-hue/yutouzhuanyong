# 真题库 data/realexam/

存放**真实考试真题**，每条记录带完整溯源（哪年·哪卷·第几题·多少分）。

本目录是**持续投喂入口**：把授权/官方渠道获得的真题按下方格式追加写入
`{exam}.json`，系统每日自动幂等同步入库并重建专项卷，绝不遗漏、也不重复。

## 支持的两类考试与开考年（避免口误全采2010）

| 考试 | 开考年 | 说明 |
|------|--------|------|
| AP Physics 1（`ap_physics_1`）| **2015** | AP1 自 2015 年 5 月首次开考，取代 AP Physics B。**2010-2014 对应前身 AP Physics B**。 |
| Physics Bowl D1（`physics_bowl_d1`）| 逐年(2010 起) | Division 1 面向 <1 年物理课程学生，分区域/全国等套卷。 |

> 若需收录 AP Physics B（2010-2014）真题，应作为独立考试 `ap_physics_b` 录入，
> 而非冒充 AP Physics 1。当前清单 `manifest.yaml` 默认按各考试真实开考年展开。

## 每条记录的溯源字段（必须，no-miss 对账依赖）

```json
{
  "external_id": "real-ap1-2018-fr-q3",
  "topic": "kinematics",
  "difficulty": "hard",
  "question_type": "free_response",
  "question_text": "……(题目原文，授权转写)……",
  "correct_answer": "……",
  "explanation": "……",
  "is_real": 1,
  "exam_year": 2018,
  "paper": "FR",           // 取值须与 manifest.yaml 的 papers 对齐(如 FR/区域卷/全国卷)
  "q_no": 3,               // 卷内题号
  "points": 6              // 分值
}
```

`exam_year / q_no / points / paper` 缺任一个都会被 `realexam_gaps` 与
no-miss 对账标为缺标/无法归卷，无法通过"全量不漏"校验。

## 持续同步 + 全量不漏对账

```bash
# 一键：同步真题入库+重建专项卷，再按清单逐卷对账(报缺哪些年份/卷)
python scripts/realexam_sync_check.py                  # 全部考试
python scripts/realexam_sync_check.py --exam ap_physics_1
python scripts/realexam_sync_check.py --json           # 结构化输出

# 仅对账(不改库)
python scripts/check_realexam.py
python scripts/check_realexam.py --exam ap_physics_1
```

- 系统每日定时任务也会自动同步本目录（见 scheduler），实现"持续获取"。
- 每批同步登记到 `realexam_imports` 可对账；重复投喂幂等去重，不重复入库。

## 全量清单（manifest）

`manifest.yaml` 登记每类考试**历年应有试卷**（开考年 + 每年应含的卷/套）。
no-miss 引擎据此比对题库，`missing=[]` 即真题全量齐全、一个不漏。

> 真实题目原文版权属出题机构（College Board / AAPT）。MC 等未公开部分不能
> 从公开渠道整卷转载；本系统不自造真题，只对**官方公布 / 授权转写**的内容
> 做幂等录入、溯源与"不漏"对账。官方每年公布的 AP FRQ 可在 AP Central 获得。

## 组织与三种下载

组织/下载管线自动把 `data/realexam/{exam}.json` 与 `data/builtin/` 合并，
按知识点归组并渲染；每知识点可单独下载：
- `题目卷` → 隐藏答案，逐题标注【真题｜年份·卷·第n题·x分】
- `答案卡` → 只含答案解析
- `含答案` → 题目+答案全卷

在线对账：`GET /api/realexam/stats`（含 no_miss_audit）。
