# NPC 子组织协作适配 · 目录

> 处理 ISSUE #2：子组织（subgroup）环境下，`@` 自动补全 / star / 互相 @ 协作失效的适配。

| 产物 | 说明 |
|---|---|
| `subgroup_@_adaptation.md` | 根因诊断 + 适配方案 + 工程实施 + 风险（主文档） |
| `resolver.subgroup.patched.py` | 修复后的 `local-agent/handle/resolver.py` 参考补丁（支持 org/subgroup/repo 三级路径） |
| `settings.subgroup.example.yml` | 子组织仓库内「架构·」团队 NPC 角色声明骨架（可选接入） |
| `selftest_subgroup.sh` | 解析器关键路径自检脚本（含三级/二级双用例） |

## 一句话
不是「引用少写 yutoujing」，而是**两级 @ 命名空间模型**装不下**子组织三级仓库路径**；
需按「目标仓库完整 slug + 权限」动态解析，并在平台侧把团队授权到子组织范围。
