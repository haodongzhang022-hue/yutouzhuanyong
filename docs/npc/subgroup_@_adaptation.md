# 子组织（subgroup）下 NPC @ 协作与自动补全的适配方案

> 角色：架构·总师 · 载体仓库：`dongxiaozu/yutoujing/yutouzhuanyong`
> 问题入口：ISSUE #2 ——「到了新环境点了 star 也没出来 @ 自动补全的 NPC，且互相 @ 协作的能力也没了」

---

## 0. 结论先行（给人类俯瞰）

- **根因成立，但方向要校正**：问题不是「引用没写子组织 `yutoujing`」，而是——**整套 NPC @ 引用与解析模型是「两级扁平命名空间」(`@org/repo(角色)`)，而 CNB 子组织是「三级路径」(`org/subgroup/repo`)**。三级路径喂给两级解析器，边界被吞掉，角色作用域对不上，于是自动补全、star、互相 @ 协作在子组织仓库里全部失效。
- 本仓库（AP Physics）是**纯业务仓库，不含任何 NPC 角色声明**；架构师团队角色都承载在根组织仓库 `dongdongxiaozu/dongjiagoushi`（`@dongdongxiaozu/dongjiagoushi(架构·角色)`）。
- 一键能改的是**角色承载侧**（`dongjiagoushi` 的 resolver 与文档）与**本子组织仓库侧的接入声明**。平台级 NPC 可见性（star / 自动补全的注册）属平台设置，需按下方第 5 节步骤在平台侧放行。

---

## 1. 环境事实（实测留痕）

从运行时注入的环境变量确认本会话处于**子组织**：

| 环境变量 | 值 | 含义 |
|---|---|---|
| `CNB_ROOT_SLUG` | `dongdongxiaozu` | 根组织 org |
| `CNB_GROUP_SLUG` | `dongdongxiaozu/yutoujing` | **子组织（2 段！）** |
| `CNB_REPO_NAME` | `yutouzhuanyong` | 仓库名 |
| `CNB_REPO_SLUG` | `dongdongxiaozu/yutoujing/yutouzhuanyong` | 完整 3 级仓库路径 |
| `CNB_NPC_SLUG` | `dongdongxiaozu/dongjiagoushi` | 架构·总师 NPC 承载仓库（根组织） |

关键矛盾：

- **角色承载仓库**（NPC 定义所在）是**根组织**的 `dongdongxiaozu/dongjiagoushi` —— `@org/repo(角色)` = `@dongdongxiaozu/dongjiagoushi(架构·经理)` 等，两级。
- **当前操作仓库**是**子组织**下的 `dongdongxiaozu/yutoujing/yutouzhuanyong` —— 三级。

两级模型去套三级仓库，必然错位。

---

## 2. 根因分析（三层错位）

### 2.1 解析层错位 —— HandleAbility resolver 只认两级

架构师体系把「@ 谁」抽象为 `local-agent/handle/resolver.py` 的 `HandleAbility`（见承载仓库 `docs/HANDLE_ABILITY.md`）。它区分两个维度：

- **角色承载仓库**：`@org/承载仓库(角色)` 里的仓库；
- **当前操作仓库**：由 `CNB_GROUP_SLUG / CNB_ROOT_SLUG + CNB_REPO_NAME` 或 git remote 探测。

它的核心 `detect_current_org_repo()` 在两个数据源都拿不到「干净的三段」：

| 数据源 | 取到 | 问题 |
|---|---|---|
| 环境 `CNB_GROUP_SLUG + CNB_REPO_NAME` | org=`dongdongxiaozu/yutoujing`、repo=`yutouzhuanyong` | org 段**已含 `/`（子组织）**，`format_at()` 会拼出 `@dongdongxiaozu/yutoujing/yutouzhuanyong(角色)` —— 3 段，不合 `@org/repo` 2 段约定 |
| git remote `…/dongdongxiaozu/yutoujing/yutouzhuanyong.git` | 正则 `([\w.-]+/[\w.-]+?)` 捕获 `yutoujing/yutouzhuanyong` | **根组织 `dongdongxiaozu` 被吞**，子组织 `yutoujing` 被误当 org |

