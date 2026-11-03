# Trading Dashboard / 交易仪表盘

一个本地运行、无需安装第三方 Python 包的交易记录与组合仪表盘。支持股票、期权卖方、期权买方、日内交易、复盘、标的详情、组合曲线和中英文界面。

> 数据默认只保存在你的电脑上。项目没有登录系统，请不要直接暴露到公网。

## 功能

- 股票与期权交易记录、编辑、筛选和搜索
- Sell Put、Covered Call、Credit Spread、Iron Condor 等策略
- 已实现盈亏、持仓盈亏、胜率、ROC、年化收益与风险指标
- 组合概览、账户分类、持仓饼图和历史收益曲线
- 标的详情、财报标记、估值面板与周度复盘
- 中文 / English 界面
- CSV 导出与本地 SQLite 数据库
- Windows、macOS 和 Linux 本地运行

## 环境要求

- Python 3.10 或更高版本
- Git（仅克隆项目时需要）
- 无需 `pip install`

确认 Python 已安装：

```bash
python --version
```

macOS 或 Linux 上命令可能是 `python3`。

## 本地部署

### 1. 下载项目

```bash
git clone https://github.com/ZhengtianChu/stock_perf_tracker.git
cd stock_perf_tracker
```

也可以在 GitHub Release 页面下载 Source code 压缩包并解压。

### 2. 启动

Windows：

```powershell
python start.py
```

也可以双击 `start_windows.bat`。

macOS / Linux：

```bash
python3 start.py
```

macOS 也可以运行：

```bash
chmod +x start_mac.command
./start_mac.command
```

### 3. 打开页面

浏览器访问：

```text
http://127.0.0.1:8000
```

按 `Ctrl+C` 停止服务。

首次启动会自动创建空数据库 `data/trades.db`。后续所有交易和账户数据都保存在该文件中。

## 更新版本

在项目目录运行：

```bash
git pull
```

更新代码不会删除 `data/` 目录里的本地数据。更新前仍建议备份 `data/trades.db`。

## 数据与隐私

以下内容默认被 `.gitignore` 排除，不会提交到 GitHub：

- `data/` 下的数据库、账户快照、缓存、组合历史和本地密钥
- `.env` 与 `.env.*`
- 本地同步结果和个人对账脚本
- `bootstrap_trades.json`

最重要的备份文件是：

```text
data/trades.db
```

建议定期复制整个 `data/` 文件夹到安全位置。不要把数据库、券商导出文件或账户快照提交到公开仓库。

## 可选配置

常用环境变量：

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `OPTIONS_TRACKER_HOST` | `127.0.0.1` | 本地监听地址 |
| `OPTIONS_TRACKER_PORT` | `8000` | 端口 |
| `OPTIONS_TRACKER_RELOAD` | `1` | 开发时自动重载；设为 `0` 可关闭 |
| `OPTIONS_TRACKER_AUTO_REFRESH_PRICES` | `1` | 每日自动刷新价格 |
| `OPTIONS_TRACKER_PRICE_REFRESH_TIME` | `00:00` | 自动刷新时间 |
| `OPTIONS_TRACKER_LOCAL_TIMEZONE` | `America/Los_Angeles` | 本地时区 |
| `FINNHUB_API_KEY` | 空 | 可选行情数据 |
| `PLAID_CLIENT_ID` | 空 | 可选 Plaid 连接 |
| `PLAID_SECRET` | 空 | 可选 Plaid 连接 |
| `PLAID_ENV` | `sandbox` | Plaid 环境 |

密钥既可以通过环境变量设置，也可以保存在 `data/` 内的本地文件中，例如：

```text
data/.finnhub_api_key
data/.plaid_client_id
data/.plaid_secret
```

这些文件不会被 Git 跟踪。

### 可选组合历史

如果需要导入自定义组合基准和历史净值，可创建 `data/portfolio_config.json`：

```json
{
  "deposit_basis": 10000,
  "manual_equity_points": [
    {"date": "2025-01-01", "value": 10000},
    {"date": "2025-06-30", "value": 11250}
  ],
  "taxable_ledger_file": "external_taxable_ledger.json",
  "retirement_ledger_file": "external_retirement_ledger.json"
}
```

配置与账本文件都应放在 `data/` 中，因此不会上传到 GitHub。

## 后台启动（可选）

Windows 可使用：

```text
start_background.bat
```

项目也包含 Windows 启动任务的安装和卸载脚本。请先检查脚本内容，再根据自己的安装目录运行。

## 安全提示

- 默认只监听 `127.0.0.1`，适合个人本机使用。
- 应用没有用户认证，不建议把端口转发到公网。
- 若需要局域网或云端部署，请先增加身份验证、HTTPS、访问控制和安全备份。
- 提交代码前运行 `git status`，确认没有数据库、快照、导出文件或密钥被暂存。

## 测试

```bash
python -m unittest tests.test_app
```

## License

当前仓库未附加开源许可证。作者保留所有权利；如需公开分发或二次开发，请先联系仓库所有者。
