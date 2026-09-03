# 真题库 data/realexam/

存放**真实考试真题**（2010 起，AP Physics 1 / Physics Bowl D1），每条记录带完整溯源：

```json
{
  "external_id": "real-ap1-2018-fr-q3",
  "topic": "kinematics",
  "difficulty": "hard",
  "question_type": "free_response",
  "question_text": "……(题目原文，转写自官方卷)……",
  "correct_answer": "……",
  "explanation": "……",
  "is_real": 1,
  "exam_year": 2018,
  "paper": "卷B",          // 或 AP1 官卷号 / Physics Bowl 套卷号
  "q_no": 3,               // 卷内题号
  "points": 6              // 分值（Physics Bowl 无分值可留空）
}
```

组织/下载管线自动把 `data/realexam/{exam}.json` 与 `data/builtin/` 合并，
按知识点归组并渲染：
- 题目卷 → 隐藏答案，逐题标注【真题｜年份·卷·第n题·x分】
- 答案卡 / 含答案 → 显示答案与解析
- 溯源缺口审计 API：`GET /api/realexam/stats` 返回 gaps / by_year，
  用于对账各年份真题是否都录入（全量不漏）。

> 内容以官方发布 / 授权转写为准。本目录由人工/外部源按上述格式持续投喂，
> 系统保证 2010 起每年每卷每题都被溯源标记并入库，不漏不错。
