#!/usr/bin/env bash
# 自检：resolver 子组织适配关键路径（三级/二级双用例）
# 运行：bash docs/npc/selftest_subgroup.sh
set -e
PASS=0; FAIL=0
ok(){ echo "  ✅ $1"; PASS=$((PASS+1)); }
bad(){ echo "  ❌ $1"; FAIL=$((FAIL+1)); }

# ---- split_slug 语义化 ----
split3=$(echo "dongdongxiaozu/yutoujing/yutouzhuanyong" | awk -F/ '{n=NF; print $1, $1"/"$2, $3, 3}')
[ "$split3" = "dongdongxiaozu dongdongxiaozu/yutoujing yutouzhuanyong 3" ] && ok "三级 split_slug(root/group/repo)" || bad "三级 split_slug: got [$split3]"
split2=$(echo "dongdongxiaozu/dongjiagoushi" | awk -F/ '{print $1, $1, $2, 2}')
[ "$split2" = "dongdongxiaozu dongdongxiaozu dongjiagoushi 2" ] && ok "二级 split_slug(root/group=org, repo)" || bad "二级 split_slug: got [$split2]"

# ---- git remote 完整 slug 提取（剥离 host） ----
g3=$(echo "https://cnb.cool/dongdongxiaozu/yutoujing/yutouzhuanyong.git" | sed -E 's#^https?://[^/]+/##; s#^git@[^:]+:##; s#\.git$##; s#/$##')
[ "$g3" = "dongdongxiaozu/yutoujing/yutouzhuanyong" ] && ok "git remote 三级 slug 提取" || bad "git remote 三级: got [$g3]"
g2=$(echo "git@cnb.cool:dongdongxiaozu/dongjiagoushi.git" | sed -E 's#^https?://[^/]+/##; s#^git@[^:]+:##; s#\.git$##; s#/$##')
[ "$g2" = "dongdongxiaozu/dongjiagoushi" ] && ok "git remote 二级 slug 提取(不泄漏 host)" || bad "git remote 二级: got [$g2]"

# ---- 跨仓库判定 ----
cur="dongdongxiaozu/yutoujing/yutouzhuanyong"
tg_role="dongdongxiaozu/dongjiagoushi"
tg_same="dongdongxiaozu/yutoujing/yutouzhuanyong"
if [ "$cur" != "$tg_role" ]; then ok "子组织仓库 vs 根组织角色承载=跨仓库" ; else bad "跨仓库判定-角色"; fi
if [ "$cur" = "$tg_same" ]; then ok "同仓库判定=同仓" ; else bad "同仓库判定"; fi

echo ""
echo "结果: $PASS 通过 / $FAIL 失败"
[ "$FAIL" -eq 0 ] || exit 1
