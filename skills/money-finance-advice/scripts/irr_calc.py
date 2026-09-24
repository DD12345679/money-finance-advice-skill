#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财经成本测算工具 —— IRR / 分期成本 / 保险收益 / 贷款利息

用法：
  # 信用卡分期真实年化
  python irr_calc.py installment --principal 12000 --months 12 --monthly-fee-rate 0.006

  # 保险产品真实 IRR
  python irr_calc.py insurance --premiums 100000,100000,100000,100000,100000 --cash-value 650000 --year 10

  # 房贷/等额本息月供与总利息
  python irr_calc.py loan --principal 1000000 --months 360 --annual-rate 0.0385

  # 从现金流数组直接算 IRR
  #   注意：以负号开头时用 = 连接，否则 argparse 会当成长选项
  python irr_calc.py irr --cashflow=-12000,1072,1072,1072,1072,1072,1072,1072,1072,1072,1072,1072,1072

  # 本福特定律首位数字检验（从文件或逗号分隔数字）
  python irr_calc.py benford --numbers 1234,2345,3456,... 
  python irr_calc.py benford --file amounts.txt
"""

import argparse
import json
import math
import sys


# ---------------------------------------------------------------- IRR 核心

def irr(cashflows, guess=0.1, tol=1e-10, max_iter=300):
    """
    求 IRR。cashflows 为按期的现金流序列，投入为负、收回为正。
    cashflows[0] 为第 0 期（当前时点）的现金流，返回期间收益率（小数）。
    """
    if not cashflows or all(c == 0 for c in cashflows):
        return None
    if not any(c > 0 for c in cashflows) or not any(c < 0 for c in cashflows):
        return None

    rate = guess
    for _ in range(max_iter):
        npv = _npv(cashflows, rate)
        if abs(npv) < tol:
            return rate
        if not math.isfinite(npv):
            break
        base = 1.0 + rate
        if base <= 0:
            break
        d_npv = 0.0
        for t, cf in enumerate(cashflows):
            if cf == 0 or t == 0:
                continue
            try:
                d_npv -= t * cf / (base ** (t + 1))
            except (OverflowError, ZeroDivisionError):
                d_npv = float("nan")
                break
        if d_npv == 0 or not math.isfinite(d_npv):
            break
        new_rate = rate - npv / d_npv
        if new_rate <= -0.999999:
            new_rate = (rate - 0.999999) / 2
        if not math.isfinite(new_rate):
            break
        if abs(new_rate - rate) < tol:
            return new_rate
        rate = new_rate

    return _irr_bisect(cashflows)


def _irr_bisect(cashflows, lo=-0.9999, hi=10.0, tol=1e-12, max_iter=400):
    """二分法兜底。下界取 -0.9999 保证 (1+r) 不为 0。"""
    f_lo = _npv(cashflows, lo)
    f_hi = _npv(cashflows, hi)

    if not math.isfinite(f_lo) or not math.isfinite(f_hi):
        lo, f_lo = -0.5, _npv(cashflows, -0.5)
    if f_lo * f_hi > 0:
        # 尝试扩大上界
        for hi_try in (100.0, 1e4, 1e6):
            f_hi_try = _npv(cashflows, hi_try)
            if math.isfinite(f_hi_try) and f_lo * f_hi_try <= 0:
                hi, f_hi = hi_try, f_hi_try
                break
        else:
            return None

    for _ in range(max_iter):
        mid = (lo + hi) / 2
        f_mid = _npv(cashflows, mid)
        if abs(f_mid) < tol or (hi - lo) < tol:
            return mid
        if f_lo * f_mid <= 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


_MAX_RATE = 1e6


def annualize(period_rate, periods_per_year=12):
    """把期间收益率换算成年化。"""
    if period_rate is None:
        return None
    return (1.0 + period_rate) ** periods_per_year - 1.0


def _npv(cashflows, rate):
    """净现值。防御 (1+rate) 溢出与除零。"""
    base = 1.0 + rate
    if base <= 0:
        return float("inf")
    total = 0.0
    for t, cf in enumerate(cashflows):
        if cf == 0:
            continue
        try:
            total += cf / (base ** t)
        except (OverflowError, ZeroDivisionError):
            return float("inf") if cf < 0 else float("-inf")
    return total


# ---------------------------------------------------------------- 分期

def installment_cost(principal, months, monthly_fee_rate):
    """
    信用卡/消费分期成本。
    手续费按初始本金计算（行业惯例），本金分期等额归还。

    现金流时点：t=0 是放款时点（+本金），此后每期末还款（-月供）。

    ⚠️ 两个年化口径都要给，因为用途不同：
      - 单利年化 = 月IRR × 12  → 与 LPR / 存款利率（单利口径）可比
      - 复利年化 = (1+月IRR)^12 - 1 → 反映真实资金成本
    """
    if principal <= 0 or months <= 0:
        raise ValueError("本金与期数必须为正数")
    if monthly_fee_rate < 0:
        raise ValueError("费率不能为负")

    monthly_fee = principal * monthly_fee_rate
    monthly_principal = principal / months
    monthly_payment = monthly_principal + monthly_fee

    cashflows = [principal] + [-monthly_payment] * months
    period_irr = irr(cashflows)

    if period_irr is None:
        simple_annual = compound_annual = None
    else:
        simple_annual = period_irr * 12
        compound_annual = annualize(period_irr, 12)

    total_fee = monthly_fee * months
    total_payment = principal + total_fee
    naive_annual = monthly_fee_rate * 12

    # 数值字段一律返回 float（可继续参与计算）；展示用字符串另以 *_显示 给出
    return {
        "本金": round(principal, 2),
        "期数": months,
        "月费率": monthly_fee_rate,
        "月费率_显示": f"{monthly_fee_rate * 100:.3f}%",
        "月手续费": round(monthly_fee, 2),
        "月还款额": round(monthly_payment, 2),
        "总手续费": round(total_fee, 2),
        "总还款额": round(total_payment, 2),
        "名义年化_简单乘12": naive_annual,
        "名义年化_显示": f"{naive_annual * 100:.2f}%",
        "真实年化_IRR单利": simple_annual,
        "真实年化_IRR复利": compound_annual,
        "真实年化_IRR单利_显示": f"{simple_annual * 100:.2f}%" if simple_annual is not None else "无法计算",
        "真实年化_IRR复利_显示": f"{compound_annual * 100:.2f}%" if compound_annual is not None else "无法计算",
        "倍数_单利除名义": round(simple_annual / naive_annual, 2)
        if (simple_annual is not None and naive_annual) else None,
    }


# ---------------------------------------------------------------- 保险

def insurance_irr(premiums, cash_value, year):
    """
    保险产品真实 IRR。

    现金流时点约定（对应合同口径）：
      - 保费在每年**年初**缴纳 → 第 k 年保费落在 t = k-1  (k=1..len(premiums))
      - 现金价值在**第 year 年末**领取 → 落在 t = year

    这样「第 1 年交费、第 1 年末退保」就是 [-P, +CV]，不会被相消掉。

    premiums: 各年保费（长度 = 缴费年数）
    cash_value: 第 year 年末的现金价值
    year: 领取的保单年度
    返回**年度** IRR。
    """
    if not premiums or year <= 0:
        raise ValueError("参数不合法")
    if any(p < 0 for p in premiums):
        raise ValueError("保费不能为负")
    if cash_value < 0:
        raise ValueError("现金价值不能为负")
    if year < len(premiums):
        raise ValueError(
            f"领取年度({year})早于缴费期数({len(premiums)})，"
            "请确认：未缴完保费时退保，应按实际已交保费测算"
        )

    # 时长 = max(缴费年数, 领取年度) + 1，下标 0..N
    n = max(len(premiums), year) + 1
    cashflows = [0.0] * n

    for k, p in enumerate(premiums, start=1):
        cashflows[k - 1] -= p          # 第 k 年年初交费
    cashflows[year] += cash_value      # 第 year 年年末领取

    period_irr = irr(cashflows)
    total_premium = sum(premiums)

    return {
        "累计保费": round(total_premium, 2),
        "第几年": year,
        "当年现金价值": round(cash_value, 2),
        "账面盈亏": round(cash_value - total_premium, 2),
        "账面盈亏率": (cash_value / total_premium - 1) if total_premium else None,
        "账面盈亏率_显示": f"{(cash_value / total_premium - 1) * 100:.2f}%" if total_premium else None,
        "真实年化_IRR": period_irr,
        "真实年化_IRR_显示": f"{period_irr * 100:.2f}%" if period_irr is not None else "无法计算",
    }


# ---------------------------------------------------------------- 贷款

def loan_amortization(principal, months, annual_rate, method="equal_installment"):
    """
    method: equal_installment=等额本息, equal_principal=等额本金
    """
    if principal <= 0 or months <= 0:
        raise ValueError("本金与期数必须为正数")

    monthly_rate = annual_rate / 12

    if method == "equal_installment":
        if monthly_rate == 0:
            monthly_payment = principal / months
        else:
            factor = (1 + monthly_rate) ** months
            monthly_payment = principal * monthly_rate * factor / (factor - 1)
        total_payment = monthly_payment * months
        cashflows = [principal] + [-monthly_payment] * months
        period_irr = irr(cashflows)
        simple_annual = period_irr * 12 if period_irr is not None else None
        compound_annual = annualize(period_irr, 12) if period_irr is not None else None
        return {
            "方式": "等额本息",
            "本金": round(principal, 2),
            "期数": months,
            "名义年利率": f"{annual_rate * 100:.3f}%",
            "月供": round(monthly_payment, 2),
            "总还款额": round(total_payment, 2),
            "总利息": round(total_payment - principal, 2),
            "校验_IRR单利口径": f"{simple_annual * 100:.3f}%" if simple_annual is not None else "无法计算",
            "校验_IRR复利口径": f"{compound_annual * 100:.3f}%" if compound_annual is not None else "无法计算",
        }
    else:
        monthly_principal = principal / months
        total_interest = 0.0
        balance = principal
        first_payment = monthly_principal + balance * monthly_rate
        last_payment = monthly_principal + monthly_principal * monthly_rate
        for _ in range(months):
            total_interest += balance * monthly_rate
            balance -= monthly_principal
        total_payment = principal + total_interest
        cashflows = [principal]
        b = principal
        for i in range(months):
            pay = monthly_principal + b * monthly_rate
            cashflows.append(-pay)
            b -= monthly_principal
        period_irr = irr(cashflows)
        simple_annual = period_irr * 12 if period_irr is not None else None
        compound_annual = annualize(period_irr, 12) if period_irr is not None else None
        return {
            "方式": "等额本金",
            "本金": round(principal, 2),
            "期数": months,
            "名义年利率": f"{annual_rate * 100:.3f}%",
            "首月还款": round(first_payment, 2),
            "末月还款": round(last_payment, 2),
            "总还款额": round(total_payment, 2),
            "总利息": round(total_interest, 2),
            "校验_IRR单利口径": f"{simple_annual * 100:.3f}%" if simple_annual is not None else "无法计算",
            "校验_IRR复利口径": f"{compound_annual * 100:.3f}%" if compound_annual is not None else "无法计算",
        }


# ---------------------------------------------------------------- 本福特

BENFORD_EXPECTED = {
    1: 30.103, 2: 17.609, 3: 12.494, 4: 9.691, 5: 7.918,
    6: 6.695, 7: 5.799, 8: 5.115, 9: 4.576,
}


def _first_digit(v):
    """
    取首位有效数字（跳过前导 0）。
    用 Decimal 规范化，避免 str() 的科学计数法与 lstrip 字符集陷阱。
    """
    try:
        from decimal import Decimal, InvalidOperation
        d = abs(Decimal(str(v)))
    except (InvalidOperation, ValueError, TypeError):
        return None

    if d == 0:
        return None

    # 归一化到 [1, 10) 区间
    while d >= 10:
        d /= 10
    while d < 1:
        d *= 10

    first = int(d)
    return first if 1 <= first <= 9 else None


def benford_test(numbers):
    """首位数字分布检验。numbers 为数值列表（含字符串数字）。"""
    counts = {d: 0 for d in range(1, 10)}
    valid = 0
    skipped = 0

    for n in numbers:
        if isinstance(n, str):
            n = n.strip().replace(",", "")
            if not n:
                skipped += 1
                continue
        try:
            v = float(n)
        except (TypeError, ValueError):
            skipped += 1
            continue

        first = _first_digit(v)
        if first is None:
            skipped += 1
            continue

        counts[first] += 1
        valid += 1

    if valid == 0:
        return {"错误": "没有有效的正数", "跳过": skipped}

    rows = []
    chi_square = 0.0
    for d in range(1, 10):
        observed = counts[d] / valid * 100
        expected = BENFORD_EXPECTED[d]
        chi_square += (observed - expected) ** 2 / expected
        rows.append({
            "首位数字": d,
            "实际占比": round(observed, 2),
            "理论占比": expected,
            "偏离pp": round(observed - expected, 2),
            "次数": counts[d],
        })

    # 自由度 8，卡方临界值：0.05 水平 15.507；0.01 水平 20.090
    if chi_square < 15.507:
        verdict = "符合本福特分布，未见明显异常"
    elif chi_square < 20.090:
        verdict = "轻度偏离（0.05 水平显著），建议抽查"
    else:
        verdict = "显著偏离（0.01 水平显著），存在人为干预的可能"

    return {
        "样本量": valid,
        "跳过": skipped,
        "卡方统计量": round(chi_square, 3),
        "判定": verdict,
        "首位数字1占比": round(counts[1] / valid * 100, 2),
        "首位数字1理论值": BENFORD_EXPECTED[1],
        "首位数字9占比": round(counts[9] / valid * 100, 2),
        "首位数字9理论值": BENFORD_EXPECTED[9],
        "分布明细": rows,
    }


# ---------------------------------------------------------------- CLI

def main():
    parser = argparse.ArgumentParser(description="财经成本测算工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("installment", help="分期真实年化")
    p1.add_argument("--principal", type=float, required=True)
    p1.add_argument("--months", type=int, required=True)
    p1.add_argument("--monthly-fee-rate", type=float, required=True,
                    help="月费率，如 0.006 表示 0.6%%")

    p2 = sub.add_parser("insurance", help="保险真实 IRR")
    p2.add_argument("--premiums", type=str, required=True,
                    help="各年保费，逗号分隔")
    p2.add_argument("--cash-value", type=float, required=True)
    p2.add_argument("--year", type=int, required=True)

    p3 = sub.add_parser("loan", help="贷款月供与利息")
    p3.add_argument("--principal", type=float, required=True)
    p3.add_argument("--months", type=int, required=True)
    p3.add_argument("--annual-rate", type=float, required=True)
    p3.add_argument("--method", choices=["equal_installment", "equal_principal"],
                    default="equal_installment")

    p4 = sub.add_parser("irr", help="从现金流直接算 IRR")
    p4.add_argument("--cashflow", type=str, required=True,
                    help="逗号分隔，投入为负。以负号开头时用 = 连接，"
                         "例：--cashflow=-12000,1072,1072")

    p5 = sub.add_parser("benford", help="本福特定律检验")
    p5.add_argument("--numbers", type=str)
    p5.add_argument("--file", type=str)

    args = parser.parse_args()

    try:
        result = _dispatch(args)
    except ValueError as e:
        print(f"输入有问题：{e}", file=sys.stderr)
        sys.exit(2)
    except FileNotFoundError as e:
        print(f"找不到文件：{e}", file=sys.stderr)
        sys.exit(2)

    print(json.dumps(_round_floats(result), ensure_ascii=False, indent=2))


def _dispatch(args):
    if args.cmd == "installment":
        return installment_cost(args.principal, args.months, args.monthly_fee_rate)
    if args.cmd == "insurance":
        premiums = [float(x) for x in args.premiums.split(",") if x.strip()]
        return insurance_irr(premiums, args.cash_value, args.year)
    if args.cmd == "loan":
        return loan_amortization(args.principal, args.months, args.annual_rate, args.method)
    if args.cmd == "irr":
        cfs = [float(x) for x in args.cashflow.split(",") if x.strip()]
        r = irr(cfs)
        return {
            "现金流": cfs,
            "期间IRR": r,
            "期间IRR_显示": f"{r * 100:.4f}%" if r is not None else "无法计算",
            "年化IRR_按月": annualize(r, 12) if r is not None else None,
            "年化IRR_按月_显示": f"{annualize(r, 12) * 100:.4f}%" if r is not None else "无法计算",
        }
    if args.cmd == "benford":
        nums = []
        if args.file:
            with open(args.file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip().replace(",", "")
                    if line:
                        try:
                            nums.append(float(line))
                        except ValueError:
                            continue
        elif args.numbers:
            nums = [float(x) for x in args.numbers.split(",") if x.strip()]
        else:
            print("需要 --numbers 或 --file", file=sys.stderr)
            sys.exit(1)
        return benford_test(nums)
    raise ValueError(f"未知子命令 {args.cmd}")


def _round_floats(obj, nd=6):
    """递归把 float 收敛到 nd 位，避免 JSON 里出现 0.130299999999 这类脏值。"""
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, dict):
        return {k: _round_floats(v, nd) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round_floats(v, nd) for v in obj]
    return obj


if __name__ == "__main__":
    main()
