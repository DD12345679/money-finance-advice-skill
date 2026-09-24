#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
irr_calc.py 行为测试 —— 验证算得对，而不只是能跑

⚠️ 断言值来源：由独立二分法交叉验证后固化（2026-09-24）。
   若修改实现导致这些断言失败，先确认是修 bug 还是引入 bug。
"""

import sys
import os
import io
import random

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from irr_calc import (
    irr, annualize, installment_cost, insurance_irr,
    loan_amortization, benford_test, BENFORD_EXPECTED,
)

passed = 0
failed = []


def check(name, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed.append(name)
        print(f"  FAIL  {name}  {detail}")


def approx(a, b, tol=1e-4):
    return a is not None and abs(a - b) < tol


def pct(s):
    """把小数(0.1303)或字符串('13.03%')统一取成百分数(13.03)"""
    if isinstance(s, str):
        return float(s.rstrip("%").replace("+", ""))
    return float(s) * 100


print("=" * 70)
print("1. IRR 基础正确性")
print("=" * 70)

r = irr([1000, -1100])
check("借1000还1100 → IRR 10%", approx(r, 0.10), f"got {r}")

r = irr([1200] + [-100] * 12)
check("零利率分期 IRR ≈ 0", approx(r, 0.0, 1e-6), f"got {r}")
check("零利率年化 ≈ 0", approx(annualize(r, 12), 0.0, 1e-6), f"got {annualize(r, 12)}")

r = irr([1000, -500])
check("借1000只还500 → IRR = -50%", approx(r, -0.5, 0.01), f"got {r}")

r = irr([])
check("空现金流返回 None", r is None, f"got {r}")
r = irr([0, 0, 0])
check("全零现金流返回 None", r is None, f"got {r}")
r = irr([100, 200, 300])
check("只有正数返回 None", r is None, f"got {r}")

# 与独立二分法交叉验证（长周期、高期数）
def _npv(cfs, rate):
    return sum(c / (1 + rate) ** t for t, c in enumerate(cfs) if c)


def _bisect(cfs, lo=-0.9, hi=10.0, iters=300):
    f_lo = _npv(cfs, lo)
    for _ in range(iters):
        mid = (lo + hi) / 2
        f_mid = _npv(cfs, mid)
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


for cfs, tag in [
    ([12000] + [-1072] * 12, "分期12期"),
    ([-10, -10, -10, -10, -10, 0, 0, 0, 0, 65], "保险10年"),
    ([-20, -20, -20, -20, -20, 0, 0, 0, 0, 118.4], "保险10年大额"),
]:
    a, b = irr(cfs), _bisect(cfs)
    check(f"交叉验证 {tag}: Newton == 二分", a is not None and abs(a - b) < 1e-8,
          f"{a} vs {b}")

print()
print("=" * 70)
print("2. 分期成本 —— 核心：0.6% 月费率 → 单利 13.03% / 复利 13.84%")
print("=" * 70)

res = installment_cost(12000, 12, 0.006)
print(f"  名义 {res['名义年化_显示']} → 单利 {res['真实年化_IRR单利_显示']} / 复利 {res['真实年化_IRR复利_显示']}")

check("月手续费 = 72 元", approx(res["月手续费"], 72.0), res["月手续费"])
check("月还款额 = 1072 元", approx(res["月还款额"], 1072.0), res["月还款额"])
check("总手续费 = 864 元", approx(res["总手续费"], 864.0), res["总手续费"])
check("总还款额 = 12864 元", approx(res["总还款额"], 12864.0), res["总还款额"])
check("名义年化 = 7.20%", approx(res["名义年化_简单乘12"] * 100, 7.20, 0.01),
      res["名义年化_简单乘12"])

check("真实年化(单利) = 13.03%", approx(pct(res["真实年化_IRR单利"]), 13.03, 0.01),
      res["真实年化_IRR单利"])
check("真实年化(复利) = 13.84%", approx(pct(res["真实年化_IRR复利"]), 13.84, 0.01),
      res["真实年化_IRR复利"])
check("倍数 ≈ 1.81", approx(res["倍数_单利除名义"], 1.81, 0.01), res["倍数_单利除名义"])

# 单调性：费率越高，年化越高
rates = [0.005, 0.006, 0.0066, 0.0075, 0.008]
vals = [pct(installment_cost(12000, 12, r)["真实年化_IRR单利"]) for r in rates]
check("费率单调递增 → 年化单调递增", all(vals[i] < vals[i + 1] for i in range(len(vals) - 1)),
      str(vals))

# 已知档位
expect = {0.005: (10.90, 11.46), 0.0066: (14.31, 15.29), 0.0075: (16.22, 17.48),
          0.008: (17.27, 18.71)}
for rate, (exp_s, exp_c) in expect.items():
    r2 = installment_cost(12000, 12, rate)
    check(f"月费率 {rate*100:.2f}% → 单利 {exp_s}%",
          approx(pct(r2["真实年化_IRR单利"]), exp_s, 0.01), r2["真实年化_IRR单利"])
    check(f"月费率 {rate*100:.2f}% → 复利 {exp_c}%",
          approx(pct(r2["真实年化_IRR复利"]), exp_c, 0.01), r2["真实年化_IRR复利"])

check("倍率稳定在 1.80-1.83 区间",
      all(1.79 < installment_cost(12000, 12, r)["倍数_单利除名义"] < 1.84 for r in rates))

print()
print("=" * 70)
print("3. 保险 IRR（年度口径，不做月度换算）")
print("=" * 70)

cases = [
    ([100000] * 5, 650000, 10, 3.32, 150000, "10万x5, 10年65万"),
    ([200000] * 5, 1184000, 10, 2.13, 184000, "20万x5, 10年118.4万"),
    ([100000] * 10, 1180000, 10, 2.99, 180000, "10万x10, 10年118万"),
    ([100000] * 10, 1760000, 20, 3.68, 760000, "10万x10, 20年176万"),
    ([100000] * 10, 2630000, 30, 3.84, 1630000, "10万x10, 30年263万"),
]
for prem, cv, yr, exp_irr, exp_pnl, tag in cases:
    r = insurance_irr(prem, cv, yr)
    got_irr = pct(r["真实年化_IRR"])
    check(f"{tag} → IRR {exp_irr}%", approx(got_irr, exp_irr, 0.02),
          f"got {got_irr}%")
    check(f"{tag} → 账面盈亏 {exp_pnl}", approx(r["账面盈亏"], exp_pnl, 1),
          f"got {r['账面盈亏']}")

# 第1年退保巨亏（时点边界：年初交费、年末领取，不能相消）
r = insurance_irr([100000], 47000, 1)
check("第1年退保亏损 53%", approx(r["账面盈亏率"] * 100, -53.0, 0.01), r["账面盈亏率"])
check("第1年退保 IRR = -53%", approx(pct(r["真实年化_IRR"]), -53.0, 0.01),
      r["真实年化_IRR"])

# 现金价值 == 已交保费 → IRR 应约 0
r = insurance_irr([100000] * 5, 500000, 5)
check("现金价值=已交保费 → IRR ≈ 0", approx(pct(r["真实年化_IRR"]), 0.0, 0.01),
      r["真实年化_IRR"])

# 单调性：持有越久 IRR 越高（同一产品）
long_irrs = [
    pct(insurance_irr([100000] * 10, cv, yr)["真实年化_IRR"])
    for cv, yr in [(1180000, 10), (1760000, 20), (2630000, 30)]
]
check("持有期越长 IRR 越高", all(long_irrs[i] < long_irrs[i + 1] for i in range(2)),
      str(long_irrs))

print()
print("=" * 70)
print("4. 贷款计算")
print("=" * 70)

res = loan_amortization(1000000, 360, 0.0385, "equal_installment")
check("100万/30年/3.85% → 月供 4688.08", approx(res["月供"], 4688.08, 0.05), res["月供"])
check("等额本息总利息 ≈ 687709.64", approx(res["总利息"], 687709.64, 1.0), res["总利息"])
check("IRR单利口径回算 = 名义 3.85%", approx(pct(res["校验_IRR单利口径"]), 3.85, 0.01),
      res["校验_IRR单利口径"])
check("IRR复利口径 = 3.919%", approx(pct(res["校验_IRR复利口径"]), 3.919, 0.01),
      res["校验_IRR复利口径"])

res2 = loan_amortization(1000000, 360, 0.0385, "equal_principal")
check("等额本金总利息 ≈ 579104.17", approx(res2["总利息"], 579104.17, 1.0), res2["总利息"])
check("等额本金总利息 < 等额本息", res2["总利息"] < res["总利息"],
      f"{res2['总利息']} vs {res['总利息']}")
check("等额本金首月 ≈ 5986.11", approx(res2["首月还款"], 5986.11, 0.05), res2["首月还款"])
check("等额本金末月 ≈ 2786.69", approx(res2["末月还款"], 2786.69, 0.05), res2["末月还款"])
check("等额本金首月 > 末月", res2["首月还款"] > res2["末月还款"])

res3 = loan_amortization(12000, 12, 0.0, "equal_installment")
check("零利率 12000/12期 → 月供 1000", approx(res3["月供"], 1000.0), res3["月供"])
check("零利率总利息 = 0", approx(res3["总利息"], 0.0), res3["总利息"])

print()
print("=" * 70)
print("5. 本福特定律")
print("=" * 70)

check("理论值 1 = 30.103", BENFORD_EXPECTED[1] == 30.103)
check("理论值 9 = 4.576", BENFORD_EXPECTED[9] == 4.576)
total = sum(BENFORD_EXPECTED.values())
check("理论值合计 ≈ 100", approx(total, 100.0, 0.05), total)

random.seed(42)
real_data = [10 ** random.uniform(0, 6) for _ in range(20000)]
res = benford_test(real_data)
print(f"  对数均匀样本: 卡方={res['卡方统计量']}, {res['判定']}")
check("真实分布样本判定为符合", "符合" in res["判定"], res["判定"])
check("首位1占比接近30%", 29.0 < res["首位数字1占比"] < 31.5, res["首位数字1占比"])
check("首位9占比接近4.6%", 4.0 < res["首位数字9占比"] < 5.2, res["首位数字9占比"])

fake_data = []
for d in range(1, 10):
    for _ in range(1000):
        fake_data.append(d * 1000 + random.randint(0, 999))
res2 = benford_test(fake_data)
print(f"  均匀摊平样本: 卡方={res2['卡方统计量']}, {res2['判定']}")
check("人为摊平样本判定为显著偏离", "显著偏离" in res2["判定"], res2["判定"])
# 摊平占比 11.11% 时，卡方约 40（远超 0.01 临界值 20.090）
check("摊平样本卡方 > 20.09（0.01 临界值）", res2["卡方统计量"] > 20.09,
      res2["卡方统计量"])
check("摊平样本首位1占比 ≈ 11.1%",
      approx(res2["首位数字1占比"], 11.11, 0.1), res2["首位数字1占比"])

res3 = benford_test([])
check("空输入返回错误提示", "错误" in res3, res3)

res4 = benford_test([0, 0, 123, 234, 345])
check("跳过 0 值", res4["样本量"] == 3, res4["样本量"])

res5 = benford_test(["abc", None, 123.45, "678"])
check("非数字被跳过", res5["样本量"] == 2, res5.get("样本量"))

print()
print("=" * 70)
print("6. 边界与异常输入")
print("=" * 70)

for args, tag in [
    ((-100, 12, 0.006), "负本金"),
    ((12000, 0, 0.006), "0 期数"),
    ((12000, 12, -0.01), "负费率"),
]:
    try:
        installment_cost(*args)
        check(f"{tag} 应抛 ValueError", False, "未抛异常")
    except ValueError:
        check(f"{tag} 应抛 ValueError", True)

try:
    insurance_irr([], 100, 10)
    check("空保费列表应抛异常", False, "未抛异常")
except ValueError:
    check("空保费列表应抛异常", True)

try:
    insurance_irr([100], -50, 1)
    check("负现金价值应抛异常", False, "未抛异常")
except ValueError:
    check("负现金价值应抛异常", True)

# 领取年度早于缴费期数 → 逻辑矛盾，应报错而非静默返回
try:
    insurance_irr([100000] * 10, 234000, 3)
    check("领取年度早于缴费期数应抛异常", False, "未抛异常")
except ValueError:
    check("领取年度早于缴费期数应抛异常", True)

# 长序列不应溢出崩溃（360 期以上）
try:
    r = irr([1000000] + [-4688.08] * 360)
    check("360 期现金流不崩溃", r is not None, f"got {r}")
    check("360 期 IRR 单利 ≈ 3.85%", approx(r * 12, 0.0385, 0.001), f"got {r*12}")
except (OverflowError, ZeroDivisionError) as e:
    check("360 期现金流不崩溃", False, str(e))

# 更长序列：600 期
try:
    r = irr([1000000] + [-5000] * 600)
    check("600 期现金流不崩溃", True)
except (OverflowError, ZeroDivisionError) as e:
    check("600 期现金流不崩溃", False, str(e))

# 各年度 IRR 单调性（缴费期已结束的各年度，缴费 10 年）
irrs = []
for cv, yr in [(1184000, 10), (1440000, 15), (1760000, 20), (2630000, 30)]:
    irrs.append(pct(insurance_irr([100000] * 10, cv, yr)["真实年化_IRR"]))
check("10→30 年 IRR 总体上升", irrs[-1] > irrs[0], str(irrs))
check("第10年 IRR 3.05%", approx(irrs[0], 3.05, 0.02), irrs[0])
check("第30年 IRR 3.84%", approx(irrs[-1], 3.84, 0.02), irrs[-1])

# 缴费期内退保：应按实际已交保费 + 对应现金价值测算
r3 = insurance_irr([100000] * 3, 234000, 3)
check("交3年第3年退保 IRR = -11.92%", approx(pct(r3["真实年化_IRR"]), -11.92, 0.02),
      r3["真实年化_IRR"])
r5 = insurance_irr([100000] * 5, 480000, 5)
check("交5年第5年退保 IRR = -1.36%", approx(pct(r5["真实年化_IRR"]), -1.36, 0.02),
      r5["真实年化_IRR"])

# 接口约定：数值字段必须是数字，能被二次计算
i12 = installment_cost(12000, 12, 0.006)
check("分期 单利字段是数字", isinstance(i12["真实年化_IRR单利"], float),
      type(i12["真实年化_IRR单利"]).__name__)
check("分期 复利字段是数字", isinstance(i12["真实年化_IRR复利"], float),
      type(i12["真实年化_IRR复利"]).__name__)
check("分期 单利字段可二次计算", approx(i12["真实年化_IRR单利"] * 100, 13.03, 0.02),
      i12["真实年化_IRR单利"])
ins = insurance_irr([100000] * 10, 1180000, 10)
check("保险 IRR 字段是数字", isinstance(ins["真实年化_IRR"], float),
      type(ins["真实年化_IRR"]).__name__)
check("保险 盈亏率字段是数字", isinstance(ins["账面盈亏率"], float),
      type(ins["账面盈亏率"]).__name__)
check("保险 显示字段是字符串", isinstance(ins["真实年化_IRR_显示"], str),
      type(ins["真实年化_IRR_显示"]).__name__)
check("保险 显示字段格式正确", ins["真实年化_IRR_显示"].endswith("%"),
      ins["真实年化_IRR_显示"])

print()
print("=" * 70)
print(f"结果: {passed} 通过, {len(failed)} 失败")
if failed:
    print("失败项:")
    for f in failed:
        print("  -", f)
print("=" * 70)

sys.exit(1 if failed else 0)