`is_cross_repo()` / `resolve()` 用这些「污染过的 org/repo」去做跨仓库判定与权限建议，判定结果在子组织场景下必然错误。

### 2.2 作用域层错位 —— 角色权限只覆盖其承载仓库

承载仓库文档写明：「角色权限通常只覆盖其所属仓库」。架构师角色注册在**根组织** `dongjiagoushi`；现在业务仓库在**子组织** `yutoujing/yutouzhuanyong`。角色若未在子组织范围内被授权/收录，star 不生效、@ 自动补全列表不含该角色、互相 @ 协作链随之断裂。

### 2.3 平台可见性层错位 —— 自动补全/star 依赖仓库或组织级收录

`.cnb/settings.yml` 中 `npc.roles` 是仓库级角色声明的事实源（承载仓库据此把角色送进平台 NPC 选择器）。业务仓库本身没有该声明，平台不会把 `dongjiagoushi` 的角色自动列进本仓库的 @ 候选。

---

## 3. 适配目标（验收标准）

在**子组织仓库** `dongdongxiaozu/yutoujing/yutouzhuanyong` 内：

1. `@` 输入「架构」能自动补全出 `架构·秘书 / 产品 / 总师 / 经理 / 开发 / 评审 / 测试 / 交付 …` 整组；
2. 点 star 后这些角色在**本仓库内**常驻可 @；
3. 角色之间用接力卡 `[触发:架构·X]` 能互相唤醒并拿到接单回执（L3/L4 不断裂）；
4. 全路径引用**能正确区分 根组织/子组织/仓库 三段**，不把 `yutoujing` 误当 org。

---

## 4. 根因到方案映射

| 层 | 根因 | 对策 | 落地位置 |
|---|---|---|---|
| 解析层 | resolver 只认两级 | 升级为**可变段数**命名空间模型（2 段 `org/repo` 或 3 段 `org/subgroup/repo`），段位语义化 | `dongjiagoushi` 的 `local-agent/handle/resolver.py` |
| 作用域层 | 角色只覆盖承载仓库 | 在**本业务仓库**声明/授权该团队；承载仓库文档化「接入子组织仓库」步骤 | 本仓库 `.cnb/` 接入声明 + 平台授权 |
| 可见性层 | @ 候选不含团队 | 按承载仓库口径把团队角色收录进本仓库（或本子组织）NPC 候选 | 平台 NPC 收录/star |

---

## 5. 工程实施方案

### 5.1 解析层修正（承载仓库侧 · 需回 `dongjiagoushi` 仓库提交）

给 `resolver.py` 增加「三级路径」支持，并把环境探测的 org 处理从「当 `CNB_GROUP_SLUG` 含 `/` 时拆成 subgroup + 根 org」修正：

```python
# 关键改动点示意
def split_slug(slug):
    """'a/b/c' -> (root='a', group='a/b', repo='c')；'a/b' -> (root='a', group='a/b', repo=None)。"""
    parts = slug.split('/')
    if len(parts) == 3:
        return parts[0], f"{parts[0]}/{parts[1]}", parts[2]   # 三级：org/subgroup/repo
    if len(parts) == 2:
        return parts[0], parts[0], parts[1]                    # 二级：org/repo
    return parts[0], parts[0], parts[0]

def detect_current_org_repo():
    # 优先级：显式 CNB_REPO_SLUG（最权威、天然三段）> CNB_GROUP_SLUG+CNB_REPO_NAME > git remote > 默认
    slug = os.environ.get("CNB_REPO_SLUG")
    if slug:
        root, group, repo = split_slug(slug)
        return {"root_org": root, "group": group, "repo": repo, "slug": slug}
    ...
```

`@` 引用约定升级为**「按目标仓库完整 slug 引用」**：目标仓库在子组织下就用 `@dongdongxiaozu/yutoujing/yutouzhuanyong(架构·X)`，目标角色承载在根组织就用 `@dongdongxiaozu/dongjiagoushi(架构·X)`——引用什么，取决于**被唤醒角色要有目标仓库权限**，而不是取决于写死哪一段。

> 完整补丁见 §7 参考（随本文档一并附上，供 `dongjiagoushi` 侧合入）。

### 5.2 可见性层（平台侧 · 需人类/管理员放行）

