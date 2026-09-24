# 💰 money-finance-advice

> 面向普通大众的**财经 / 财务 / 会计 / 金融 / 税务**知识顾问 —— 把信息差摊平。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Skill](https://img.shields.io/badge/type-Agent%20Skill-blue.svg)](https://www.workbuddy.cn/docs/workbuddy/Overview)
[![Python](https://img.shields.io/badge/python-3.9%2B-green.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-86%20passed-brightgreen.svg)](#-测试)

一个 **Agent Skill**：装上之后，AI 就能用「官方权威信源 + 强制联网核实 + 结论先行」的方式，回答普通人日常生活中真会碰到的钱的问题 —— 而且**不编数字**。

---

## 它能回答什么

| 场景 | 典型问题 |
|---|---|
| 🧾 **生活理财避坑** | 信用卡分期到底多少年化？这个保险划算吗？"零利息"有什么猫腻？ |
| 💼 **工作财务问题** | 报销发票怎么开才合规？劳务合同和劳动合同差在哪？社保基数怎么定？ |
| 📈 **投资与理财判断** | 这家公司财报可信吗？IRR 怎么算？理财产品真假怎么查？ |
| 🏛️ **税务合规** | 专项附加扣除怎么填？年终奖选哪种计税？个税汇算怎么办？ |
| 🛡️ **社保公积金** | 断缴有什么后果？养老金怎么估？医保报销规则？ |

**不适用于**：专业审计意见、正式税务筹划方案、投资建议。

---

## 它和普通 AI 回答的区别

大多数人被金融信息差收割的方式是**不知道真实成本**。这个 skill 的解法是给数字：

```
用户：信用卡分期手续费 0.6%，划不划算？

❌ 普通回答：分期手续费年化 7.2%，需要综合考虑……
✅ 这个 skill：真实年化 13.03%，不是 7.2%。是 1 年期 LPR（3.0%）的 4.3 倍。
             以后听到"手续费 0.6%"先问 IRR。12 期 12000 元要多付 864 元。
```

三大差异：

1. **💻 带计算工具** —— 内置 IRR 计算器，不是"大概""也许"，是真算出来的数
2. **🌐 强制联网核实** —— 税率、扣除标准、社保年限这类数字**必须查当期官方口径**，且标注查询日期和文号
3. **📚 信源分级** —— A 级（部委官网/法规原文）才可定案，D 级（自媒体）只能当线索

---

## 安装

### 方式一：克隆整仓（推荐）

```bash
git clone https://github.com/DD12345679/money-finance-advice-skill.git
```

然后把 **skill 本体** 复制到 skills 目录（注意是 `skills/money-finance-advice/` 这一层，不是仓库根）：

**Windows（PowerShell / CMD）**

```powershell
# PowerShell
Copy-Item -Recurse -Force "money-finance-advice-skill\skills\money-finance-advice" "$env:USERPROFILE\.workbuddy\skills\"

# CMD
xcopy /E /I money-finance-advice-skill\skills\money-finance-advice "%USERPROFILE%\.workbuddy\skills\money-finance-advice"
```

**macOS / Linux**

```bash
mkdir -p ~/.workbuddy/skills
cp -r money-finance-advice-skill/skills/money-finance-advice ~/.workbuddy/skills/
```

### 方式二：只手动取 skill 本体

不想 clone 整个仓库的话，直接下载 `skills/money-finance-advice/` 这一个目录放进
`~/.workbuddy/skills/` 即可（`README.md`、`.github/` 等只是仓库门面，装的时候不需要）。

### 验证安装

```bash
ls ~/.workbuddy/skills/money-finance-advice/SKILL.md      # macOS / Linux
dir %USERPROFILE%\.workbuddy\skills\money-finance-advice\SKILL.md   # Windows
```

能列出文件就装好了。**重启会话**，问一句「这个分期划不划算」就会自动触发。

> 💡 Claude Code 用户同理：把 `money-finance-advice/` 放进 `~/.claude/skills/`。

---

## 目录结构

```
money-finance-advice-skill/
├── README.md                          # 你正在看的这个
├── LICENSE                            # MIT
├── CONTRIBUTING.md                    # 贡献指南
├── CHANGELOG.md                       # 变更日志
├── .gitignore
├── .gitattributes                     # 统一换行符
├── .github/
│   ├── workflows/tests.yml            # CI：3 OS × 2 Python 版本
│   └── ISSUE_TEMPLATE/                # 数据纠错 / 新增条目 模板
└── skills/
    └── money-finance-advice/          # ← skill 本体（装这个目录）
        ├── SKILL.md                   # 主入口：铁律 / 定位表 / 五条路径
        ├── references/
        │   ├── policy-index.md            # 官方政策查询入口 + 查询纪律
        │   ├── cost-calculation.md         # IRR 测算法 + 实测对照表
        │   ├── pitfall-catalog.md          # 16 条金融消费套路库
        │   └── financial-statement-reading.md  # 财报识读 + 本福特定律
        └── scripts/
            ├── irr_calc.py            # IRR 计算器 CLI
            └── test_irr_calc.py       # 行为测试（86 项断言）
```

---

## 🧮 内置计算器

`scripts/irr_calc.py` 是个独立 CLI，不依赖第三方库（纯标准库）。

### 信用卡分期真实年化

```bash
python irr_calc.py installment --principal 12000 --months 12 --monthly-fee-rate 0.006
```

```json
{
  "名义年化_显示": "7.20%",
  "真实年化_IRR单利_显示": "13.03%",
  "真实年化_IRR复利_显示": "13.84%",
  "倍数_单利除名义": 1.81
}
```

> **为什么有两个年化？** 单利口径（月 IRR × 12）与 LPR、存款利率可比，对外讲用这个；
> 复利口径反映真实资金成本。两者都对，别混用。

### 保险真实 IRR

```bash
python irr_calc.py insurance \
  --premiums 200000,200000,200000,200000,200000 \
  --cash-value 1184000 --year 10
```

```json
{
  "累计保费": 1000000.0,
  "账面盈亏_显示": "18.40%",
  "真实年化_IRR_显示": "2.13%"
}
```

> 时点约定：保费按保单年度**年初**缴纳，现金价值按第 N 年**年末**领取。

### 房贷月供与总利息

```bash
python irr_calc.py loan --principal 1000000 --months 360 --annual-rate 0.0385
python irr_calc.py loan --principal 1000000 --months 360 --annual-rate 0.0385 \
    --method equal_principal
```

### 直接算现金流 IRR

```bash
# 注意：以负号开头时必须用 = 连接
python irr_calc.py irr --cashflow=-12000,1072,1072,1072,1072,1072,1072,1072,1072,1072,1072,1072,1072
```

### 本福特定律检验（识别可疑数据）

```bash
python irr_calc.py benford --numbers 1234,2345,3456,...
python irr_calc.py benford --file amounts.txt
```

---

## 🧪 测试

**86 项断言，全部通过。**

```bash
cd skills/money-finance-advice/scripts
python test_irr_calc.py
```

覆盖：

- IRR 基础正确性（教科书案例 + 牛顿法/二分法交叉验证）
- 分期成本计算（含 5 档费率）
- 保险 IRR（含年度口径、退保边界、时点约定）
- 贷款计算（等额本息 / 等额本金）
- 本福特定律（真实分布 vs 人为摊平）
- 边界与异常输入（360/600 期长序列抗溢出）

---

## 设计原则

### 铁律四条

1. **政策类数据必须联网核实** —— 触发词：税率 / 扣除标准 / 缴费年限 / LPR / 新规…
2. **信源分级** —— A 级（部委官网、法规原文）→ B 级（地方口径）→ C 级（协会/权威媒体）→ D 级（自媒体，仅线索）
3. **结论先行，给数字，给动作**
4. **不越界** —— 不给投资建议、不出专业意见、不点名具体机构

### 回答结构

```
【结论】一句话 + 关键数字
【为什么】反差在哪
【关键数字】标来源与查询日期
【你可以做的】2-3 个可执行动作
【注意】地区/合同差异 + 免责
```

---

## ⚠️ 免责声明

本项目提供**通用财经知识普及与计算工具**，不构成：

- 投资建议或产品推荐
- 专业税务筹划方案、审计意见或法律意见

**所有政策、税率、利率数据请以官方最新公告为准**（本项目在涉及此类数据时均标注查询日期）。
具体决策请咨询持牌专业人士。

---

## License

[MIT](LICENSE)