在平台 NPC/Agent 设置中，把架构师团队角色**授权到子组织 `dongdongxiaozu/yutoujing`（或其下仓库）**，使：
- 本仓库 @ 自动补全收录该团队；
- star 后在本仓库内常驻可 @。
> ⚠️ 该动作是**平台级配置**，非仓库代码，须由具备平台管理权限的人类在 NPC 选择器/云原生开发 Agent 设置中完成；本 NPC 无法代办。此为「需人拍板」项（CP 放行点）。

### 5.3 本仓库接入声明（可在本仓库落地）

若目标运行方式是「本子组织仓库自建/复用该团队」，在本仓库根目录放置 `settings.yml` 的角色骨架（声明各 `架构·` 角色人设与 slogan，供平台收录与 @ 触发兜底），并加 `.cnb.yml` 的 `issue.comment@npc` 兜底接线。内容与承载仓库 `.cnb/settings.yml` 同源，避免另起炉灶。

---

## 6. 可行性验证与风险

| 假设 | 验证方式 | 结论 |
|---|---|---|
| 本会话确实处于子组织 3 级路径 | 实测 `CNB_GROUP_SLUG`/`CNB_REPO_SLUG` | ✅ 已确认 |
| resolver 只认两级会解析错 | 用真实 git remote/环境喂 `detect_current_org_repo()` 模拟 | ✅ 已复现（根 org 被吞 / org 含 `/`） |
| `.cnb/settings.yml` 的 `npc.roles` 是仓库级角色事实源 | 承载仓库 `.cnb.yml`/`settings.yml` 注释与结构 | ✅ 强支持（同源声明复用） |
| 平台自动补全/star 需在平台侧授权 | 属平台设置，仓库代码无法变更 | ⚠️ 需人拍板放行 |

**风险清单**

| 风险 | 等级 | 规避 |
|---|---|---|
| 我无法直接改平台 NPC 收录/授权 | MEDIUM | 显式列出平台侧操作步骤，交人类 CP 放行 |
| resolver 改动在承载仓库（非本仓库），本轮只能交付补丁不能合入 | MEDIUM | 交付完整补丁 + 改动点，交接 `dongjiagoushi` 侧提交 |
| 三级路径解析若改错影响现有两级场景 | MEDIUM | 两级/三级双兼容（`split_slug` 按段数分派），保留两级回退 |
| 角色人设在本仓库声明若与承载仓库漂移 | LOW | 声明与承载仓库 `.cnb/settings.yml` 同源复制 + 注释来源 |

---

## 7. 索引

| 产物 | 位置 |
|---|---|
| 本适配方案 | `docs/npc/subgroup_@_adaptation.md`（本文件） |
| 承载仓库自适应 @ 解析说明 | `dongjiagoushi` → `docs/HANDLE_ABILITY.md` |
| 承载仓库解析器 | `dongjiagoushi` → `local-agent/handle/resolver.py` |
| 角色人设事实源 | `dongjiagoushi` → `.cnb/settings.yml` |
| 平台跨宿主适配 | `dongjiagoushi` → `docs/PLATFORM_ADAPTERS.md` |
| 接入模板（可选随附） | `docs/npc/settings.subgroup.example.yml` |

---

## 8. 汇报与复盘

### 决策摘要
- **已定**：根因 = 两级 @ 命名空间 vs 子组织三级仓库错位；需「解析层 + 作用域 + 平台可见性」三层适配。
- **待定（需人拍板）**：平台侧对架构师团队在子组织的收录/授权（§5.2）。
- **交接**：resolver 补丁回 `dongjiagoushi` 合入；本仓库按需放接入声明。

### 复盘四要素
- **根因**：参考模型把命名空间写死成两级，未适配 CNB 子组织三级路径；角色作用域未覆盖子组织仓库。
- **教训**：跨仓库/跨组织协作的引用与解析，必须「按目标仓库的完整 slug + 权限动态解析」，不能写死段数或仓库名。
- **预防**：新增子组织场景后，resolver 纳入 `org/subgroup/repo` 解析用例 + 自动补全冒烟测试。
- **已落地**：本诊断 + 适配方案 + 补丁参考。
