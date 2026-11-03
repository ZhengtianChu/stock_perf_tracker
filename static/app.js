document.addEventListener("DOMContentLoaded", () => {
  const currentUrl = new URL(window.location.href);
  const languagePicker = document.querySelector(".language-picker");
  const savedLanguage = localStorage.getItem("optionLedgerLanguage") || "en";
  const urlLanguage = currentUrl.searchParams.get("lang");
  if (!urlLanguage && savedLanguage !== "en") {
    currentUrl.searchParams.set("lang", savedLanguage);
    window.location.replace(`${currentUrl.pathname}${currentUrl.search}`);
    return;
  }
  const activeLanguage = urlLanguage === "zh" ? "zh" : "en";
  localStorage.setItem("optionLedgerLanguage", activeLanguage);
  const cp1252Bytes = new Map([
    [0x20ac, 0x80], [0x201a, 0x82], [0x0192, 0x83], [0x201e, 0x84],
    [0x2026, 0x85], [0x2020, 0x86], [0x2021, 0x87], [0x02c6, 0x88],
    [0x2030, 0x89], [0x0160, 0x8a], [0x2039, 0x8b], [0x0152, 0x8c],
    [0x017d, 0x8e], [0x2018, 0x91], [0x2019, 0x92], [0x201c, 0x93],
    [0x201d, 0x94], [0x2022, 0x95], [0x2013, 0x96], [0x2014, 0x97],
    [0x02dc, 0x98], [0x2122, 0x99], [0x0161, 0x9a], [0x203a, 0x9b],
    [0x0153, 0x9c], [0x017e, 0x9e], [0x0178, 0x9f]
  ]);
  const decodeMojibakeOnce = (value) => {
    if (typeof value !== "string" || !/[\u00c2-\u00f4\u0152\u0153\u0160\u0161\u0178\u017d\u017e\u0192\u2013-\u203a\u2122]/.test(value)) {
      return value;
    }
    const bytes = [];
    for (const character of value) {
      const codePoint = character.codePointAt(0);
      if (codePoint <= 0xff) bytes.push(codePoint);
      else if (cp1252Bytes.has(codePoint)) bytes.push(cp1252Bytes.get(codePoint));
      else return value;
    }
    try {
      return new TextDecoder("utf-8", { fatal: true }).decode(new Uint8Array(bytes));
    } catch (_error) {
      return value;
    }
  };
  const repairMojibake = (value) => {
    let repaired = value;
    for (let pass = 0; pass < 2; pass += 1) {
      const next = decodeMojibakeOnce(repaired);
      if (next === repaired) break;
      repaired = next;
    }
    return repaired;
  };
  const zhText = {
    "Top 5 Rankings": "\u524d\u4e94\u699c\u5355",
    "Current filters": "\u5f53\u524d\u7b5b\u9009\u8303\u56f4",
    "Trade Count": "\u4ea4\u6613\u6b21\u6570",
    "Win Rate (10+ trades)": "\u80dc\u7387\uff08\u81f3\u5c11 10 \u7b14\uff09",
    "Top Sectors": "\u677f\u5757\u524d\u4e94",
    "This Week Earnings": "\u672c\u5468\u8d22\u62a5",
    "Loading this week's reports...": "\u6b63\u5728\u52a0\u8f7d\u672c\u5468\u8d22\u62a5...",
    "Best Trades": "\u5355\u7b14\u6536\u76ca\u524d\u4e94",
    "Worst Trades": "\u5355\u7b14\u4e8f\u635f\u524d\u4e94",
    "Sectors by Trade Count": "\u677f\u5757\u4ea4\u6613\u6570\u524d\u4e94",
    "Best Earnings": "\u8d22\u62a5\u4ea4\u6613\u6536\u76ca\u524d\u4e94",
    "Worst Earnings": "\u8d22\u62a5\u4ea4\u6613\u4e8f\u635f\u524d\u4e94",
    "Dandan": "\u86cb\u86cb",
    "Pet Dandan": "\u6478\u6478\u86cb\u86cb",
    "Trade reminder": "\u4ea4\u6613\u63d0\u9192",
    "Let Dandan nap": "\u8ba9\u86cb\u86cb\u4f11\u606f",
    "Wake Dandan": "\u53eb\u9192\u86cb\u86cb",
    "Back to corner": "\u56de\u5230\u89d2\u843d",
    "Hide": "\u9690\u85cf",
    "Dashboard": "仪表盘",
    "Analytics": "分析",
    "Tools": "工具",
    "Review": "复盘",
    "Options Calculator": "期权计算器",
    "Earnings Calendar": "财报日历",
    "Important Macro": "重要宏观事件",
    "No important macro events this week.": "本周暂无重要宏观事件。",
    "high-impact events": "个高影响事件",
    "Watchlist Heatmap": "自选热力图",
    "Portfolio Stress Test": "组合压力测试",
    "Trade Journal Review": "交易复盘",
    "Brokerage / Robinhood": "券商 / Robinhood",
    "Account snapshot": "账户快照",
    "Brokerage": "券商",
    "Portfolio": "组合",
    "Portfolio overview": "组合概览",
    "portfolio overview": "组合概览",
    "Robinhood Account": "Robinhood 账户",
    "Portfolio Overview": "组合概览",
    "Account Details": "账户详情",
    "display-only profile": "仅展示资料",
    "local snapshot": "本地快照",
    "Status": "状态",
    "Account": "账户",
    "Portfolio value": "组合市值",
    "Buying power": "购买力",
    "Last sync": "最近同步",
    "Connected": "已连接",
    "Not linked": "未连接",
    "Stocks value": "股票市值",
    "Options value": "期权市值",
    "Cash value": "现金",
    "Account last 4": "账号后四位",
    "Account type": "账户类型",
    "Trading type": "交易类型",
    "Sync from Robinhood": "从 Robinhood 同步",
    "Sync Robinhood": "同步 Robinhood",
    "Sync all": "全部同步",
    "READY": "就绪",
    "Ready": "就绪",
    "Connect accounts": "连接账户",
    "Connect Plaid": "连接 Plaid",
    "Plaid items": "Plaid 项目",
    "Investments": "投资账户",
    "Retirement": "退休账户",
    "Banking": "银行账户",
    "Crypto": "加密资产",
    "Stocks": "股票",
    "Options": "期权",
    "Cash": "现金",
    "Position mix": "持仓结构",
    "Save snapshot": "保存快照",
    "SPY and ticker shock scenarios": "SPY 与个股冲击情景",
    "Rules from closed trades": "从已平仓交易提炼规则",
    "Insider / 13F / Analyst Changes": "内部人 / 13F / 分析师变化",
    "Finnhub supplemental data": "Finnhub 辅助数据",
    "Analyst Snapshot": "分析师概览",
    "Analyst recommendations": "分析师评级",
    "Price Targets": "目标价",
    "Insider Transactions": "内部人交易",
    "Institutional / 13F": "机构 / 13F",
    "Portfolio Stress Test": "组合压力测试",
    "Risk tool": "风险工具",
    "Scenario": "情景",
    "estimated live-position impact": "实时持仓影响估算",
    "Estimated impact": "预计影响",
    "Stock impact": "股票影响",
    "Options impact": "期权影响",
    "Worst ticker": "最差标的",
    "Position Impact": "持仓影响",
    "quotes refresh through Yahoo cache": "报价通过 Yahoo 缓存刷新",
    "Trade Journal Review": "交易复盘",
    "Review tool": "复盘工具",
    "Weekly review": "每周复盘",
    "Portfolio change": "组合变化",
    "Realized P&L": "已实现盈亏",
    "Profit factor": "盈亏比",
    "Trade pace": "交易频率",
    "Take a breath:": "先停一下：",
    "this was a difficult risk event, not a verdict on your ability. The priority is not to win the money back immediately; it is to make risk controllable again.": "这是一次艰难的风险事件，不是对你能力的判决。现在最重要的不是立刻把钱赚回来，而是让风险重新变得可控。",
    "What happened this week": "本周发生了什么",
    "Rules for next week": "下周执行规则",
    "Strategy attribution": "策略归因",
    "Largest losses": "最大亏损",
    "There is not enough activity for a weekly diagnosis yet.": "本周尚无足够数据形成归因。",
    "No closed trades this week.": "本周没有已平仓交易。",
    "No losing closes this week.": "本周没有亏损平仓。",
    "Pause new outright Long Calls for the first two sessions next week. Manage existing positions and write the entry thesis, invalidation condition, and exit price for each one.": "下周前两个交易日暂停新增纯方向 Long Call。只管理现有仓位，并逐笔写清入场逻辑、失效条件和退出价格。",
    "Allow at most three new directional ideas per day. Treat highly correlated technology names or the same theme as one risk basket.": "每天最多允许三个新的方向性想法。高相关科技标的或同一主题应按一个风险篮子计算。",
    "Review the three largest losses before restoring position size. The immediate goal is not to win it back; it is to stop extending the drawdown.": "先复盘最大的三笔亏损，再恢复仓位规模。眼前目标不是立刻赚回来，而是停止扩大回撤。",
    "Portfolio change equals the account snapshot change less net cash flow. It includes realized P&L, unrealized marks, and quote changes, so it will not exactly match closed-trade P&L. Annualized return magnifies historical results and can fall sharply after a short losing period; it is not the account's actual weekly loss percentage.": "组合变化等于账户快照变化减去净现金流。它包含已实现盈亏、未实现浮动和报价变化，因此不会与平仓盈亏完全一致。年化收益率会放大历史结果，短期亏损可能使它快速下降，但它不是账户本周的实际亏损百分比。",
    "Closed trades": "已平仓交易",
    "Average ROC": "平均 ROC",
    "Avg Trade P/L %": "平均每单盈亏%",
    "Rules to Keep / Avoid": "保留 / 避免规则",
    "auto-generated from closed trades": "根据已平仓交易自动生成",
    "By Strategy": "按策略",
    "By Ticker": "按标的",
    "By DTE": "按 DTE",
    "By Spread Width": "按价差宽度",
    "Live movers and support zones": "实时涨跌与支撑压力",
    "High-impact macro events": "高影响宏观事件",
    "Tracks red/high-impact US events such as CPI, PPI, FOMC, nonfarm payrolls, unemployment, GDP, PCE, ISM and jobless claims. Data requires FINNHUB_API_KEY.": "追踪美国红色/高影响事件，例如 CPI、PPI、FOMC、非农、失业率、GDP、PCE、ISM 和初请失业金。数据需要 FINNHUB_API_KEY。",
    "No macro events found.": "暂无宏观事件。",
    "No high-impact US macro events found in this range.": "该区间暂无美国高影响宏观事件。",
    "Economic calendar requires Finnhub premium access.": "经济日历需要 Finnhub 付费权限。",
    "Impact": "影响",
    "Event": "事件",
    "Country": "国家",
    "Forecast": "预期",
    "Previous": "前值",
    "High": "高",
    "Core": "核心",
    "Holding": "持仓",
    "Open": "未平仓",
    "Frequent": "常交易",
    "Earnings": "财报",
    "Top 5 Symbols": "盈利前五",
    "Ranked by Total P&L": "按总收益排名",
    "Next Week Earnings": "下周财报",
    "Loading next week's reports...": "正在加载下周财报...",
    "Position": "持仓",
    "Sector": "板块",
    "20D": "20日",
    "Large-cap Earnings": "大市值财报",
    "Large caps": "大市值公司",
    "My symbols": "我的标的",
    "Today": "今天",
    "This week": "本周",
    "Before Open": "盘前",
    "After Close": "盘后",
    "During Market": "盘中",
    "No reports": "暂无财报",
    "Market cap": "市值",
    "EPS est.": "预期 EPS",
    "EPS actual": "实际 EPS",
    "Revenue est.": "预期营收",
    "Quarter": "季度",
    "Time": "时间",
    "BMO": "盘前",
    "AMC": "盘后",
    "During market": "盘中",
    "TBD": "待定",
    "Tracked": "已关注",
    "No earnings found.": "暂无财报数据。",
    "No large-cap earnings found in this range.": "该区间暂无大市值公司财报。",
    "Set FINNHUB_API_KEY to enable earnings calendar.": "设置 FINNHUB_API_KEY 后启用财报日历。",
    "Set FINNHUB_API_KEY to enable Finnhub data.": "设置 FINNHUB_API_KEY 后启用 Finnhub 数据。",
    "Market cap filter: $10.0B+ companies. Combines Finnhub calendar with targeted symbol lookups for tracked and high-interest tickers.": "市值筛选：100亿美元以上公司。结合 Finnhub 总日历和重点标的单独补查。",
    "Combines Finnhub calendar with targeted symbol lookups for tracked and high-interest tickers. The fallback list includes DELL, PANW, MDB and other large-cap names so major reports are less likely to be missed.": "结合 Finnhub 总日历和重点标的单独补查。默认补查包含 DELL、PANW、MDB 和其他大市值公司，减少重要财报漏掉的概率。",
    "Long Call": "买入 Call",
    "Long Put": "买入 Put",
    "Black-Scholes estimate": "Black-Scholes 估算",
    "Implied volatility": "隐含波动率",
    "Range": "价格范围",
    "Contract Value": "合约价值",
    "Profit / Loss $": "盈亏 $",
    "Profit / Loss %": "盈亏 %",
    "Stock": "股价",
    "Infinite": "无限",
    "Black-Scholes": "Black-Scholes",
    "theoretical value and Greeks": "理论价格与 Greeks",
    "Strategy": "策略",
    "Single Option": "单腿期权",
    "Put Credit Spread": "看跌信用价差",
    "Call Credit Spread": "看涨信用价差",
    "Iron Condor": "铁鹰策略",
    "Option type": "期权类型",
    "Put": "看跌",
    "Call": "看涨",
    "Stock price": "股价",
    "Strike": "行权价",
    "DTE": "到期天数",
    "Expiration": "到期日",
    "IV %": "隐波 %",
    "Risk-free %": "无风险利率 %",
    "Dividend %": "股息率 %",
    "Short put strike": "卖出 Put 行权价",
    "Long put strike": "买入 Put 行权价",
    "Short put IV %": "卖出 Put IV %",
    "Long put IV %": "买入 Put IV %",
    "Short put IV": "卖出 Put IV",
    "Long put IV": "买入 Put IV",
    "Long strike": "买入行权价",
    "Short leg IV %": "卖出腿 IV %",
    "Long leg IV %": "买入腿 IV %",
    "Short leg IV": "卖出腿 IV",
    "Long leg IV": "买入腿 IV",
    "Net credit": "净权利金",
    "Contracts": "合约数",
    "Calculate": "计算",
    "Result": "结果",
    "per share unless noted": "除特别说明外均为每股",
    "Theoretical price": "理论价格",
    "Intrinsic": "内在价值",
    "Extrinsic": "时间价值",
    "Theta / day": "Theta / 天",
    "Vega / 1%": "Vega / 1%",
    "Rho / 1%": "Rho / 1%",
    "Theoretical credit": "理论权利金",
    "Entered credit": "输入权利金",
    "Max profit": "最大盈利",
    "Max loss": "最大亏损",
    "Breakeven": "盈亏平衡",
    "Credit / width": "权利金 / 宽度",
    "Spread Delta": "价差 Delta",
    "Spread Gamma": "价差 Gamma",
    "Spread Theta / day": "价差 Theta / 天",
    "Spread Vega / 1%": "价差 Vega / 1%",
    "Spread Rho / 1%": "价差 Rho / 1%",
    "Records": "记录",
    "Search": "搜索",
    "Sentiment": "市场情绪",
    "Market Sentiment": "市场情绪",
    "Mega-cap Companies": "大型科技股",
    "Global Fear & Greed": "全球贪婪恐惧指标",
    "GreedyFear": "GreedyFear",
    "Open GreedyFear": "打开 GreedyFear",
    "Data from greedyfear.com. Cached locally.": "数据来自 greedyfear.com，本地缓存。",
    "No sentiment data yet.": "暂无市场情绪数据。",
    "Extreme Greed": "极度贪婪",
    "Greed": "贪婪",
    "Neutral": "中性",
    "Fear": "恐惧",
    "Extreme Fear": "极度恐惧",
    "No data": "无数据",
    "Market News": "市场快讯",
    "Loading": "加载中",
    "Market prices": "市场价格",
    "No positions": "暂无持仓",
    "Add holdings to track prices": "添加持仓后跟踪价格",
    "Symbols": "标的",
    "Trades": "交易",
    "Holdings": "持仓",
    "Positions": "持仓数",
    "Total value": "总持仓资金",
    "Allocation": "持仓比例",
    "Profitable": "盈利占比",
    "Average": "平均",
    "Best": "最佳",
    "Worst": "最差",
    "+ New trade": "+ 新交易",
    "Account settings": "账户设置",
    "Assistant review": "AI 持仓分析",
    "Use root account": "使用 root 账户",
    "Language": "语言",
    "Currency": "货币",
    "Theme": "主题",
    "Font": "字体",
    "Local": "本地",
    "Current": "当前",
    "User": "用户",
    "No other users yet": "暂无其他用户",
    "Jin10 red flash": "金十红色快讯",
    "Jin10 Red Market Alerts": "金十红色市场快讯",
    "Refresh now": "立即刷新",
    "Open Jin10": "打开金十",
    "Data from Jin10. Polling is rate-limited locally.": "数据来自金十，本地已限制轮询频率。",
    "source": "来源",
    "No red market flashes right now.": "暂无红色市场快讯。",
    "Seller performance tracker": "交易仪表盘",
    "卖方策略表现追踪": "交易仪表盘",
    "Local data | Your SQLite file stays on this computer": "本地数据 | SQLite 文件仅保存在此电脑",
    "Performance overview": "表现概览",
    "Options Selling Dashboard": "期权卖方仪表盘",
    "Record trade": "记录交易",
    "Trade": "交易信息",
    "Trade date": "交易日期",
    "Trade Type": "交易类型",
    "Stock trade": "股票交易",
    "Buyer Setup": "买方设置",
    "Seller Setup": "卖方设置",
    "Earnings bet": "财报交易",
    "Show this trade in Earnings and highlight it in trade lists.": "在财报页面显示此交易，并在交易列表中突出标记。",
    "Buy price / share": "买入价 / 股",
    "Sell price / share": "卖出价 / 股",
    "Current price / share": "当前价 / 股",
    "Required when closed": "平仓时必填",
    "Used for open holdings": "用于未平仓持仓",
    "Price as of": "价格日期",
    "Buyer fees": "买方手续费",
    "Leave blank while open.": "未平仓时请留空。",
    "Add stock trade": "添加股票交易",
    "Add option trade": "添加期权交易",
    "Realized net P&L": "已实现净盈亏",
    "PL %": "盈亏率",
    "Win rate": "胜率",
    "Total trades": "总交易数",
    "Weighted annualized": "加权年化率",
    "Avg Trade P/L %": "平均每单盈亏%",
    "Average ROC": "平均 ROC",
    "Avg Trade P/L %": "平均每单盈亏%",
    "Best trade": "最佳交易",
    "Max drawdown": "最大回撤",
    "Open Position Alerts": "持仓提醒",
    "active signals": "条提醒",
    "Position Monitor": "持仓监控",
    "Open Positions": "当前持仓",
    "Expiration Watch": "到期观察",
    "Recent Trades": "最近交易",
    "Recent trades": "最近交易",
    "View all": "查看全部",
    "Calendar": "日历",
    "Performance": "表现",
    "Close Date Calendar": "平仓日期日历",
    "Month": "月",
    "Year": "年",
    "Cumulative P&L": "累计盈亏",
    "P&L by Strategy": "按策略盈亏",
    "Capital Usage": "资金占用",
    "Selected Range": "选择区间",
    "Since Inception": "成立以来",
    "All": "全部",
    "Custom": "自定义",
    "5D": "5日",
    "1M": "1月",
    "3M": "3月",
    "6M": "6月",
    "1Y": "1年",
    "Ticker": "标的",
    "Sector": "板块",
    "Strategy": "策略",
    "Status": "状态",
    "Opened": "开仓",
    "Expiration": "到期日",
    "Contracts": "合约",
    "Strike": "行权价",
    "Net P&L": "净盈亏",
    "Trade P/L": "本单盈亏",
    "Trade P/L %": "本单盈亏%",
    "ROC": "ROC",
    "Capital": "资金",
    "Open capital": "占用资金",
    "Current user": "当前用户",
    "Switch user": "切换用户",
    "Create user": "创建用户",
    "Signed in as": "当前登录",
    "Username": "用户名",
    "Password": "密码",
    "Display name": "显示名称",
    "Sign in": "登录",
    "Create and sign in": "创建并登录",
    "No closed-trade history yet.": "暂无已平仓交易历史。",
    "by close date": "按平仓日期",
    "No strategy P&L in this range.": "该区间暂无策略盈亏。",
    "No data available.": "暂无数据。",
    "No matches.": "无匹配结果。",
    "N/A": "N/A",
    "Live Price": "实时价格",
    "Current price": "当前价格",
    "Stock value": "股票市值",
    "Refresh price": "刷新价格",
    "No open positions.": "暂无未平仓持仓。",
    "No upcoming expirations.": "暂无即将到期。",
    "No trades yet.": "暂无交易。",
    "All clear": "全部正常",
    "No near-term expirations or missing holding prices.": "暂无近期到期或缺失价格的持仓。",
    "No open positions expiring within 14 days.": "未来 14 天内没有到期的未平仓持仓。",
    "No capital history yet.": "暂无资金占用历史。",
    "No monthly summaries yet.": "暂无月度汇总。",
    "Monthly Summary": "月度汇总",
    "latest 6 months": "最近 6 个月",
    "Period Summary": "周期汇总",
    "realized by close date": "按平仓日期统计已实现盈亏",
    "This week": "本周",
    "This month": "本月",
    "YTD": "年初至今",
    "Risk Snapshot": "风险快照",
    "open risk & realized curve": "未平仓风险与已实现曲线",
    "Nearest DTE": "最近到期天数",
    "Max drawdown": "最大回撤",
    "Drawdown %": "回撤比例",
    "days until closest expiration": "距离最近到期日的天数",
    "vs peak concurrent capital": "相对峰值并发资金",
    "Risk Review": "风险复盘",
    "snapshot and concentration": "风险快照与集中度",
    "Ticker Exposure": "标的敞口",
    "No current ticker exposure yet.": "暂无当前标的敞口。",
    "open options + stock holdings": "未平仓期权 + 股票持仓",
    "Options capital": "期权资金",
    "Total exposure": "总敞口",
    "Share": "占比",
    "Open": "未平仓",
    "No closed trades yet.": "暂无已平仓交易。",
    "Deeper review": "深度复盘",
    "All symbols": "全部标的",
    "Symbol performance": "标的表现",
    "Total P&L": "总盈亏",
    "Trades": "交易",
    "AI Analysis": "AI 分析",
    "AI Assistant": "AI 助手",
    "Portfolio Prompt": "组合提示词",
    "Position review": "持仓复盘",
    "Analyze Current Holdings": "分析当前持仓",
    "open options, stock holdings, exposure, recent closes": "未平仓期权、股票持仓、敞口、近期平仓",
    "Focus": "关注点",
    "Analyze": "分析",
    "Edit": "编辑",
    "No stock holdings yet.": "暂无股票持仓。",
    "Stock book": "股票持仓簿",
    "Stock Holdings": "股票持仓",
    "Refresh prices": "刷新价格",
    "Add holding": "添加持仓",
    "No trades match these filters.": "没有符合筛选条件的交易。",
    "All statuses": "全部状态",
    "All strategies": "全部策略",
    "All sectors": "全部板块",
    "Sell Put": "卖出 Put",
    "Covered Call": "备兑 Call",
    "Closed": "已平仓",
    "Expired": "到期",
    "Assigned": "被指派",
    "Rolled": "展期",
    "Win": "盈利",
    "Loss": "亏损",
    "Breakeven": "盈亏平衡",
    "Technology": "科技",
    "Communication Services": "通信服务",
    "Consumer Discretionary": "可选消费",
    "Consumer Staples": "必需消费",
    "Financials": "金融",
    "Healthcare": "医疗保健",
    "Industrials": "工业",
    "Energy": "能源",
    "Utilities": "公用事业",
    "Materials": "材料",
    "Real Estate": "房地产",
    "ETF / Index / Commodity": "ETF / 指数 / 商品",
    "Other / Unknown": "其他 / 未知",
    "Prev": "上一页",
    "Next": "下一页",
    "Next earnings": "下次财报",
    "Position & Earnings Alerts": "持仓与财报提醒",
    "No open positions expiring or tracked earnings within 14 days.": "14 天内暂无持仓到期或关注标的财报。",
    "Complete ledger": "完整交易记录",
    "Export CSV": "导出 CSV",
    "Filter": "筛选",
    "Clear": "清除",
    "Symbol breakdown": "标的拆分",
    "Per-ticker performance": "按标的表现",
    "Back to trades": "返回交易",
    "Ticker detail": "标的详情",
    "Back to symbols": "返回标的",
    "Delete holding": "删除持仓",
    "Cancel": "取消",
    "New position": "新仓位",
    "Update position": "更新仓位",
    "Record a trade": "记录交易",
    "Edit trade": "编辑交易",
    "Add trade": "添加交易",
    "Save changes": "保存修改",
    "Holding": "持仓",
    "Ticker": "标的",
    "Short strike": "卖出行权价",
    "Open date": "开仓日期",
    "Close date": "平仓日期",
    "Premium received / share": "收到权利金 / 股",
    "Exit or current premium / share": "平仓或当前权利金 / 股",
    "Stock / assignment P&L": "股票 / 指派盈亏",
    "Fees": "手续费",
    "Capital used": "占用资金",
    "Leave blank for expired options": "到期归零可留空",
    "Use max loss for credit spreads if preferred": "信用价差可填写最大亏损",
    "Notes": "备注",
    "Delete trade": "删除交易",
    "Position": "仓位",
    "Dates": "日期",
    "Cash flow & capital": "现金流与资金",
    "Local account": "本地账户",
    "Account": "账户",
    "data is isolated per account": "数据按账户隔离",
    "root uses a blank password": "root 密码可留空",
    "new account starts with empty trades and holdings": "新账户会从空交易和空持仓开始",
    "Current user": "当前用户",
    "Earnings": "财报",
    "Earnings results": "财报结果",
    "Earnings play": "财报交易",
    "Record earnings bet": "记录财报押注",
    "Record trade": "记录交易",
    "Edit earnings bet": "编辑财报押注",
    "Add earnings bet": "添加财报押注",
    "Delete earnings bet": "删除财报押注",
    "Setup": "设置",
    "Direction": "方向",
    "Bullish": "看涨",
    "Bearish": "看跌",
    "Neutral": "中性",
    "Strategy type": "策略类型",
    "Single option": "单腿期权",
    "Single Option": "单腿期权",
    "Sell option": "卖方期权",
    "Sell Option": "卖方期权",
    "Combo": "组合",
    "Combination": "组合",
    "Stock": "正股",
    "Shares": "股数",
    "Buy price": "买入价",
    "Sell price": "卖出价",
    "Option type": "期权类型",
    "Call": "Call",
    "Put": "Put",
    "Open price / contract": "开仓价 / 合约",
    "Open credit / contract": "开仓权利金 / 合约",
    "Close price / contract": "平仓价 / 合约",
    "Combo description": "组合描述",
    "Contracts / units": "合约 / 单位",
    "Open debit / risk": "开仓成本 / 风险",
    "Close value": "平仓价值",
    "Outcome": "结果",
    "Position size override": "仓位金额覆盖",
    "Cost / risk override": "成本 / 风险覆盖",
    "Realized P&L override": "已实现盈亏覆盖",
    "Earnings date": "财报日期",
    "Position size": "仓位金额",
    "Cost": "成本",
    "P&L": "盈亏",
    "P&L %": "盈亏率",
    "Result": "结果",
    "Results": "结果统计",
    "Pending": "待定",
    "Win / Breakeven / Loss": "盈利 / 保本 / 亏损",
    "Option Seller": "期权卖方",
    "Option Buyer": "期权买方",
    "Day Trades": "日内交易",
    "Day trade": "日内交易",
    "Stock Trades": "正股交易",
    "Stock Position": "股票持仓",
    "Other option": "其他期权",
    "Option Buyer Call": "期权买方 Call",
    "Option Buyer Put": "期权买方 Put",
    "Option Buyer Combo": "期权买方组合",
    "Option Buyer Call Debit Spread": "Call 借方价差",
    "Option Buyer Put Debit Spread": "Put 借方价差",
    "Day Trade Call": "日内 Call",
    "Day Trade Put": "日内 Put",
    "Stock Sell": "正股卖出",
    "Total holdings": "总持仓资金",
    "Current Holdings": "当前持仓",
    "Holdings": "持仓",
    "Refresh prices": "刷新价格",
    "Market value": "市值",
    "Avg cost": "平均成本",
    "Cost basis": "成本基础",
    "Unrealized P&L": "未实现盈亏",
    "Return": "收益率",
    "As of": "截至",
    "Return method": "收益计算方式",
    "Simple weighted": "简单加权",
    "Time weighted": "时间加权",
    "All accounts": "全部账户",
    "Add deposit": "添加入金",
    "Portfolio cash flow": "组合资金流",
    "Back to portfolio": "返回投资组合",
    "Deposit details": "入金明细",
    "Deposit date": "入金日期",
    "Deposit history": "入金记录",
    "Portfolio / unassigned": "投资组合 / 未指定账户",
    "Used to remove contributions from portfolio returns": "用于从投资组合收益中扣除入金影响",
    "No deposits recorded yet.": "尚无入金记录。",
    "Available": "可用余额",
    "Category": "类别",
    "Updated": "更新时间",
    "Never": "从未",
    "Synced": "已同步",
    "No snapshot": "无快照",
    "No account snapshot yet.": "尚无账户快照。",
    "2027 Year-End Valuation": "2027 年底估值",
    "2027 EPS": "2027 年 EPS",
    "Bear P/E": "悲观市盈率",
    "Base P/E": "基准市盈率",
    "Bull P/E": "乐观市盈率",
    "Bear": "悲观",
    "Base": "基准",
    "Bull": "乐观",
    "Price unavailable": "暂无价格",
    "Weekly win rate": "当周胜率",
    "Account value": "账户价值",
    "Back-adjusted value": "回溯调整后价值",
    "Deposit": "入金",
    "Withdrawal": "出金",
    "Trading Dashboard": "交易仪表盘",
    "Local-first trading intelligence": "本地优先的交易智能",
    "Built for": "专为",
    "Private by default": "默认保护隐私",
    "Bilingual workflow": "中英双语工作流",
    "Fast local analytics": "快速本地分析",
    "View portfolio": "查看组合",
    "Enter dashboard": "进入仪表盘",
    "Edit details": "编辑详情",
    "Loading details...": "正在加载详情...",
    "Trades / Contracts": "交易 / 合约",
    "Best / Worst": "最佳 / 最差",
    "Avg Win P/L / %": "平均盈利 / 收益率",
    "Avg Loss P/L / %": "平均亏损 / 亏损率",
    "Avg P&L": "平均盈亏",
    "Avg P/L %": "平均盈亏率",
    "P&L%": "盈亏率",
    "Max capital usage": "最大资金占用",
    "Best symbol": "最佳标的",
    "Worst symbol": "最差标的",
    "Best trade": "最佳交易",
    "Worst trade": "最差交易",
    "Side": "方向",
    "Exposure": "敞口",
    "Long": "多头",
    "Short": "空头",
    "Buy to open": "买入开仓",
    "Sell to open": "卖出开仓",
    "Sell": "卖出",
    "Sell Put": "卖出看跌期权",
    "Covered Call": "备兑看涨期权",
    "Put Credit Spread": "看跌信用价差",
    "Call Credit Spread": "看涨信用价差",
    "Iron Condor": "铁鹰价差",
    "Call Debit Spread": "看涨借方价差",
    "Put Debit Spread": "看跌借方价差",
    "Bets": "交易数",
    "Buy": "买入",
    "Buys": "次买入",
    "Call": "看涨期权",
    "Put": "看跌期权",
    "Shares": "股",
    "Options": "期权",
    "Stocks": "股票",
    "All option strategies": "全部期权策略",
    "All strategies": "全部策略",
    "All sources": "全部来源",
    "Descending": "降序",
    "Ascending": "升序",
    "Record stock trade": "记录股票交易",
    "S&P": "标普 500",
    "Nasdaq": "纳斯达克",
    "Option ledger": "期权交易记录",
    "Option Trades": "期权交易",
    "All results": "全部结果",
    "All types": "全部类型",
    "Call / Put": "看涨 / 看跌",
    "Broker": "券商",
    "Trade type": "交易类型",
    "Book": "交易簿",
    "Broker source": "券商来源",
    "Execution": "执行信息",
    "Buy price / contract": "买入价 / 合约",
    "Delete option buyer trade": "删除期权买方交易",
    "Option buyer": "期权买方",
    "Edit option buyer trade": "编辑期权买方交易",
    "Record option buyer trade": "记录期权买方交易",
    "Add option buyer trade": "添加期权买方交易",
    "Opened from": "开仓起始日",
    "Opened to": "开仓截止日",
    "Symbol intelligence": "标的情报",
    "load on demand": "按需加载",
    "Market intelligence is paused so this page opens quickly.": "市场情报已暂停自动加载，以便快速打开页面。",
    "Refresh intelligence": "刷新情报",
    "Live - refreshes every 30s": "实时数据 - 每 30 秒刷新",
    "As of live quote": "最新实时报价",
    "Live quote": "实时报价",
    "EPS x P/E": "EPS × 市盈率",
    "1W": "1周",
    "ALL": "全部",
    "Jan": "1月",
    "Feb": "2月",
    "Mar": "3月",
    "Apr": "4月",
    "May": "5月",
    "Jun": "6月",
    "Jul": "7月",
    "Aug": "8月",
    "Sep": "9月",
    "Oct": "10月",
    "Nov": "11月",
    "Dec": "12月",
    "Sun": "日",
    "Mon": "一",
    "Tue": "二",
    "Wed": "三",
    "Thu": "四",
    "Fri": "五",
    "Sat": "六",
    "Cash-flow-adjusted account value; deposits and withdrawals are back-adjusted for comparability.": "现金流调整后的账户价值；入金和出金已回溯调整，便于比较。",
    "Simple return subtracts deposits; the chart back-adjusts earlier values for comparability.": "简单收益会扣除入金；图表对较早数据进行回溯调整，便于比较。",
    "Time-weighted return removes deposits by date; the chart back-adjusts earlier values for comparability.": "时间加权收益按日期剔除入金；图表对较早数据进行回溯调整，便于比较。",
    "Dashboard": "仪表盘"
  };
  const localizedMonths = {
    Jan: "1月", Feb: "2月", Mar: "3月", Apr: "4月", May: "5月", Jun: "6月",
    Jul: "7月", Aug: "8月", Sep: "9月", Oct: "10月", Nov: "11月", Dec: "12月"
  };
  const localizedFullMonths = {
    January: "1月", February: "2月", March: "3月", April: "4月", May: "5月", June: "6月",
    July: "7月", August: "8月", September: "9月", October: "10月", November: "11月", December: "12月"
  };
  const translatedText = (raw) => {
    if (!raw) return null;
    if (zhText[raw]) return zhText[raw];
    const dashboardHoldings = raw.match(/^(\d+) open options \| (\d+) current holdings \| (\d+) recent trades$/);
    if (dashboardHoldings) return `${dashboardHoldings[1]} 个未平仓期权 | ${dashboardHoldings[2]} 个当前持仓 | ${dashboardHoldings[3]} 笔最近交易`;
    const symbolTradeCounts = raw.match(/^([\d,]+) symbols? · ([\d,]+) trades?$/);
    if (symbolTradeCounts) return symbolTradeCounts[1] + " 个标的 · " + symbolTradeCounts[2] + " 笔交易";
    const symbolTradesTitle = raw.match(/^(.+) trades$/);
    if (symbolTradesTitle) return symbolTradesTitle[1] + " 交易记录";
    const recordCount = raw.match(/^([\d,]+) \/ ([\d,]+) records$/);
    if (recordCount) return recordCount[1] + " / " + recordCount[2] + " 条记录";
    const abbreviatedWinRate = raw.match(/^WR (.+)$/);
    if (abbreviatedWinRate) return "胜率 " + abbreviatedWinRate[1];
    const portfolioMethod = raw.match(/^Portfolio \((Simple weighted|Time weighted)\)$/);
    if (portfolioMethod) return "组合（" + (translatedText(portfolioMethod[1]) || portfolioMethod[1]) + "）";
    const weeklyWinDisplay = raw.match(/^(.+) \| Weekly win (.+)$/);
    if (weeklyWinDisplay) return weeklyWinDisplay[1] + " | 当周胜率 " + weeklyWinDisplay[2];
    const positionSummary = raw.match(/^([\d,]+) positions? - (.+)$/);
    if (positionSummary) return positionSummary[1] + " 个持仓 - " + positionSummary[2];
    const stockOptionPnl = raw.match(/^Stocks (.+) · Options (.+)$/);
    if (stockOptionPnl) return "股票 " + stockOptionPnl[1] + " · 期权 " + stockOptionPnl[2];
    const averageValue = raw.match(/^Avg (.+)$/);
    if (averageValue) return "平均 " + averageValue[1];
    const ytdPeak = raw.match(/^YTD - peak (.+)$/);
    if (ytdPeak) return `年初至今 - 峰值 ${ytdPeak[1]}`;
    const inceptionPeak = raw.match(/^Since Inception - peak (.+)$/);
    if (inceptionPeak) return `成立以来 - 峰值 ${inceptionPeak[1]}`;
    const asOf = raw.match(/^As of (.+)$/);
    if (asOf) return `截至 ${translatedText(asOf[1]) || asOf[1]}`;
    const calendarPnl = raw.match(/^(January|February|March|April|May|June|July|August|September|October|November|December) (\d{4}) realized P&L by close date$/);
    if (calendarPnl) return `${calendarPnl[2]}年${localizedFullMonths[calendarPnl[1]]}按平仓日期统计已实现盈亏`;
    const calendarYearPnl = raw.match(/^(\d{4}) realized P&L by close date$/);
    if (calendarYearPnl) return `${calendarYearPnl[1]}年按平仓日期统计已实现盈亏`;
    const tradeCount = raw.match(/^(\d+) trades?$/);
    if (tradeCount) return `${tradeCount[1]} 笔交易`;
    const buyCount = raw.match(/^(\d+) (Buy|Buys)$/);
    if (buyCount) return `${buyCount[1]} 次买入`;
    const datedBuyCount = raw.match(/^(.+) · (\d+) (Buy|Buys)$/);
    if (datedBuyCount) return `${datedBuyCount[1]} · ${datedBuyCount[2]} 次买入`;
    const datedShares = raw.match(/^(.+) · ([\d,.]+) shares$/);
    if (datedShares) return datedShares[1] + " · " + datedShares[2] + " 股";
    const valueAndAverage = raw.match(/^(.+) value · (.+) avg$/);
    if (valueAndAverage) return valueAndAverage[1] + " 市值 · 平均成本 " + valueAndAverage[2];
    const statusAndDate = raw.match(/^(Open|Closed) · (.+)$/);
    if (statusAndDate) return (statusAndDate[1] === "Open" ? "未平仓" : "已平仓") + " · " + statusAndDate[2];
    const stockStrategy = raw.match(/^Stock: ([\d,.]+) shares(.*)$/);
    if (stockStrategy) return "股票：" + stockStrategy[1] + " 股" + stockStrategy[2];
    const datedStockStrategy = raw.match(/^(.+) · Stock: ([\d,.]+) shares$/);
    if (datedStockStrategy) return datedStockStrategy[1] + " · 股票：" + datedStockStrategy[2] + " 股";
    const strategyNames = "Sell Put|Covered Call|Put Credit Spread|Call Credit Spread|Iron Condor|Call Debit Spread|Put Debit Spread";
    const datedStrategy = raw.match(new RegExp("^(.+) · (" + strategyNames + ")$"));
    if (datedStrategy) return datedStrategy[1] + " · " + (translatedText(datedStrategy[2]) || datedStrategy[2]);
    const strategyAndDate = raw.match(new RegExp("^(" + strategyNames + ") · (.+)$"));
    if (strategyAndDate) return (translatedText(strategyAndDate[1]) || strategyAndDate[1]) + " · " + strategyAndDate[2];
    const simpleStrategyNames = "Single option|Sell option|Call|Put|Day trade";
    const datedSimpleStrategy = raw.match(new RegExp("^(.+) · (" + simpleStrategyNames + ")$"));
    if (datedSimpleStrategy) return datedSimpleStrategy[1] + " · " + (translatedText(datedSimpleStrategy[2]) || datedSimpleStrategy[2]);
    const simpleStrategyAndDate = raw.match(new RegExp("^(" + simpleStrategyNames + ") · (.+)$"));
    if (simpleStrategyAndDate) return (translatedText(simpleStrategyAndDate[1]) || simpleStrategyAndDate[1]) + " · " + simpleStrategyAndDate[2];
    const pnlSuffix = raw.match(/^(.+) P&L$/);
    if (pnlSuffix) return pnlSuffix[1] + " 盈亏";
    const shareCount = raw.match(/^([\d,.]+) Shares$/);
    if (shareCount) return `${shareCount[1]} 股`;
    const strategySummary = raw.match(/^(\d+) · (Single option|Sell option): (Call|Put)$/);
    if (strategySummary) {
      const strategy = strategySummary[2] === "Single option" ? "单腿期权" : "卖出期权";
      const optionType = strategySummary[3] === "Call" ? "看涨" : "看跌";
      return `${strategySummary[1]} · ${strategy}：${optionType}`;
    }
    const singleOptionDetail = raw.match(/^(Single option|Sell option): (Call|Put)(.*)$/);
    if (singleOptionDetail) {
      const strategy = singleOptionDetail[1] === "Single option" ? "单腿期权" : "卖出期权";
      const optionType = singleOptionDetail[2] === "Call" ? "看涨" : "看跌";
      return `${strategy}：${optionType}${singleOptionDetail[3]}`;
    }
    const pluralOption = raw.match(/^(.+) (Calls|Puts)$/);
    if (pluralOption) return `${pluralOption[1]} ${pluralOption[2] === "Calls" ? "看涨期权" : "看跌期权"}`;
    const contractCount = raw.match(/^(.+) · ([\d.]+) contracts?$/);
    if (contractCount) return `${contractCount[1]} · ${contractCount[2]} 张合约`;
    const shareStatus = raw.match(/^([\d,.]+) shares$/);
    if (shareStatus) return `${shareStatus[1]} 股`;
    const sellOptionDetail = raw.match(/^Sell option: (.+)$/);
    if (sellOptionDetail) {
      const detail = sellOptionDetail[1]
        .replace(/^Sell /, "卖出 ")
        .replace(/\bCalls?\b/g, "看涨期权")
        .replace(/\bPuts?\b/g, "看跌期权");
      return "卖出期权：" + detail;
    }
    const prefixedOptionContract = raw.match(/^(Call|Put) (.+)$/);
    if (prefixedOptionContract) return (prefixedOptionContract[1] === "Call" ? "看涨期权" : "看跌期权") + " " + prefixedOptionContract[2];
    const optionStrike = raw.match(/^(.+) (Call|Put)$/);
    if (optionStrike) return `${optionStrike[1]} ${optionStrike[2] === "Call" ? "看涨期权" : "看跌期权"}`;
    const holdingPrices = raw.match(/^(.+) avg · (.+) current$/);
    if (holdingPrices) return `平均成本 ${holdingPrices[1]} · 当前价 ${holdingPrices[2]}`;
    const nearestContracts = raw.match(/^(.+) nearest · (.+) contracts?$/);
    if (nearestContracts) return `${nearestContracts[1]} 最近到期 · ${nearestContracts[2]} 张合约`;
    const optionStockExposure = raw.match(/^Options (.+) · Stocks (.+)$/);
    if (optionStockExposure) return `期权 ${optionStockExposure[1]} · 股票 ${optionStockExposure[2]}`;
    const optionLegend = raw.match(/^(.+) options$/);
    if (optionLegend) return `${optionLegend[1]} 期权`;
    const earningsRange = raw.match(/^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{1,2}) - (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{1,2}) \| (\d+) reports? \| (\d+) positions?$/);
    if (earningsRange) return `${localizedMonths[earningsRange[1]]}${earningsRange[2]}日 - ${localizedMonths[earningsRange[3]]}${earningsRange[4]}日 | ${earningsRange[5]} 份财报 | ${earningsRange[6]} 个持仓`;
    const updatedAt = raw.match(/^Updated (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{1,2}), (\d{4}), (.+)$/);
    if (updatedAt) {
      const localizedTime = updatedAt[4].replace(/^(.*) AM$/, "上午 $1").replace(/^(.*) PM$/, "下午 $1");
      return `${updatedAt[3]}年${localizedMonths[updatedAt[1]]}${updatedAt[2]}日 ${localizedTime} 更新`;
    }
    const activeSignals = raw.match(/^(\d+) active signals$/);
    if (activeSignals) return `${activeSignals[1]} 条提醒`;
    const accountSync = raw.match(/^(\d+) accounts? - (\d+) Plaid items? - Last sync (.+)$/);
    if (accountSync) return `${accountSync[1]} 个账户 - ${accountSync[2]} 个 Plaid 项目 - 最近同步 ${accountSync[3]}`;
    const lastSync = raw.match(/^Last sync (.+)$/);
    if (lastSync) return `最近同步 ${lastSync[1]}`;
    const syncedRobinhood = raw.match(/^Synced (\d+) Robinhood accounts? and (\d+) stock holdings?\.$/);
    if (syncedRobinhood) return `已同步 ${syncedRobinhood[1]} 个 Robinhood 账户和 ${syncedRobinhood[2]} 个股票持仓。`;
    const syncedAccounts = raw.match(/^Synced (\d+) accounts?\.$/);
    if (syncedAccounts) return `已同步 ${syncedAccounts[1]} 个账户。`;
    const syncedPlaid = raw.match(/^Synced (\d+) Plaid accounts?\.$/);
    if (syncedPlaid) return `已同步 ${syncedPlaid[1]} 个 Plaid 账户。`;
    const openRecent = raw.match(/^(\d+) open positions \| (\d+) recent trades$/);
    if (openRecent) return `${openRecent[1]} 个当前持仓 | ${openRecent[2]} 笔最近交易`;
    const openCount = raw.match(/^(\d+) open$/);
    if (openCount) return `${openCount[1]} 个未平仓`;
    const openPositions = raw.match(/^(\d+) open positions$/);
    if (openPositions) return `${openPositions[1]} 个未平仓持仓`;
    const openPositionsShort = raw.match(/^(\d+) open positions?$/);
    if (openPositionsShort) return `${openPositionsShort[1]} 个未平仓持仓`;
    const openPlain = raw.match(/^(\d+) open$/);
    if (openPlain) return `${openPlain[1]} 个未平仓`;
    if (raw === "open positions") return "未平仓持仓";
    const dteValue = raw.match(/^(\d+) DTE$/);
    if (dteValue) return `${dteValue[1]} 天到期`;
    const positionTickers = raw.match(/^(\d+) positions? · (.+)$/);
    if (positionTickers) return `${positionTickers[1]} 个持仓 · ${positionTickers[2]}`;
    const monthDate = raw.match(/^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{1,2})$/);
    if (monthDate) {
      return `${localizedMonths[monthDate[1]]}${monthDate[2]}日`;
    }
    const dateRange = raw.match(/^(\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})$/);
    if (dateRange) return `${dateRange[1]} 至 ${dateRange[2]}`;
    const tradeSummary = raw.match(/^(\d+) trades · Win ([^·]+) · PL% (.+)$/);
    if (tradeSummary) return `${tradeSummary[1]} 笔交易 · 胜率 ${tradeSummary[2]} · 盈亏率 ${tradeSummary[3]}`;
    const oneTradeSummary = raw.match(/^1 trades · Win ([^·]+) · PL% (.+)$/);
    if (oneTradeSummary) return `1 笔交易 · 胜率 ${oneTradeSummary[1]} · 盈亏率 ${oneTradeSummary[2]}`;
    const selectedRange = raw.match(/^Selected Range: (.+?) - (.+?) to (.+)$/);
    if (selectedRange) {
      const rangeLabel = translatedText(selectedRange[1]) || selectedRange[1];
      return `选择区间：${rangeLabel} - ${selectedRange[2]} 至 ${selectedRange[3]}`;
    }
    const winRate = raw.match(/^Win rate (.+)$/);
    if (winRate) return `胜率 ${winRate[1]}`;
    const dataThrough = raw.match(/^Data through (.+)$/);
    if (dataThrough) return `数据截至 ${dataThrough[1]}`;
    const closedTrades = raw.match(/^(\d+) closed trades$/);
    if (closedTrades) return `${closedTrades[1]} 笔已平仓交易`;
    const winLoss = raw.match(/^(\d+)W \/ (\d+)L$/);
    if (winLoss) return `${winLoss[1]} 胜 / ${winLoss[2]} 负`;
    const activeDays = raw.match(/^(\d+) active days$/);
    if (activeDays) return `${activeDays[1]} 个交易日`;
    const tradePace = raw.match(/^([\d.]+)\/day$/);
    if (tradePace) return `${tradePace[1]} 笔/日`;
    const largestDrag = raw.match(/^The largest drag was (.+?): (\d+) trades, (.+) win rate, and (.+) total\. This is the first strategy to pause and review, not ordinary weekly noise\.$/);
    if (largestDrag) return `主要拖累来自 ${largestDrag[1]}：${largestDrag[2]} 笔交易，胜率 ${largestDrag[3]}，合计 ${largestDrag[4]}。这不是普通的周度噪音，而是最需要暂停和复盘的策略。`;
    const concentratedLosses = raw.match(/^Losses were concentrated: (.+?) contributed (.+?), while the three largest losses made up (.+?) of gross losses\. A few oversized mistakes drove the week\.$/);
    if (concentratedLosses) return `亏损较为集中：${concentratedLosses[1]} 贡献 ${concentratedLosses[2]}，最大的三笔亏损占总亏损 ${concentratedLosses[3]}。少数过大的错误主导了本周结果。`;
    const highFrequency = raw.match(/^Trade frequency was high: (\d+) closes across (\d+) sessions, or ([\d.]+) per day\. At a (.+?) win rate, frequency amplified both decision errors and emotional pressure\.$/);
    if (highFrequency) return `交易频率偏高：${highFrequency[1]} 笔平仓分布在 ${highFrequency[2]} 个交易日，平均每天 ${highFrequency[3]} 笔。在胜率仅 ${highFrequency[4]} 时，频率同时放大了判断误差和情绪压力。`;
    const pnlGap = raw.match(/^Portfolio movement differed from realized P&L by about (.+?)\. Open-position marks, option pricing, cash flows, or account-sync differences explain the remainder; closed trades alone do not\.$/);
    if (pnlGap) return `组合变化与已实现盈亏相差约 ${pnlGap[1]}。其余部分来自持仓市值、期权报价、现金流或账户同步差异，不能只用平仓记录解释。`;
    const riskLimit = raw.match(/^Limit new risk per idea to about 1% of the portfolio \((.+?) at the latest snapshot\) until results stabilize for two consecutive weeks\.$/);
    if (riskLimit) return `单个新想法的风险限制在组合的 1% 左右（按最新快照约 ${riskLimit[1]}），直到连续两周恢复稳定。`;
    const dailyLimit = raw.match(/^Use a 1\.5% daily loss limit \(about (.+?)\)\. Once reached, open no additional directional positions that day\.$/);
    if (dailyLimit) return `设置 1.5% 的单日止损线（约 ${dailyLimit[1]}）。触线后当天不再开新的方向性仓位。`;
    const showing = raw.match(/^Showing (\d+) to (\d+) of (\d+)$/);
    if (showing) return `显示第 ${showing[1]}-${showing[2]} 条，共 ${showing[3]} 条`;
    const showingZero = raw.match(/^Showing 0 of 0$/);
    if (showingZero) return "显示 0 条，共 0 条";
    return null;
  };
  const translateNode = (node) => {
    if (!node) return;
    if (node.children.length) {
      node.childNodes.forEach((child) => {
        if (child.nodeType !== Node.TEXT_NODE) return;
        const raw = child.textContent.trim();
        const next = repairMojibake(translatedText(raw));
        if (next) child.textContent = child.textContent.replace(raw, next);
      });
      return;
    }
    const raw = node.textContent.trim();
    const next = repairMojibake(translatedText(raw));
    if (next) node.textContent = node.textContent.replace(raw, next);
  };
  const actionIcons = {
    edit: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>',
    view: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.1 12a10.8 10.8 0 0 1 19.8 0 10.8 10.8 0 0 1-19.8 0Z"/><circle cx="12" cy="12" r="3"/></svg>',
    delete: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v5M14 11v5"/></svg>',
    refresh: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/></svg>'
  };
  const setActionIcon = (control, icon, label) => {
    if (!control || !actionIcons[icon]) return;
    control.dataset.actionLabel = label;
    control.classList.add("icon-action");
    control.setAttribute("aria-label", label);
    control.setAttribute("title", label);
    control.innerHTML = actionIcons[icon];
  };
  const applyActionIcons = (root = document) => {
    root.querySelectorAll("a.text-button, a.transaction-edit, .panel-head > a").forEach((control) => {
      const label = control.dataset.actionLabel || control.textContent.trim();
      if (label === "Edit") setActionIcon(control, "edit", "Edit");
      else if (label === "View") setActionIcon(control, "view", "View");
      else if (/^View all(?:\s*>|\s*›)?$/.test(label)) setActionIcon(control, "view", "View all");
    });
    root.querySelectorAll(".row-actions .danger-link").forEach((control) => {
      const label = control.dataset.actionLabel || control.textContent.trim();
      if (label === "Delete") {
        control.classList.add("icon-action-danger");
        setActionIcon(control, "delete", "Delete");
      }
    });
    root.querySelectorAll("[data-earnings-reminder-refresh]").forEach((control) => {
      setActionIcon(control, "refresh", "Refresh earnings");
    });
  };
  const applyLanguage = (root = document) => {
    document.documentElement.lang = activeLanguage === "zh" ? "zh-CN" : "en";
    if (languagePicker) languagePicker.value = activeLanguage;
    applyActionIcons(root);
    if (activeLanguage !== "zh") return;
    root.querySelectorAll("a,button,span,b,strong,small,h1,h2,h3,p,th,td,li,label,legend,option,footer,em,div,svg text,svg tspan").forEach(translateNode);
    root.querySelectorAll("select option").forEach((option) => {
      const text = option.textContent.trim();
      const next = translatedText(text);
      if (next) option.textContent = next;
    });
    root.querySelectorAll("input[placeholder],textarea[placeholder]").forEach((field) => {
      const text = field.getAttribute("placeholder");
      const placeholders = {
        "Search pages, symbols, actions...": "搜索页面、标的、操作...",
        "Search ticker or sector": "搜索标的或板块",
        "Search ticker, sector, or notes": "搜索标的、板块或备注",
        "Search ticker, strategy, or notes": "搜索标的、策略或备注",
        "Search ticker, combo, or notes": "搜索标的、组合或备注",
        "Search strategy or notes": "搜索策略或备注",
        "Search ticker first, or longer text": "优先搜索标的，也可输入更多内容",
        "Optional transfer reference or note": "可选：转账编号或备注",
        "Thesis, catalyst, exit reason...": "交易逻辑、催化剂、退出原因...",
        "Setup, sell reason, realized lot notes...": "交易设置、卖出原因、已实现批次备注...",
        "Setup, thesis, exit note...": "交易设置、交易逻辑、退出备注...",
        "blank for root": "root 可留空",
        "e.g. SOXL": "例如 SOXL",
        "e.g. AAPL": "例如 AAPL",
        "e.g. NVDA": "例如 NVDA",
        "e.g. Straddle, iron condor, calendar": "例如跨式、铁鹰、日历价差",
        "Dividend notes, covered call linkage, thesis...": "分红备注、备兑关联、交易逻辑...",
        "Roll linkage, assignment details, thesis…": "展期关联、指派细节、交易逻辑...",
        "Expected move, IV crush, entry/exit, what you learned...": "预期波动、IV crush、进出场、复盘心得..."
      };
      if (placeholders[text]) field.setAttribute("placeholder", repairMojibake(placeholders[text]));
    });
    root.querySelectorAll(".earnings-linked").forEach((badge) => {
      badge.textContent = "财报";
      badge.title = "关联财报交易";
    });
  };
  if (languagePicker) {
    languagePicker.value = activeLanguage;
    languagePicker.addEventListener("change", () => {
      localStorage.setItem("optionLedgerLanguage", languagePicker.value);
      const nextUrl = new URL(window.location.href);
      if (languagePicker.value === "en") nextUrl.searchParams.delete("lang");
      else nextUrl.searchParams.set("lang", languagePicker.value);
      window.location.href = `${nextUrl.pathname}${nextUrl.search}`;
    });
  }

  const currencyPicker = document.querySelector(".currency-picker");
  const savedCurrency = localStorage.getItem("optionLedgerCurrency") || "usd";
  const urlCurrency = currentUrl.searchParams.get("currency");
  if (!urlCurrency && savedCurrency !== "usd") {
    currentUrl.searchParams.set("currency", savedCurrency);
    window.location.replace(`${currentUrl.pathname}${currentUrl.search}`);
    return;
  }
  const activeCurrency = urlCurrency === "rmb" ? "rmb" : "usd";
  localStorage.setItem("optionLedgerCurrency", activeCurrency);
  if (currencyPicker) {
    currencyPicker.value = activeCurrency;
    currencyPicker.addEventListener("change", () => {
      localStorage.setItem("optionLedgerCurrency", currencyPicker.value);
      const nextUrl = new URL(window.location.href);
      if (currencyPicker.value === "usd") {
        nextUrl.searchParams.delete("currency");
      } else {
        nextUrl.searchParams.set("currency", currencyPicker.value);
      }
      window.location.href = `${nextUrl.pathname}${nextUrl.search}`;
    });
  }

  const themePicker = document.querySelector(".theme-picker");
  const themeToggle = document.querySelector(".theme-toggle");
  const themeIcon = themeToggle ? themeToggle.querySelector(".theme-toggle-icon") : null;
  const themeModes = ["auto", "light", "dark"];
  const themeForMode = (mode) => {
    if (mode !== "auto") return mode;
    return "light";
  };
  const updateThemeToggle = (mode, resolved) => {
    if (!themeToggle || !themeIcon) return;
    themeToggle.dataset.mode = mode;
    themeToggle.dataset.resolved = resolved;
    const labels = { auto: "Auto", light: "Light", dark: "Dark" };
    themeToggle.title = `Theme: ${labels[mode] || "Auto"}`;
    themeToggle.setAttribute("aria-label", `Theme: ${labels[mode] || "Auto"}. Click to change.`);
    themeIcon.textContent = mode === "auto" ? "A" : (resolved === "dark" ? "☾" : "☀");
  };
  const applyTheme = () => {
    const mode = localStorage.getItem("optionLedgerTheme") || "auto";
    const resolved = themeForMode(mode);
    document.body.dataset.themeMode = mode;
    document.body.dataset.theme = resolved;
    if (themePicker) themePicker.value = mode;
    updateThemeToggle(mode, resolved);
  };
  applyTheme();
  if (themePicker) {
    themePicker.addEventListener("change", () => {
      localStorage.setItem("optionLedgerTheme", themePicker.value);
      applyTheme();
    });
  }
  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const current = localStorage.getItem("optionLedgerTheme") || "auto";
      const next = themeModes[(themeModes.indexOf(current) + 1) % themeModes.length];
      localStorage.setItem("optionLedgerTheme", next);
      applyTheme();
    });
  }
  if (themePicker || themeToggle) {
    window.setInterval(() => {
      if ((localStorage.getItem("optionLedgerTheme") || "auto") === "auto") applyTheme();
    }, 60000);
  }

  const fontPicker = document.querySelector(".font-picker");
  const savedFont = localStorage.getItem("optionLedgerFont") || "Tahoma";
  document.body.dataset.font = savedFont;
  if (fontPicker) {
    fontPicker.value = savedFont;
    fontPicker.addEventListener("change", () => {
      document.body.dataset.font = fontPicker.value;
      localStorage.setItem("optionLedgerFont", fontPicker.value);
    });
  }

  const bindLegacyTradeForm = (root = document) => {
    const strategy = root.querySelector("#strategy");
    const spread = root.querySelector(".spread-field");
    const condorFields = Array.from(root.querySelectorAll(".condor-field"));
    const syncSpread = () => {
      if (!strategy) return;
      const isCondor = strategy.value === "Iron Condor";
      const usesLongPut = isCondor || ["Put Credit Spread", "Call Credit Spread"].includes(strategy.value);
      if (spread) {
        spread.hidden = !usesLongPut;
        spread.querySelectorAll("input").forEach((input) => { input.required = usesLongPut; });
      }
      condorFields.forEach((field) => {
        field.hidden = !isCondor;
        field.querySelectorAll("input").forEach((input) => { input.required = isCondor; });
      });
      root.querySelector("[data-seller-strike-label]")?.replaceChildren(document.createTextNode(isCondor ? "Short put strike" : "Short strike"));
      root.querySelector("[data-seller-long-label]")?.replaceChildren(document.createTextNode(isCondor ? "Long put strike" : "Long strike"));
      root.querySelector("[data-seller-long-help]")?.replaceChildren(document.createTextNode(isCondor ? "Put-side protective wing." : "Only for credit spreads"));
    };
    if (strategy && strategy.dataset.legacyTradeBound !== "1") {
      strategy.dataset.legacyTradeBound = "1";
      strategy.addEventListener("change", syncSpread);
      syncSpread();
    }

    const tradeStatus = root.querySelector('.trade-form select[name="status"]');
    const closeDate = root.querySelector('.trade-form input[name="close_date"]');
    const syncCloseDate = () => {
      if (!tradeStatus || !closeDate) return;
      const needsCloseDate = tradeStatus.value !== "Open";
      closeDate.required = needsCloseDate;
      if (needsCloseDate && !closeDate.value) closeDate.value = new Date().toISOString().slice(0, 10);
    };
    if (tradeStatus && closeDate && tradeStatus.dataset.closeDateBound !== "1") {
      tradeStatus.dataset.closeDateBound = "1";
      tradeStatus.addEventListener("change", syncCloseDate);
      syncCloseDate();
    }
  };
  bindLegacyTradeForm();

  const loadPlaidScript = () => new Promise((resolve, reject) => {
    if (window.Plaid) return resolve();
    const existing = document.querySelector('script[data-plaid-link]');
    if (existing) {
      existing.addEventListener("load", resolve, { once: true });
      existing.addEventListener("error", reject, { once: true });
      return;
    }
    const script = document.createElement("script");
    script.src = "https://cdn.plaid.com/link/v2/stable/link-initialize.js";
    script.async = true;
    script.dataset.plaidLink = "true";
    script.addEventListener("load", resolve, { once: true });
    script.addEventListener("error", reject, { once: true });
    document.head.appendChild(script);
  });

  const bindPlaidConnect = (root = document) => {
    root.querySelectorAll("[data-plaid-connect]").forEach((button) => {
      if (button.dataset.plaidBound === "1") return;
      button.dataset.plaidBound = "1";
      button.addEventListener("click", async () => {
      const original = button.textContent;
      button.disabled = true;
      button.textContent = "Connecting...";
      try {
        const tokenResponse = await fetch("/brokerage/plaid/link-token", { method: "POST" });
        const tokenPayload = await tokenResponse.json();
        if (!tokenResponse.ok || !tokenPayload.link_token) throw new Error(tokenPayload.error || "Could not create Plaid Link token.");
        await loadPlaidScript();
        const handler = window.Plaid.create({
          token: tokenPayload.link_token,
          onSuccess: async (public_token, metadata) => {
            const body = new URLSearchParams();
            body.set("public_token", public_token);
            body.set("institution", metadata?.institution?.name || "Plaid account");
            const exchangeResponse = await fetch("/brokerage/plaid/exchange", { method: "POST", body });
            const exchangePayload = await exchangeResponse.json();
            if (!exchangeResponse.ok) throw new Error(exchangePayload.error || "Plaid exchange failed.");
            window.location.href = "/brokerage";
          },
          onExit: () => {
            button.disabled = false;
            button.textContent = original;
          },
        });
        handler.open();
      } catch (error) {
        alert(error.message || "Plaid connection failed.");
        button.disabled = false;
        button.textContent = original;
      }
      });
    });
  };
  bindPlaidConnect();

  const numericValue = (raw) => {
    if (raw === null || raw === undefined) return Number.NEGATIVE_INFINITY;
    const cleaned = String(raw).trim().replace(/[$,%]/g, "").replace(/,/g, "");
    const numeric = Number.parseFloat(cleaned);
    return Number.isFinite(numeric) ? numeric : Number.NEGATIVE_INFINITY;
  };

  const sortRows = (table, key, direction) => {
    const tbody = table.querySelector("tbody");
    if (!tbody) return;
    const columnIndex = Number.parseInt(table.dataset.sortIndex || "0", 10);
    const rows = [...tbody.querySelectorAll("tr")];
    rows.sort((a, b) => {
      const aCell = a.querySelectorAll("td")[columnIndex];
      const bCell = b.querySelectorAll("td")[columnIndex];
      const aValue = aCell?.dataset?.sortValue ?? aCell?.textContent?.trim() ?? "";
      const bValue = bCell?.dataset?.sortValue ?? bCell?.textContent?.trim() ?? "";
      const aNum = numericValue(aValue);
      const bNum = numericValue(bValue);
      const useNumber = Number.isFinite(aNum) && Number.isFinite(bNum);
      let result = 0;
      if (useNumber) {
        result = aNum - bNum;
      } else if (aValue < bValue) {
        result = -1;
      } else if (aValue > bValue) {
        result = 1;
      }
      return direction === "asc" ? result : -result;
    });
    rows.forEach((row) => tbody.appendChild(row));
  };

  const bindSortableTables = (root = document) => root.querySelectorAll("table[data-sortable-table]").forEach((table) => {
    if (table.dataset.sortableBound === "1") return;
    table.dataset.sortableBound = "1";
    const headers = [...table.querySelectorAll("th[data-sort-key]")];
    const tBody = table.querySelector("tbody");
    if (!headers.length || !tBody) return;

    headers.forEach((header) => {
      const key = header.dataset.sortKey;
      if (!key) return;
      const columnIndex = [...header.parentElement.children].indexOf(header);
      const button = document.createElement("button");
      button.type = "button";
      button.className = "sort-toggle";
      button.textContent = header.dataset.label || header.textContent.trim();
      button.setAttribute("aria-label", `Sort by ${header.dataset.label || header.textContent.trim()}`);
      button.addEventListener("click", () => {
        const current = table.dataset.sortKey;
        const nextDirection = current === key && table.dataset.sortDirection === "asc" ? "desc" : "asc";
        table.dataset.sortKey = key;
        table.dataset.sortDirection = nextDirection;
        table.dataset.sortIndex = String(columnIndex);
        sortRows(table, key, nextDirection);
        headers.forEach((cell) => {
          const active = cell.dataset.sortKey === key;
          cell.classList.toggle("sorted", active);
          cell.setAttribute("aria-sort", active ? (nextDirection === "asc" ? "ascending" : "descending") : "none");
        });
      });
      header.innerHTML = "";
      header.appendChild(button);
    });
  });
  bindSortableTables();

  const bindDeleteButtons = (root = document) => root.querySelectorAll("[data-delete]").forEach((button) => {
    if (button.dataset.deleteBound === "1") return;
    button.dataset.deleteBound = "1";
    button.addEventListener("click", () => {
      if (!confirm("Delete this trade permanently?")) return;
      const form = document.createElement("form"); form.method = "post"; form.action = button.dataset.delete;
      document.body.appendChild(form); form.submit();
    });
  });
  bindDeleteButtons();

  const commandPalette = document.querySelector(".command-palette");
  const commandInput = document.querySelector(".command-input");
  const commandItems = [...document.querySelectorAll(".command-item")];
  const commandEmpty = document.querySelector(".command-empty");
  const openCommands = () => {
    if (!commandPalette || !commandInput) return;
    commandPalette.hidden = false;
    commandInput.value = "";
    commandItems.forEach((item) => item.hidden = false);
    if (commandEmpty) commandEmpty.hidden = true;
    window.setTimeout(() => commandInput.focus(), 0);
  };
  const closeCommands = () => {
    if (!commandPalette) return;
    commandPalette.classList.remove("is-open");
    window.setTimeout(() => {
      if (!commandPalette.classList.contains("is-open")) commandPalette.hidden = true;
    }, 190);
  };
  document.querySelectorAll(".command-trigger").forEach((button) => {
    button.addEventListener("click", () => {
      openCommands();
      window.requestAnimationFrame(() => commandPalette?.classList.add("is-open"));
    });
  });
  document.querySelectorAll("[data-command-close]").forEach((item) => {
    item.addEventListener("click", closeCommands);
  });
  document.addEventListener("keydown", (event) => {
    const isShortcut = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k";
    if (isShortcut) {
      event.preventDefault();
      openCommands();
      window.requestAnimationFrame(() => commandPalette?.classList.add("is-open"));
    } else if (event.key === "Escape") {
      closeCommands();
    } else if (event.key === "Enter" && !commandPalette?.hidden && document.activeElement === commandInput) {
      const first = commandItems.find((item) => !item.hidden);
      if (first) window.location.href = first.href;
    }
  });
  if (commandInput) {
    commandInput.addEventListener("input", () => {
      const query = commandInput.value.trim().toLowerCase();
      let visible = 0;
      commandItems.forEach((item) => {
        const match = !query || item.dataset.commandText.includes(query);
        item.hidden = !match;
        if (match) visible += 1;
      });
      if (commandEmpty) commandEmpty.hidden = visible !== 0;
    });
  }

  const bindPerformanceChart = (panel) => {
    if (!panel) return;
    const svg = panel.querySelector(".performance-chart");
    if (!svg) return;
    const points = JSON.parse(svg.dataset.points || "[]");
    const hitArea = svg.querySelector(".perf-hit-area");
    const hoverX = svg.querySelector(".perf-hover-x");
    const hoverY = svg.querySelector(".perf-hover-y");
    const hoverDot = svg.querySelector(".perf-hover-dot");
    if (!points.length || !hitArea || !hoverX || !hoverY || !hoverDot) return;

    let tooltip = panel.querySelector(".perf-tooltip");
    if (!tooltip) {
      tooltip = document.createElement("div");
      tooltip.className = "perf-tooltip";
      panel.appendChild(tooltip);
    }

    const svgPointFromEvent = (event) => {
      const source = event.touches?.[0] || event;
      const point = svg.createSVGPoint();
      point.x = source.clientX;
      point.y = source.clientY;
      const matrix = svg.getScreenCTM();
      if (!matrix) return { x: 0, y: 0 };
      return point.matrixTransform(matrix.inverse());
    };

    const setHover = (event) => {
      const rect = svg.getBoundingClientRect();
      const box = svg.viewBox.baseVal;
      const cursor = svgPointFromEvent(event);
      const x = cursor.x;
      let nearest = points[0];
      for (const point of points) {
        if (Math.abs(point.x - x) < Math.abs(nearest.x - x)) nearest = point;
      }
      hoverX.setAttribute("y1", nearest.y);
      hoverX.setAttribute("y2", nearest.y);
      hoverY.setAttribute("x1", nearest.x);
      hoverY.setAttribute("x2", nearest.x);
      hoverDot.setAttribute("cx", nearest.x);
      hoverDot.setAttribute("cy", nearest.y);
      panel.classList.add("is-hovering");

      const pageX = (nearest.x / box.width) * rect.width;
      const pageY = (nearest.y / box.height) * rect.height;
      tooltip.innerHTML = `<b>${nearest.display}</b><span>${nearest.label}</span>`;
      tooltip.style.left = `${Math.min(Math.max(pageX + 14, 10), rect.width - 150)}px`;
      tooltip.style.top = `${Math.max(pageY - 48, 10)}px`;
      if (event.type === "touchmove") event.preventDefault();
    };
    const clearHover = () => panel.classList.remove("is-hovering");
    svg.addEventListener("mousemove", setHover);
    svg.addEventListener("mouseenter", setHover);
    svg.addEventListener("mouseleave", clearHover);
    svg.addEventListener("touchstart", setHover, { passive: true });
    svg.addEventListener("touchmove", setHover, { passive: false });
    svg.addEventListener("touchend", clearHover);
  };

  const bindCapitalUsageCharts = (root = document) => {
    root.querySelectorAll(".capital-panel").forEach((panel) => {
      const svg = panel.querySelector(".capital-chart");
      if (!svg || svg.dataset.hoverBound === "1") return;
      const points = JSON.parse(svg.dataset.points || "[]");
      const hitArea = svg.querySelector(".capital-hit-area");
      const hoverX = svg.querySelector(".perf-hover-x");
      const hoverY = svg.querySelector(".perf-hover-y");
      const hoverDot = svg.querySelector(".perf-hover-dot");
      if (!points.length || !hitArea || !hoverX || !hoverY || !hoverDot) return;
      svg.dataset.hoverBound = "1";

      let tooltip = panel.querySelector(".perf-tooltip");
      if (!tooltip) {
        tooltip = document.createElement("div");
        tooltip.className = "perf-tooltip";
        panel.appendChild(tooltip);
      }

      const setHover = (event) => {
        const rect = svg.getBoundingClientRect();
        const box = svg.viewBox.baseVal;
        const x = ((event.clientX - rect.left) / rect.width) * box.width;
        let nearest = points[0];
        for (const point of points) {
          if (Math.abs(point.x - x) < Math.abs(nearest.x - x)) nearest = point;
        }
        hoverX.setAttribute("y1", nearest.y);
        hoverX.setAttribute("y2", nearest.y);
        hoverY.setAttribute("x1", nearest.x);
        hoverY.setAttribute("x2", nearest.x);
        hoverDot.setAttribute("cx", nearest.x);
        hoverDot.setAttribute("cy", nearest.y);
        panel.classList.add("is-hovering");

        const pageX = (nearest.x / box.width) * rect.width;
        const pageY = (nearest.y / box.height) * rect.height;
        const display = activeLanguage === "zh" ? translatedText(nearest.display) || nearest.display : nearest.display;
        tooltip.innerHTML = `<b>${display}</b><span>${nearest.label}</span>`;
        tooltip.style.left = `${Math.min(Math.max(pageX + 14, 10), rect.width - 150)}px`;
        tooltip.style.top = `${Math.max(pageY - 48, 10)}px`;
      };
      const clearHover = () => panel.classList.remove("is-hovering");
      hitArea.addEventListener("mousemove", setHover);
      hitArea.addEventListener("mouseleave", clearHover);
    });
  };

  const mergeSearchParams = (target, source) => {
    const keys = new Set();
    source.searchParams.forEach((_value, key) => keys.add(key));
    keys.forEach((key) => target.searchParams.delete(key));
    source.searchParams.forEach((value, key) => target.searchParams.append(key, value));
  };

  const performanceFetchUrl = (url) => {
    const incoming = new URL(url, window.location.href);
    const next = new URL(window.location.href);
    mergeSearchParams(next, incoming);
    const currency = localStorage.getItem("optionLedgerCurrency") || "usd";
    if (currency === "rmb") next.searchParams.set("currency", "rmb");
    else next.searchParams.delete("currency");
    next.pathname = "/performance";
    return next;
  };

  const loadPerformancePanel = (url) => {
    const currentPanel = document.querySelector(".performance-panel");
    if (!currentPanel) return;
    currentPanel.classList.add("is-loading");
    const requestUrl = performanceFetchUrl(url);
    fetch(requestUrl, { headers: { "X-Requested-With": "fetch" }, cache: "no-store" })
      .then((response) => response.ok ? response.text() : Promise.reject())
      .then((html) => {
        const template = document.createElement("template");
        template.innerHTML = html.trim();
        const nextPanel = template.content.querySelector(".performance-panel");
        if (!nextPanel) return;
        currentPanel.replaceWith(nextPanel);
        const pageUrl = new URL(requestUrl);
        pageUrl.pathname = window.location.pathname;
        window.history.replaceState(null, "", `${pageUrl.pathname}${pageUrl.search}`);
        bindPerformanceChart(nextPanel);
        applyLanguage(nextPanel);
        loadStrategyPanel(requestUrl);
      })
      .catch(() => currentPanel.classList.remove("is-loading"));
  };

  const loadStrategyPanel = (url) => {
    const currentPanel = document.querySelector(".strategy-panel");
    if (!currentPanel) return;
    currentPanel.classList.add("is-loading");
    const requestUrl = new URL(url, window.location.href);
    const currency = localStorage.getItem("optionLedgerCurrency") || "usd";
    if (currency === "rmb") requestUrl.searchParams.set("currency", "rmb");
    else requestUrl.searchParams.delete("currency");
    requestUrl.pathname = "/strategy-performance";
    fetch(requestUrl, { headers: { "X-Requested-With": "fetch" }, cache: "no-store" })
      .then((response) => response.ok ? response.text() : Promise.reject())
      .then((html) => {
        const template = document.createElement("template");
        template.innerHTML = html.trim();
        const nextPanel = template.content.querySelector(".strategy-panel");
        if (nextPanel) {
          currentPanel.replaceWith(nextPanel);
          applyLanguage(nextPanel);
        }
      })
      .catch(() => currentPanel.classList.remove("is-loading"));
  };

  const loadCapitalUsagePanel = (url) => {
    const currentPanel = document.querySelector(".capital-panel");
    if (!currentPanel) return;
    currentPanel.classList.add("is-loading");
    const requestUrl = new URL(url, window.location.href);
    const currency = localStorage.getItem("optionLedgerCurrency") || "usd";
    if (currency === "rmb") requestUrl.searchParams.set("currency", "rmb");
    else requestUrl.searchParams.delete("currency");
    requestUrl.pathname = "/capital-usage";
    fetch(requestUrl, { headers: { "X-Requested-With": "fetch" }, cache: "no-store" })
      .then((response) => response.ok ? response.text() : Promise.reject())
      .then((html) => {
        const template = document.createElement("template");
        template.innerHTML = html.trim();
        const nextPanel = template.content.querySelector(".capital-panel");
        if (!nextPanel) return;
        currentPanel.replaceWith(nextPanel);
        bindCapitalUsageCharts(nextPanel.parentElement || document);
        applyLanguage(nextPanel);
      })
      .catch(() => currentPanel.classList.remove("is-loading"));
  };

  const loadPerformanceControls = (url) => {
    const currentControls = document.querySelector(".dashboard-filter-range > .perf-controls, .dashboard-performance-card > .perf-controls");
    if (!currentControls) return;
    const requestUrl = new URL(url, window.location.href);
    const currency = localStorage.getItem("optionLedgerCurrency") || "usd";
    if (currency === "rmb") requestUrl.searchParams.set("currency", "rmb");
    else requestUrl.searchParams.delete("currency");
    requestUrl.pathname = "/performance-controls";
    fetch(requestUrl, { headers: { "X-Requested-With": "fetch" }, cache: "no-store" })
      .then((response) => response.ok ? response.text() : Promise.reject())
      .then((html) => {
        const template = document.createElement("template");
        template.innerHTML = html.trim();
        const nextControls = template.content.querySelector(".perf-controls");
        if (nextControls) {
          currentControls.replaceWith(nextControls);
          applyLanguage(nextControls);
        }
      });
  };

  const loadDashboardCharts = (url) => {
    loadPerformancePanel(url);
    loadCapitalUsagePanel(url);
    loadPerformanceControls(url);
  };

  const loadDashboardView = (url) => {
    const currentLayout = document.querySelector("[data-dashboard-layout]");
    const currentFilters = document.querySelector(".dashboard-filter-panel");
    if (!currentLayout || !currentFilters || window.location.pathname !== "/") return;
    const requestUrl = new URL(url, window.location.href);
    requestUrl.pathname = "/";
    const currency = localStorage.getItem("optionLedgerCurrency") || "usd";
    if (currency === "rmb") requestUrl.searchParams.set("currency", "rmb");
    else requestUrl.searchParams.delete("currency");
    currentLayout.classList.add("is-loading");
    currentFilters.classList.add("is-loading");
    fetch(requestUrl, { headers: { "X-Requested-With": "fetch" }, cache: "no-store" })
      .then((response) => response.ok ? response.text() : Promise.reject())
      .then((html) => {
        const page = new DOMParser().parseFromString(html, "text/html");
        const nextLayout = page.querySelector("[data-dashboard-layout]");
        const nextFilters = page.querySelector(".dashboard-filter-panel");
        if (!nextLayout || !nextFilters) return;
        currentFilters.replaceWith(nextFilters);
        currentLayout.replaceWith(nextLayout);
        window.history.replaceState(null, "", `${requestUrl.pathname}${requestUrl.search}`);
        bindPerformanceChart(nextLayout.querySelector(".performance-panel"));
        bindCapitalUsageCharts(nextLayout);
        bindDashboardSplitter();
        bindOptionPositionGroups();
        applyLanguage(nextFilters);
        applyLanguage(nextLayout);
      })
      .catch(() => {
        currentLayout.classList.remove("is-loading");
        currentFilters.classList.remove("is-loading");
      });
  };

  document.addEventListener("click", (event) => {
    const dashboardRangeLink = event.target.closest(".dashboard-filter-range a[href]");
    if (dashboardRangeLink && document.querySelector("[data-dashboard-layout]")) {
      event.preventDefault();
      loadDashboardCharts(dashboardRangeLink.href);
      return;
    }
    const link = event.target.closest(".performance-panel .perf-tab[href], .dashboard-performance-card a[href]");
    if (!link) return;
    event.preventDefault();
    loadDashboardCharts(link.href);
  });

  document.addEventListener("submit", (event) => {
    const dashboardRangeForm = event.target.closest(".dashboard-filter-range form");
    if (dashboardRangeForm && document.querySelector("[data-dashboard-layout]")) {
      event.preventDefault();
      const target = new URL(dashboardRangeForm.action || "/", window.location.href);
      target.search = new URLSearchParams(new FormData(dashboardRangeForm)).toString();
      loadDashboardCharts(target);
      return;
    }
    const form = event.target.closest(".dashboard-performance-card form");
    if (!form) return;
    event.preventDefault();
    const params = new URLSearchParams(new FormData(form));
    const url = `/?${params.toString()}`;
    loadPerformancePanel(url);
    loadCapitalUsagePanel(url);
    loadPerformanceControls(url);
  });

  document.addEventListener("change", (event) => {
    const dashboardField = event.target.closest("[data-dashboard-filter] input[type='checkbox']");
    if (dashboardField) {
      const form = dashboardField.form;
      if (!form) return;
      const params = new URLSearchParams(new FormData(form));
      loadDashboardView(`/?${params.toString()}`);
      return;
    }
    const field = event.target.closest(".broker-filter-inline input[type='checkbox']");
    if (!field || field.name !== "perf_broker") return;
    const form = field.form;
    if (!form) return;
    const params = new URLSearchParams(new FormData(form));
    const url = `/?${params.toString()}`;
    loadPerformancePanel(url);
    loadCapitalUsagePanel(url);
    loadPerformanceControls(url);
  });

  bindPerformanceChart(document.querySelector(".performance-panel"));
  bindCapitalUsageCharts();

  const sectionFetchUrl = (url, pathname) => {
    const incoming = new URL(url, window.location.href);
    const next = new URL(window.location.href);
    mergeSearchParams(next, incoming);
    const currency = localStorage.getItem("optionLedgerCurrency") || "usd";
    if (currency === "rmb") next.searchParams.set("currency", "rmb");
    else next.searchParams.delete("currency");
    next.pathname = pathname;
    return next;
  };

  const loadCalendarPanel = (url) => {
    const currentPanel = document.querySelector(".calendar-panel");
    if (!currentPanel) return;
    currentPanel.classList.add("is-loading");
    const requestUrl = sectionFetchUrl(url, "/calendar");
    fetch(requestUrl, { headers: { "X-Requested-With": "fetch" }, cache: "no-store" })
      .then((response) => response.ok ? response.text() : Promise.reject())
      .then((html) => {
        const template = document.createElement("template");
        template.innerHTML = html.trim();
        const nextPanel = template.content.querySelector(".calendar-panel");
        if (!nextPanel) return;
        currentPanel.replaceWith(nextPanel);
        const pageUrl = new URL(requestUrl);
        pageUrl.pathname = "/";
        window.history.replaceState(null, "", `${pageUrl.pathname}${pageUrl.search}`);
        applyLanguage(nextPanel);
      })
      .catch(() => currentPanel.classList.remove("is-loading"));
  };

  document.addEventListener("click", (event) => {
    const link = event.target.closest(".calendar-panel a[href]");
    if (!link) return;
    event.preventDefault();
    loadCalendarPanel(link.href);
  });

  document.addEventListener("change", (event) => {
    const field = event.target.closest(".calendar-panel select, .calendar-panel .broker-filter-inline input[type='checkbox']");
    if (!field) return;
    const form = field.form;
    if (!form) return;
    const params = new URLSearchParams(new FormData(form));
    loadCalendarPanel(`/?${params.toString()}`);
  });

  const setConnectedInterval = (node, callback, delay) => {
    const interval = window.setInterval(() => {
      if (!node.isConnected) {
        window.clearInterval(interval);
        return;
      }
      callback();
    }, delay);
    return interval;
  };

  const bindJin10Feed = () => {
    const feed = document.querySelector("[data-jin10-feed]");
    if (!feed) return;
    const seconds = Math.max(Number.parseInt(feed.dataset.refreshSeconds || "30", 10), 10);
    const refreshFeed = () => {
      feed.classList.add("is-loading");
      fetch("/market-news/data", { headers: { "X-Requested-With": "fetch" }, cache: "no-store" })
        .then((response) => response.ok ? response.text() : Promise.reject())
        .then((html) => {
          feed.innerHTML = html;
          applyLanguage(feed);
        })
        .catch(() => {})
        .finally(() => feed.classList.remove("is-loading"));
    };
    setConnectedInterval(feed, refreshFeed, seconds * 1000);
  };
  bindJin10Feed();

  const bindGreedyFearFeed = () => {
    const feed = document.querySelector("[data-greedyfear-feed]");
    if (!feed) return;
    const seconds = Math.max(Number.parseInt(feed.dataset.refreshSeconds || "300", 10), 60);
    const refreshFeed = () => {
      feed.classList.add("is-loading");
      fetch("/sentiment/data", { headers: { "X-Requested-With": "fetch" }, cache: "no-store" })
        .then((response) => response.ok ? response.text() : Promise.reject())
        .then((html) => {
          feed.innerHTML = html;
          applyLanguage(feed);
        })
        .catch(() => {})
        .finally(() => feed.classList.remove("is-loading"));
    };
    setConnectedInterval(feed, refreshFeed, seconds * 1000);
  };
  bindGreedyFearFeed();

  const bindOptionsCalculator = () => {
    const shell = document.querySelector("[data-options-calculator]");
    const form = document.querySelector("[data-options-calculator-form]");
    if (!shell || !form) return;
    const mode = form.querySelector("[data-calculator-mode]");
    const table = shell.querySelector("[data-calc-matrix]");
    let tableMode = "value";
    const numberValue = (name, fallback = 0) => {
      const field = form.elements[name] || shell.querySelector(`[name="${name}"]`);
      const value = Number.parseFloat(field?.value);
      return Number.isFinite(value) ? value : fallback;
    };
    const moneyText = (value) => {
      if (!Number.isFinite(value)) return "—";
      const sign = value < 0 ? "-" : "";
      return `${sign}$${Math.abs(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    };
    const pctText = (value) => Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "—";
    const normPdf = (x) => Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI);
    const normCdf = (x) => {
      const sign = x < 0 ? -1 : 1;
      const abs = Math.abs(x) / Math.sqrt(2);
      const t = 1 / (1 + 0.3275911 * abs);
      const erf = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-abs * abs);
      return 0.5 * (1 + sign * erf);
    };
    const bs = (type, spot, strike, days, iv, rate, dividend) => {
      const years = Math.max(days, 0) / 365;
      const sigma = Math.max(iv, 0.0001);
      if (years <= 0) {
        const intrinsic = type === "call" ? Math.max(0, spot - strike) : Math.max(0, strike - spot);
        const delta = type === "call" ? (spot > strike ? 1 : 0) : (spot < strike ? -1 : 0);
        return { price: intrinsic, delta, gamma: 0, theta: 0, vega: 0, rho: 0, intrinsic, extrinsic: 0 };
      }
      const sqrtT = Math.sqrt(years);
      const d1 = (Math.log(spot / strike) + (rate - dividend + 0.5 * sigma * sigma) * years) / (sigma * sqrtT);
      const d2 = d1 - sigma * sqrtT;
      const discountRate = Math.exp(-rate * years);
      const discountDividend = Math.exp(-dividend * years);
      const gamma = discountDividend * normPdf(d1) / (spot * sigma * sqrtT);
      const vega = spot * discountDividend * normPdf(d1) * sqrtT / 100;
      if (type === "call") {
        const price = spot * discountDividend * normCdf(d1) - strike * discountRate * normCdf(d2);
        const intrinsic = Math.max(0, spot - strike);
        return { price, delta: discountDividend * normCdf(d1), gamma, theta: 0, vega, rho: 0, intrinsic, extrinsic: Math.max(0, price - intrinsic) };
      }
      const price = strike * discountRate * normCdf(-d2) - spot * discountDividend * normCdf(-d1);
      const intrinsic = Math.max(0, strike - spot);
      return { price, delta: discountDividend * (normCdf(d1) - 1), gamma, theta: 0, vega, rho: 0, intrinsic, extrinsic: Math.max(0, price - intrinsic) };
    };
    const daysBetween = (from, to) => Math.max(0, Math.round((to - from) / 86400000));
    const expirationDate = () => {
      const value = form.elements.expiration?.value;
      const parsed = value ? new Date(`${value}T00:00:00`) : new Date();
      return Number.isNaN(parsed.getTime()) ? new Date() : parsed;
    };
    const todayDate = () => {
      const parsed = new Date(`${shell.dataset.today || new Date().toISOString().slice(0, 10)}T00:00:00`);
      return Number.isNaN(parsed.getTime()) ? new Date() : parsed;
    };
    const optionPrice = (spot, days) => {
      const calcMode = ["put_credit_spread", "call_credit_spread"].includes(mode?.value) ? mode.value : "single";
      const rate = numberValue("rate", 0) / 100;
      const dividend = numberValue("dividend", 0) / 100;
      if (calcMode !== "single") {
        const shortStrike = Math.max(numberValue("short_strike", numberValue("strike", spot)), 0.0001);
        const longStrike = Math.max(numberValue("long_strike", calcMode === "call_credit_spread" ? shortStrike + 5 : shortStrike - 5), 0.0001);
        const shortIv = numberValue("short_iv", numberValue("iv", 35)) / 100;
        const longIv = numberValue("long_iv", numberValue("iv", 35)) / 100;
        const spreadType = calcMode === "call_credit_spread" ? "call" : "put";
        return Math.max(0, bs(spreadType, spot, shortStrike, days, shortIv, rate, dividend).price - bs(spreadType, spot, longStrike, days, longIv, rate, dividend).price);
      }
      const type = form.elements.option_type?.value === "call" ? "call" : "put";
      const strike = Math.max(numberValue("strike", spot), 0.0001);
      const iv = numberValue("iv", 35) / 100;
      return Math.max(0, bs(type, spot, strike, days, iv, rate, dividend).price);
    };
    const syncSliderBounds = () => {
      const spot = Math.max(numberValue("spot", 100), 1);
      shell.querySelectorAll('[data-calc-slider="strike"],[data-calc-slider="short"],[data-calc-slider="long"]').forEach((slider) => {
        slider.min = String(Math.max(1, Math.floor(spot * 0.65)));
        slider.max = String(Math.max(2, Math.ceil(spot * 1.35)));
      });
    };
    const render = () => {
      const calcMode = ["put_credit_spread", "call_credit_spread"].includes(mode?.value) ? mode.value : "single";
      const type = form.elements.option_type?.value === "call" ? "call" : "put";
      const spot = Math.max(numberValue("spot", 100), 0.01);
      const strike = numberValue("strike", spot);
      const shortStrike = numberValue("short_strike", strike);
      const longStrike = numberValue("long_strike", calcMode === "call_credit_spread" ? shortStrike + 5 : Math.max(shortStrike - 5, 0.01));
      const credit = Math.max(numberValue("credit", 0), 0);
      const iv = numberValue("iv", 35);
      const shortIv = numberValue("short_iv", iv);
      const longIv = numberValue("long_iv", iv);
      const exp = expirationDate();
      const today = todayDate();
      const dte = daysBetween(today, exp);
      const currentPrice = optionPrice(spot, dte);
      const width = Math.abs(longStrike - shortStrike);
      const isSpread = calcMode !== "single";
      const spreadType = calcMode === "call_credit_spread" ? "call" : "put";
      const breakeven = isSpread ? (calcMode === "call_credit_spread" ? shortStrike + credit : shortStrike - credit) : (type === "call" ? strike + currentPrice : strike - currentPrice);
      const loss = isSpread ? Math.max(0, (width - credit) * 100) : currentPrice * 100;
      const profit = isSpread ? credit * 100 : Infinity;
      const delta = isSpread
        ? bs(spreadType, spot, shortStrike, dte, shortIv / 100, numberValue("rate", 0) / 100, numberValue("dividend", 0) / 100).delta - bs(spreadType, spot, longStrike, dte, longIv / 100, numberValue("rate", 0) / 100, numberValue("dividend", 0) / 100).delta
        : bs(type, spot, strike, dte, iv / 100, numberValue("rate", 0) / 100, numberValue("dividend", 0) / 100).delta;
      shell.querySelector("[data-calc-title]").textContent = isSpread ? (calcMode === "call_credit_spread" ? "Call Credit Spread" : "Put Credit Spread") : (type === "call" ? "Long Call" : "Long Put");
      shell.querySelector("[data-calc-spot]").textContent = moneyText(spot);
      shell.querySelector("[data-calc-dte]").textContent = `${dte} DTE`;
      shell.querySelector("[data-calc-strike-label]").textContent = moneyText(strike);
      shell.querySelector("[data-calc-short-label]").textContent = moneyText(shortStrike);
      shell.querySelector("[data-calc-long-label]").textContent = moneyText(longStrike);
      shell.querySelector("[data-calc-iv-label]").textContent = `${iv.toFixed(0)}%`;
      shell.querySelector("[data-calc-short-iv-label]").textContent = `${shortIv.toFixed(0)}%`;
      shell.querySelector("[data-calc-long-iv-label]").textContent = `${longIv.toFixed(0)}%`;
      shell.querySelector("[data-calc-range-label]").textContent = `±${numberValue("range", 10).toFixed(0)}%`;
      shell.querySelector('[data-calc-metric="value"]').textContent = moneyText(currentPrice);
      shell.querySelector('[data-calc-metric="profit"]').textContent = Number.isFinite(profit) ? moneyText(profit) : "Infinite";
      shell.querySelector('[data-calc-metric="loss"]').textContent = moneyText(loss);
      shell.querySelector('[data-calc-metric="breakeven"]').textContent = moneyText(breakeven);
      shell.querySelector('[data-calc-metric="delta"]').textContent = delta.toFixed(3);
      const rangePct = Math.max(numberValue("range", 10), 1) / 100;
      const rows = Array.from({ length: 13 }, (_, index) => spot * (1 + rangePct - (rangePct * 2 * index / 12)));
      const columnCount = 7;
      const dates = Array.from({ length: columnCount }, (_, index) => {
        const pct = columnCount === 1 ? 0 : index / (columnCount - 1);
        const date = new Date(today);
        date.setDate(date.getDate() + Math.round(dte * pct));
        return date;
      });
      const entry = isSpread ? credit : currentPrice;
      const header = `<thead><tr><th>Stock</th>${dates.map((date) => `<th>${date.toLocaleDateString("en-US", { month: "short", day: "numeric" })}</th>`).join("")}</tr></thead>`;
      const body = rows.map((rowSpot) => {
        const cells = dates.map((date) => {
          const daysLeft = daysBetween(today, date);
          const value = optionPrice(rowSpot, Math.max(dte - daysLeft, 0));
          const pl = isSpread ? (entry - value) * 100 : (value - entry) * 100;
          const plPct = entry ? pl / (entry * 100) : null;
          const display = tableMode === "pl" ? moneyText(pl) : tableMode === "pl_pct" ? pctText(plPct) : moneyText(value);
          const intensity = Math.min(1, Math.abs(pl) / Math.max(loss || 100, 100));
          const cls = pl >= 0 ? "gain" : "loss";
          return `<td class="${cls}" style="--heat:${intensity.toFixed(2)}">${display}</td>`;
        }).join("");
        return `<tr><th>${moneyText(rowSpot)}</th>${cells}</tr>`;
      }).join("");
      table.innerHTML = `${header}<tbody>${body}</tbody>`;
      applyLanguage(shell);
    };
    const syncMode = () => {
      const showSpread = mode && ["put_credit_spread", "call_credit_spread"].includes(mode.value);
      shell.querySelectorAll(".spread-field").forEach((field) => {
        field.hidden = !showSpread;
        field.classList.toggle("hidden", !showSpread);
      });
      shell.querySelectorAll(".single-field").forEach((field) => {
        field.hidden = showSpread;
        field.classList.toggle("hidden", showSpread);
      });
      syncSliderBounds();
      render();
    };
    shell.querySelectorAll("[data-calc-slider]").forEach((slider) => {
      slider.addEventListener("input", () => {
        const key = slider.dataset.calcSlider;
        if (key === "strike") form.elements.strike.value = slider.value;
        if (key === "short") form.elements.short_strike.value = slider.value;
        if (key === "long") form.elements.long_strike.value = slider.value;
        if (key === "iv") form.elements.iv.value = slider.value;
        if (key === "short_iv") form.elements.short_iv.value = slider.value;
        if (key === "long_iv") form.elements.long_iv.value = slider.value;
        render();
      });
    });
    form.addEventListener("input", (event) => {
      const field = event.target;
      if (!field.name) return;
      if (field.name === "spot") syncSliderBounds();
      if (field.name === "iv") {
        const ivSlider = shell.querySelector('[data-calc-slider="iv"]');
        if (ivSlider) ivSlider.value = field.value;
      }
      if (field.name === "short_iv") {
        const shortIvSlider = shell.querySelector('[data-calc-slider="short_iv"]');
        if (shortIvSlider) shortIvSlider.value = field.value;
      }
      if (field.name === "long_iv") {
        const longIvSlider = shell.querySelector('[data-calc-slider="long_iv"]');
        if (longIvSlider) longIvSlider.value = field.value;
      }
      render();
    });
    form.addEventListener("change", render);
    shell.querySelectorAll("[data-expiry-days]").forEach((button) => {
      button.addEventListener("click", () => {
        const next = todayDate();
        next.setDate(next.getDate() + Number.parseInt(button.dataset.expiryDays || "30", 10));
        form.elements.expiration.value = next.toISOString().slice(0, 10);
        shell.querySelectorAll("[data-expiry-days]").forEach((item) => item.classList.toggle("active", item === button));
        render();
      });
    });
    shell.querySelectorAll("[data-calc-table-mode]").forEach((button) => {
      button.addEventListener("click", () => {
        tableMode = button.dataset.calcTableMode || "value";
        shell.querySelectorAll("[data-calc-table-mode]").forEach((item) => item.classList.toggle("active", item === button));
        render();
      });
    });
    mode?.addEventListener("change", syncMode);
    syncMode();
  };
  bindOptionsCalculator();

  const bindPortfolioPie = () => {
    document.querySelectorAll(".portfolio-pie-card").forEach((card) => {
      const slices = Array.from(card.querySelectorAll("[data-pie-slice]"));
      const rows = Array.from(card.querySelectorAll("[data-pie-legend]"));
      const labelNode = card.querySelector("[data-pie-center-label]");
      const valueNode = card.querySelector("[data-pie-center-value]");
      const defaultLabel = labelNode?.textContent || "Allocation";
      const defaultValue = valueNode?.textContent || "";
      const setActive = (key) => {
        const activeSlice = slices.find((slice) => slice.dataset.pieSlice === key);
        const label = activeSlice?.dataset.pieLabel || defaultLabel;
        const share = activeSlice?.dataset.pieShare || defaultValue;
        card.classList.toggle("is-interacting", Boolean(key));
        slices.forEach((slice) => {
          const active = slice.dataset.pieSlice === key;
          slice.classList.toggle("is-active", active);
          slice.classList.toggle("is-muted", Boolean(key) && !active);
        });
        rows.forEach((row) => {
          const active = row.dataset.pieLegend === key;
          row.classList.toggle("is-active", active);
          row.classList.toggle("is-muted", Boolean(key) && !active);
        });
        const displayLabel = activeLanguage === "zh" ? translatedText(label) || label : label;
        if (labelNode) labelNode.textContent = displayLabel;
        if (valueNode) valueNode.textContent = share;
      };
      const clearActive = () => setActive("");
      slices.forEach((slice) => {
        const key = slice.dataset.pieSlice || "";
        slice.addEventListener("mouseenter", () => setActive(key));
        slice.addEventListener("focus", () => setActive(key));
        slice.addEventListener("mouseleave", clearActive);
        slice.addEventListener("blur", clearActive);
      });
      rows.forEach((row) => {
        const key = row.dataset.pieLegend || "";
        row.addEventListener("mouseenter", () => setActive(key));
        row.addEventListener("focus", () => setActive(key));
        row.addEventListener("mouseleave", clearActive);
        row.addEventListener("blur", clearActive);
      });
    });
  };
  bindPortfolioPie();

  const bindPortfolioBenchmarks = (root = document) => {
    root.querySelectorAll(".portfolio-benchmark-controls").forEach((controls) => {
      if (controls.dataset.benchmarkBound === "1") return;
      controls.dataset.benchmarkBound = "1";
      const chartColumn = controls.parentElement?.parentElement;
      const chart = chartColumn?.querySelector("[data-portfolio-chart]");
      if (!chart) return;
      if (!chart.id) chart.id = "portfolio-performance-chart";
      const toggles = Array.from(controls.querySelectorAll("[data-portfolio-overlay]"))
        .map((toggle) => [toggle, toggle.dataset.portfolioOverlay]);
      toggles.forEach(([toggle, key]) => {
        if (!toggle) return;
        toggle.addEventListener("change", () => {
          const url = new URL(location.href);
          url.searchParams.delete("benchmark");
          toggles.forEach(([candidate, candidateKey]) => {
            if (candidate?.checked && candidateKey) url.searchParams.append("benchmark", candidateKey);
          });
          loadPortfolioChartRange(url.href);
        });
      });
      const sync = () => {
        toggles.forEach(([toggle, key]) => {
          if (!toggle) return;
          chart.classList.toggle(`hide-benchmark-${key}`, !toggle.checked);
          toggle.setAttribute("aria-controls", chart.id);
        });
      };
      toggles.forEach(([toggle]) => toggle?.addEventListener("change", sync));
      sync();
    });
  };
  bindPortfolioBenchmarks();

  const bindPortfolioChart = (root = document) => {
    root.querySelectorAll("[data-portfolio-chart]").forEach((chart) => {
      if (chart.dataset.portfolioBound === "1") return;
      chart.dataset.portfolioBound = "1";
      let points = [];
      try {
        points = JSON.parse(chart.dataset.portfolioPoints || "[]");
      } catch {
        points = [];
      }
      if (!points.length) return;
      const baseViewBox = {
        width: chart.viewBox.baseVal.width,
        height: chart.viewBox.baseVal.height
      };
      const plotTop = 18;
      const plotBottom = 24;
      const basePlotHeight = baseViewBox.height - plotTop - plotBottom;
      points.forEach((point) => { point.baseY = Number(point.y); });
      const yAttributes = Array.from(chart.querySelectorAll("line[y1], circle[cy]")).map((node) => ({
        node,
        y1: node.hasAttribute("y1") ? Number(node.getAttribute("y1")) : null,
        y2: node.hasAttribute("y2") ? Number(node.getAttribute("y2")) : null,
        cy: node.hasAttribute("cy") ? Number(node.getAttribute("cy")) : null
      }));
      const pointAttributes = Array.from(chart.querySelectorAll("polygon[points], polyline[points]")).map((node) => ({
        node,
        values: (node.getAttribute("points") || "").trim().split(/\s+/).map((pair) => pair.split(",").map(Number))
      }));
      const yLabels = Array.from(chart.querySelectorAll(".portfolio-y-label")).map((node) => ({
        node,
        y: Number(node.getAttribute("y"))
      }));
      const hitArea = chart.querySelector(".portfolio-hit-area");
      const profitGradients = Array.from(chart.querySelectorAll("#portfolioProfitFill, #portfolioLineGradient"));
      const scaleChartY = (value, scale) => plotTop + (value - plotTop) * scale;
      const resizeChartGeometry = () => {
        const rect = chart.getBoundingClientRect();
        const desktop = window.matchMedia("(min-width: 981px)").matches;
        const targetHeight = desktop && rect.width > 0
          ? Math.max(baseViewBox.height, baseViewBox.width * rect.height / rect.width)
          : baseViewBox.height;
        const targetPlotHeight = targetHeight - plotTop - plotBottom;
        const scale = targetPlotHeight / basePlotHeight;
        chart.setAttribute("viewBox", `0 0 ${baseViewBox.width} ${targetHeight}`);
        yAttributes.forEach((item) => {
          if (item.y1 !== null) item.node.setAttribute("y1", scaleChartY(item.y1, scale));
          if (item.y2 !== null) item.node.setAttribute("y2", scaleChartY(item.y2, scale));
          if (item.cy !== null) item.node.setAttribute("cy", scaleChartY(item.cy, scale));
        });
        pointAttributes.forEach((item) => {
          item.node.setAttribute("points", item.values.map(([x, y]) => `${x},${scaleChartY(y, scale)}`).join(" "));
        });
        yLabels.forEach((item) => {
          item.node.setAttribute("y", scaleChartY(item.y - 4, scale) + 4);
        });
        if (hitArea) {
          hitArea.setAttribute("y", plotTop);
          hitArea.setAttribute("height", targetPlotHeight);
        }
        profitGradients.forEach((gradient) => gradient.setAttribute("y2", targetHeight - plotBottom));
        points.forEach((point) => { point.y = scaleChartY(point.baseY, scale); });
      };
      resizeChartGeometry();
      if (window.ResizeObserver) {
        const chartResizeObserver = new ResizeObserver(resizeChartGeometry);
        chartResizeObserver.observe(chart);
        chart._portfolioResizeObserver = chartResizeObserver;
      } else {
        window.addEventListener("resize", resizeChartGeometry);
      }
      const line = chart.querySelector(".portfolio-hover-line");
      const dot = chart.querySelector(".portfolio-hover-dot");
      const hero = chart.closest(".portfolio-hero");
      const liveValue = hero?.querySelector("[data-portfolio-live-value]");
      const liveChange = hero?.querySelector("[data-portfolio-live-change]");
      const tooltip = document.createElement("div");
      tooltip.className = "portfolio-tooltip";
      tooltip.innerHTML = '<b class="portfolio-tooltip-title"></b><span class="portfolio-tooltip-date"></span><div class="portfolio-tooltip-rows"></div>';
      chart.insertAdjacentElement("afterend", tooltip);

      const nearestPoint = (clientX) => {
        const rect = chart.getBoundingClientRect();
        const viewBox = chart.viewBox.baseVal;
        const svgX = ((clientX - rect.left) / Math.max(rect.width, 1)) * viewBox.width;
        return points.reduce((best, point) => (
          Math.abs(point.x - svgX) < Math.abs(best.x - svgX) ? point : best
        ), points[0]);
      };
      const positionTooltip = (point, event) => {
        const chartRect = chart.getBoundingClientRect();
        const viewBox = chart.viewBox.baseVal;
        const x = (point.x / viewBox.width) * chartRect.width;
        const y = (point.y / viewBox.height) * chartRect.height;
        tooltip.querySelector(".portfolio-tooltip-title").textContent = point.display || "";
        tooltip.querySelector(".portfolio-tooltip-date").textContent = point.date || "";
        const rows = tooltip.querySelector(".portfolio-tooltip-rows");
        if (rows) {
          rows.innerHTML = "";
          (point.comparisons || []).forEach((item) => {
            if (item.key && chart.classList.contains(`hide-benchmark-${item.key}`)) return;
            const row = document.createElement("div");
            row.className = `portfolio-tooltip-row ${item.key || ""}`;
            const label = document.createElement("span");
            label.textContent = activeLanguage === "zh" ? translatedText(item.label) || item.label || "" : item.label || "";
            const value = document.createElement("b");
            value.textContent = item.pct || "--";
            row.append(label, value);
            rows.appendChild(row);
          });
        }
        const offsetParentRect = tooltip.offsetParent?.getBoundingClientRect() || chartRect;
        const chartOffsetX = chartRect.left - offsetParentRect.left;
        const chartOffsetY = chartRect.top - offsetParentRect.top;
        const left = chartOffsetX + Math.min(Math.max(x + 14, 8), chartRect.width - tooltip.offsetWidth - 8);
        const top = chartOffsetY + Math.min(Math.max(y - 44, 8), chartRect.height - tooltip.offsetHeight - 8);
        tooltip.style.left = `${left}px`;
        tooltip.style.top = `${top}px`;
        if (event?.type === "touchmove") event.preventDefault();
      };
      const setLiveSummary = (point) => {
        if (liveValue) liveValue.textContent = point.display || liveValue.dataset.defaultValue || "";
        if (liveChange) {
          const changeText = `${point.changeDisplay || ""} (${point.changePctDisplay || "-"})`;
          liveChange.textContent = changeText;
          liveChange.classList.remove("positive", "negative");
          liveChange.classList.add(point.changeClass || "positive");
        }
      };
      const resetLiveSummary = () => {
        if (liveValue) liveValue.textContent = liveValue.dataset.defaultValue || liveValue.textContent;
        if (liveChange) {
          liveChange.textContent = liveChange.dataset.defaultValue || liveChange.textContent;
          liveChange.classList.remove("positive", "negative");
          liveChange.classList.add(liveChange.dataset.defaultClass || "positive");
        }
      };
      const showPoint = (event) => {
        const source = event.touches?.[0] || event;
        const point = nearestPoint(source.clientX);
        if (line) {
          line.setAttribute("x1", point.x);
          line.setAttribute("x2", point.x);
        }
        if (dot) {
          dot.setAttribute("cx", point.x);
          dot.setAttribute("cy", point.y);
          dot.classList.remove("positive", "negative");
          dot.classList.add(point.changeClass || "positive");
        }
        chart.classList.add("is-hovering");
        tooltip.classList.add("is-visible");
        positionTooltip(point, event);
        setLiveSummary(point);
      };
      const hidePoint = () => {
        chart.classList.remove("is-hovering");
        tooltip.classList.remove("is-visible");
        resetLiveSummary();
      };
      chart.addEventListener("mousemove", showPoint);
      chart.addEventListener("mouseenter", showPoint);
      chart.addEventListener("mouseleave", hidePoint);
      chart.addEventListener("touchstart", showPoint, { passive: true });
      chart.addEventListener("touchmove", showPoint, { passive: false });
      chart.addEventListener("touchend", hidePoint);
    });
  };
  bindPortfolioChart();

  const syncPortfolioAccountSelection = (accountKey = null) => {
    const selected = accountKey === null
      ? (new URL(location.href).searchParams.get("account") || "")
      : accountKey;
    document.querySelectorAll("[data-portfolio-account]").forEach((button) => {
      const active = Boolean(selected) && button.dataset.portfolioAccount === selected;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
  };
  syncPortfolioAccountSelection();

  let portfolioChartRequest = null;
  const loadPortfolioChartRange = async (url, pushHistory = true) => {
    const currentColumn = document.querySelector("[data-portfolio-chart-column]");
    if (!currentColumn) return;
    portfolioChartRequest?.abort();
    portfolioChartRequest = new AbortController();
    currentColumn.classList.add("is-loading");
    currentColumn.setAttribute("aria-busy", "true");
    try {
      const response = await fetch(url, {
        headers: { "X-Requested-With": "fetch" },
        cache: "no-store",
        signal: portfolioChartRequest.signal
      });
      if (!response.ok) throw new Error(`Chart request failed: ${response.status}`);
      const page = new DOMParser().parseFromString(await response.text(), "text/html");
      const nextColumn = page.querySelector("[data-portfolio-chart-column]");
      if (!nextColumn) throw new Error("Chart response is missing the chart region.");
      const currentLiveValue = document.querySelector("[data-portfolio-live-value]");
      const nextLiveValue = page.querySelector("[data-portfolio-live-value]");
      if (currentLiveValue && nextLiveValue) {
        currentLiveValue.textContent = nextLiveValue.textContent;
        currentLiveValue.dataset.defaultValue = nextLiveValue.dataset.defaultValue || nextLiveValue.textContent;
      }
      const currentLiveLabel = document.querySelector("[data-portfolio-live-label]");
      const nextLiveLabel = page.querySelector("[data-portfolio-live-label]");
      if (currentLiveLabel && nextLiveLabel) {
        currentLiveLabel.textContent = nextLiveLabel.textContent;
        currentLiveLabel.dataset.defaultValue = nextLiveLabel.dataset.defaultValue || nextLiveLabel.textContent;
      }
      const currentLiveChange = document.querySelector("[data-portfolio-live-change]");
      const nextLiveChange = page.querySelector("[data-portfolio-live-change]");
      if (currentLiveChange && nextLiveChange) {
        currentLiveChange.textContent = nextLiveChange.textContent;
        currentLiveChange.className = nextLiveChange.className;
        currentLiveChange.dataset.defaultValue = nextLiveChange.dataset.defaultValue || nextLiveChange.textContent;
        currentLiveChange.dataset.defaultClass = nextLiveChange.dataset.defaultClass || "";
      }
      currentColumn.querySelector("[data-portfolio-chart]")?._portfolioResizeObserver?.disconnect();
      const replacement = document.importNode(nextColumn, true);
      currentColumn.replaceWith(replacement);
      applyLanguage(replacement);
      bindPortfolioBenchmarks(replacement);
      bindPortfolioChart(replacement);
      if (pushHistory) history.pushState({ portfolioChartRange: true }, "", url);
      syncPortfolioAccountSelection(new URL(url, location.href).searchParams.get("account") || "");
    } catch (error) {
      if (error.name === "AbortError") return;
      window.location.assign(url);
    }
  };

  document.addEventListener("click", (event) => {
    const accountButton = event.target.closest("[data-portfolio-account]");
    if (accountButton && !accountButton.disabled) {
      event.preventDefault();
      const url = new URL(location.href);
      const accountKey = accountButton.dataset.portfolioAccount || "";
      const currentKey = url.searchParams.get("account") || "";
      if (accountKey && accountKey !== currentKey) url.searchParams.set("account", accountKey);
      else url.searchParams.delete("account");
      loadPortfolioChartRange(url.href);
      return;
    }
    const link = event.target.closest("[data-portfolio-chart-column] .portfolio-ranges a");
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    loadPortfolioChartRange(link.href);
  });
  document.addEventListener("change", (event) => {
    const methodPicker = event.target.closest("#portfolio-return-method");
    if (!methodPicker?.form) return;
    const target = new URL(methodPicker.form.action || location.href, location.href);
    const params = new URLSearchParams(new FormData(methodPicker.form));
    ["lang", "currency"].forEach((key) => {
      const value = new URL(location.href).searchParams.get(key);
      if (value && !params.has(key)) params.set(key, value);
    });
    target.search = params.toString();
    loadPortfolioChartRange(target.href);
  });
  window.addEventListener("popstate", () => {
    if (document.querySelector("[data-portfolio-chart-column]") && location.pathname === "/brokerage") {
      loadPortfolioChartRange(location.href, false);
    }
  });

  const bindDashboardHero = (root = document) => {
    const hero = root.matches?.("[data-dashboard-hero]") ? root : root.querySelector?.("[data-dashboard-hero]");
    if (!hero || hero.dataset.heroBound === "1") return;
    hero.dataset.heroBound = "1";
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const typing = hero.querySelector("[data-dashboard-typing]");
    const phrases = activeLanguage === "zh"
      ? ["股票、期权与投资组合", "复盘、学习与持续进步", "数据始终留在你的电脑", "更清晰、更自律的交易"]
      : ["stocks, options, and portfolios", "review, learning, and iteration", "data that stays on your computer", "clearer, more disciplined trading"];

    hero.classList.add("is-ready");
    if (typing) {
      typing.setAttribute("aria-live", "polite");
      if (reducedMotion) {
        typing.textContent = phrases[0];
      } else {
        let phraseIndex = 0;
        let characterIndex = 0;
        let deleting = false;
        const typeNext = () => {
          const phrase = phrases[phraseIndex];
          characterIndex += deleting ? -1 : 1;
          typing.textContent = phrase.slice(0, Math.max(0, characterIndex));
          let delay = deleting ? 28 : 54;
          if (!deleting && characterIndex >= phrase.length) {
            deleting = true;
            delay = 1450;
          } else if (deleting && characterIndex <= 0) {
            deleting = false;
            phraseIndex = (phraseIndex + 1) % phrases.length;
            delay = 320;
          }
          window.setTimeout(typeNext, delay);
        };
        typing.textContent = "";
        window.setTimeout(typeNext, 280);
      }
    }

    if (!reducedMotion) {
      hero.addEventListener("pointermove", (event) => {
        if (event.pointerType === "touch") return;
        const rect = hero.getBoundingClientRect();
        hero.style.setProperty("--hero-pointer-x", `${((event.clientX - rect.left) / Math.max(rect.width, 1) * 100).toFixed(1)}%`);
        hero.style.setProperty("--hero-pointer-y", `${((event.clientY - rect.top) / Math.max(rect.height, 1) * 100).toFixed(1)}%`);
      });
      hero.addEventListener("pointerleave", () => {
        hero.style.removeProperty("--hero-pointer-x");
        hero.style.removeProperty("--hero-pointer-y");
      });
    }
  };
  bindDashboardHero();

  const bindCollapsiblePanels = (root = document) => {
    const panels = root.querySelectorAll?.(".panel:not(.trade-form):not([data-no-collapse])") || [];
    panels.forEach((panel, index) => {
      if (panel.dataset.collapseBound === "1") return;
      if (panel.closest(".webull-dashboard-grid,.webull-dashboard-side")) return;
      const head = panel.querySelector(":scope > .panel-head");
      if (!head || panel.children.length < 2) return;
      panel.dataset.collapseBound = "1";
      panel.classList.add("fx-collapsible-panel");
      const heading = head.querySelector("h1,h2,h3,b,strong")?.textContent?.trim() || `section-${index}`;
      const storageKey = `optionLedgerPanel:${location.pathname}:${heading}`;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "fx-collapse-button";
      button.innerHTML = '<span aria-hidden="true"></span>';
      head.appendChild(button);
      const setCollapsed = (collapsed, animate = true) => {
        button.setAttribute("aria-expanded", collapsed ? "false" : "true");
        button.setAttribute("aria-label", collapsed ? "Expand section" : "Collapse section");
        button.title = collapsed ? "Expand section" : "Collapse section";
        if (!animate) panel.style.transition = "none";
        if (collapsed) {
          panel.style.maxHeight = `${Math.ceil(head.getBoundingClientRect().height + 34)}px`;
          panel.classList.add("fx-panel-collapsed");
        } else {
          panel.classList.remove("fx-panel-collapsed");
          panel.style.maxHeight = `${panel.scrollHeight}px`;
          window.setTimeout(() => {
            if (!panel.classList.contains("fx-panel-collapsed")) panel.style.removeProperty("max-height");
          }, 340);
        }
        if (!animate) requestAnimationFrame(() => panel.style.removeProperty("transition"));
      };
      setCollapsed(localStorage.getItem(storageKey) === "collapsed", false);
      button.addEventListener("click", () => {
        const collapsed = !panel.classList.contains("fx-panel-collapsed");
        setCollapsed(collapsed);
        if (collapsed) localStorage.setItem(storageKey, "collapsed");
        else localStorage.removeItem(storageKey);
      });
    });
  };

  const bindSlideDrawer = () => {
    if (document.documentElement.dataset.drawerBound === "1") return;
    document.documentElement.dataset.drawerBound = "1";
    const shell = document.createElement("div");
    shell.className = "fx-drawer-shell";
    shell.hidden = true;
    shell.innerHTML = `<button class="fx-drawer-backdrop" type="button" aria-label="Close details"></button>
      <aside class="fx-drawer" role="dialog" aria-modal="true" aria-labelledby="fx-drawer-title">
        <div class="fx-drawer-head"><div><small>QUICK EDIT</small><h2 id="fx-drawer-title">Edit details</h2></div><button class="fx-drawer-close" type="button" aria-label="Close details">&times;</button></div>
        <div class="fx-drawer-content"></div>
      </aside>`;
    document.body.appendChild(shell);
    const content = shell.querySelector(".fx-drawer-content");
    const closeButton = shell.querySelector(".fx-drawer-close");
    let request = null;
    const close = () => {
      request?.abort();
      shell.classList.remove("is-open");
      document.body.classList.remove("fx-drawer-open");
      window.setTimeout(() => { shell.hidden = true; content.replaceChildren(); }, 280);
    };
    const open = async (url) => {
      request?.abort();
      request = new AbortController();
      shell.hidden = false;
      content.innerHTML = '<div class="fx-drawer-loading"><i></i><span>Loading details...</span></div>';
      applyLanguage(shell);
      requestAnimationFrame(() => shell.classList.add("is-open"));
      document.body.classList.add("fx-drawer-open");
      closeButton.focus({ preventScroll: true });
      try {
        const destination = new URL(url, location.href);
        if (activeLanguage === "zh") destination.searchParams.set("lang", "zh");
        const response = await fetch(destination, { cache: "no-store", signal: request.signal });
        if (!response.ok) throw new Error(`Drawer request failed: ${response.status}`);
        const page = new DOMParser().parseFromString(await response.text(), "text/html");
        const nextMain = page.querySelector("main");
        if (!nextMain) throw new Error("Missing form content");
        const imported = document.importNode(nextMain, true);
        content.replaceChildren(...Array.from(imported.childNodes));
        hydrateSoftPage(content);
        content.querySelector("input:not([type=hidden]),select,textarea")?.focus({ preventScroll: true });
      } catch (error) {
        if (error.name === "AbortError") return;
        location.assign(url);
      }
    };
    shell.querySelector(".fx-drawer-backdrop").addEventListener("click", close);
    closeButton.addEventListener("click", close);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && shell.classList.contains("is-open")) close();
    });
    document.addEventListener("click", (event) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const link = event.target.closest("main a[href]");
      if (!link || !/\/(?:trade|day-trade|other-option|earnings-bet|stock-trade)\/\d+\/edit(?:\?|$)/.test(link.getAttribute("href") || "")) return;
      event.preventDefault();
      event.stopPropagation();
      open(link.href);
    });
  };

  bindCollapsiblePanels();
  bindSlideDrawer();

  const bindDynamicHeader = () => {
    const header = document.querySelector("body > header");
    const nav = header?.querySelector("nav");
    if (!header || !nav || header.dataset.dynamicBound === "1") return;
    header.dataset.dynamicBound = "1";
    header.classList.add("fx-dynamic-header");
    const indicator = document.createElement("span");
    indicator.className = "fx-nav-indicator";
    indicator.setAttribute("aria-hidden", "true");
    nav.appendChild(indicator);
    const progress = document.createElement("span");
    progress.className = "fx-header-progress";
    progress.setAttribute("aria-hidden", "true");
    header.appendChild(progress);
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frame = 0;
    const activeTarget = () => nav.querySelector(":scope > a.active,:scope > .nav-menu.active > .nav-menu-button") || nav.querySelector(":scope > a");
    const moveIndicator = (target, immediate = false) => {
      if (!target || !target.isConnected) return;
      const navRect = nav.getBoundingClientRect();
      const rect = target.getBoundingClientRect();
      indicator.style.setProperty("--fx-nav-x", `${Math.round(rect.left - navRect.left)}px`);
      indicator.style.setProperty("--fx-nav-width", `${Math.round(rect.width)}px`);
      indicator.classList.toggle("is-immediate", immediate);
      if (immediate) requestAnimationFrame(() => indicator.classList.remove("is-immediate"));
    };
    const updateScrollState = () => {
      frame = 0;
      const root = document.documentElement;
      const maximum = Math.max(root.scrollHeight - window.innerHeight, 1);
      const ratio = Math.max(0, Math.min(window.scrollY / maximum, 1));
      header.style.setProperty("--fx-header-progress", `${(ratio * 100).toFixed(2)}%`);
      header.classList.toggle("is-page-scrolled", window.scrollY > 10);
    };
    const requestScrollUpdate = () => {
      if (!frame) frame = requestAnimationFrame(updateScrollState);
    };
    nav.addEventListener("pointerover", (event) => {
      const target = event.target.closest("nav > a,nav > button,nav > .nav-menu > .nav-menu-button");
      if (target && nav.contains(target)) moveIndicator(target);
    });
    nav.addEventListener("pointerleave", () => moveIndicator(activeTarget()));
    header.addEventListener("pointermove", (event) => {
      if (reducedMotion || event.pointerType === "touch") return;
      const rect = header.getBoundingClientRect();
      header.style.setProperty("--fx-header-pointer", `${((event.clientX - rect.left) / Math.max(rect.width, 1) * 100).toFixed(1)}%`);
    });
    header.addEventListener("pointerleave", () => header.style.removeProperty("--fx-header-pointer"));
    window.addEventListener("scroll", requestScrollUpdate, { passive: true });
    window.addEventListener("resize", () => moveIndicator(activeTarget(), true));
    document.addEventListener("option-ledger:navigation-updated", () => moveIndicator(activeTarget()));
    requestAnimationFrame(() => moveIndicator(activeTarget(), true));
    updateScrollState();
  };

  bindDynamicHeader();

  const bindPolishEffects = () => {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (!reducedMotion) {
      const revealNodes = document.querySelectorAll([
        "main > .dashboard-motion-hero",
        "main > .page-head",
        "main > .metrics",
        "main > .panel",
        "main > [data-portfolio-page] > .page-head",
        "main > [data-portfolio-page] > .portfolio-hero",
        "main > [data-portfolio-page] > .portfolio-connect",
        "main > [data-portfolio-page] > .portfolio-categories"
      ].join(","));
      revealNodes.forEach((node, index) => {
        node.classList.add("fx-section-enter");
        node.style.setProperty("--fx-enter-delay", `${Math.min(index, 6) * 45}ms`);
      });
    }

    const numberPattern = /^([+-]?)(\$?)(\d[\d,]*(?:\.\d+)?)(%)?$/;
    const numberNodes = document.querySelectorAll([
      ".dashboard-summary-row strong",
      ".metric strong",
      ".compact-summary-card strong",
      ".symbols-summary-card strong",
      "[data-portfolio-live-value]",
      ".portfolio-category summary>strong"
    ].join(","));
    if (!reducedMotion) {
      numberNodes.forEach((node) => {
        if (node.childElementCount) return;
        if (node.dataset.fxCountBound === "1") return;
        const match = (node.textContent || "").trim().match(numberPattern);
        if (!match) return;
        node.dataset.fxCountBound = "1";
        node.classList.add("fx-number-pop");
        const [, sign, currency, numericText, suffix] = match;
        const target = Number(numericText.replaceAll(",", ""));
        if (!Number.isFinite(target)) return;
        const decimals = numericText.includes(".") ? numericText.split(".")[1].length : 0;
        const original = node.textContent.trim();
        node.setAttribute("aria-label", original);
        const startedAt = performance.now();
        const duration = 680;
        const render = (now) => {
          const progress = Math.min((now - startedAt) / duration, 1);
          const eased = 1 - Math.pow(1 - progress, 3);
          const value = target * eased;
          node.textContent = `${sign}${currency}${value.toLocaleString("en-US", {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
          })}${suffix || ""}`;
          if (progress < 1) requestAnimationFrame(render);
          else node.textContent = original;
        };
        requestAnimationFrame(render);
      });
    }

    const interactiveCards = document.querySelectorAll([
      ".metric",
      ".compact-summary-card",
      ".symbols-summary-card",
      ".portfolio-category"
    ].join(","));
    interactiveCards.forEach((card) => {
      card.classList.add("fx-card");
      if (reducedMotion) return;
      card.addEventListener("pointermove", (event) => {
        if (event.pointerType === "touch") return;
        const rect = card.getBoundingClientRect();
        const rotateX = ((event.clientY - rect.top) / Math.max(rect.height, 1) - 0.5) * -0.8;
        const rotateY = ((event.clientX - rect.left) / Math.max(rect.width, 1) - 0.5) * 0.8;
        card.style.setProperty("--fx-rotate-x", `${rotateX.toFixed(2)}deg`);
        card.style.setProperty("--fx-rotate-y", `${rotateY.toFixed(2)}deg`);
      });
      card.addEventListener("pointerleave", () => {
        card.style.removeProperty("--fx-rotate-x");
        card.style.removeProperty("--fx-rotate-y");
      });
    });

    if (!reducedMotion) {
      document.querySelectorAll(".performance-chart,.capital-chart,[data-portfolio-chart]").forEach((chart) => chart.classList.add("fx-chart-reveal"));
      document.querySelectorAll(".perf-area,.capital-area,.portfolio-area").forEach((area) => area.classList.add("fx-area-reveal"));
      document.querySelectorAll(".perf-line,.capital-line,.portfolio-line").forEach((line) => {
        line.setAttribute("pathLength", "1");
        line.classList.add("fx-line-draw");
      });
    }

    const pendingToast = sessionStorage.getItem("optionLedgerToast");
    if (pendingToast) {
      sessionStorage.removeItem("optionLedgerToast");
      const toast = document.createElement("div");
      toast.className = "fx-toast";
      toast.setAttribute("role", "status");
      toast.innerHTML = `<span aria-hidden="true">&#10003;</span><b>${pendingToast}</b>`;
      document.body.appendChild(toast);
      requestAnimationFrame(() => toast.classList.add("is-visible"));
      window.setTimeout(() => toast.classList.remove("is-visible"), 2600);
      window.setTimeout(() => toast.remove(), 3000);
    }
    document.querySelectorAll('form[action="/brokerage/robinhood/sync"],form[action="/holdings/refresh-prices"]').forEach((form) => {
      form.addEventListener("submit", () => {
        const isSync = form.getAttribute("action")?.includes("robinhood");
        sessionStorage.setItem("optionLedgerToast", isSync ? "Portfolio synced" : "Prices refreshed");
        form.querySelector("button")?.classList.add("is-processing");
      });
    });

    window.addEventListener("pageshow", () => document.documentElement.classList.remove("fx-page-leaving"));
  };
  bindPolishEffects();

  const bindPortfolioAutoSync = () => {
    const page = document.querySelector("[data-portfolio-page]");
    if (!page) return;
    let currentMarker = page.dataset.robinhoodSnapshotMarker || "";
    const seconds = Math.max(Number.parseInt(page.dataset.refreshSeconds || "30", 10), 15);
    let syncing = false;
    const syncButton = page.querySelector('form[action="/brokerage/robinhood/sync"] button');
    const setSyncing = (active) => {
      syncing = active;
      if (!syncButton) return;
      syncButton.disabled = active;
      syncButton.textContent = active ? "Syncing..." : "Sync Robinhood";
    };
    const syncFromSnapshot = () => {
      if (syncing) return;
      setSyncing(true);
      fetch("/brokerage/robinhood/sync", { method: "POST", cache: "no-store" })
        .then((response) => response.ok ? response.text() : Promise.reject())
        .then(() => window.location.reload())
        .catch(() => setSyncing(false));
    };
    const checkSnapshot = () => {
      if (syncing || document.hidden) return;
      fetch("/brokerage/robinhood/status", { headers: { "X-Requested-With": "fetch" }, cache: "no-store" })
        .then((response) => response.ok ? response.json() : Promise.reject())
        .then((payload) => {
          if (!payload.exists) return;
          const nextMarker = payload.marker || "";
          if (payload.needs_import || (nextMarker && currentMarker && nextMarker !== currentMarker)) {
            currentMarker = nextMarker;
            syncFromSnapshot();
          }
        })
        .catch(() => {});
    };
    setConnectedInterval(page, checkSnapshot, seconds * 1000);
    checkSnapshot();
  };
  bindPortfolioAutoSync();

  const bindNotificationMenu = () => {
    const menu = document.querySelector("[data-notification-menu]");
    if (!menu) return;
    const button = menu.querySelector("[data-notification-button]");
    if (!button) return;
    const closeMenu = () => {
      menu.classList.remove("is-open");
      button.setAttribute("aria-expanded", "false");
    };
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const shouldOpen = !menu.classList.contains("is-open");
      menu.classList.toggle("is-open", shouldOpen);
      button.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
    });
    document.addEventListener("click", (event) => {
      if (!menu.contains(event.target)) closeMenu();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeMenu();
    });
  };
  bindNotificationMenu();

  const bindMarketClock = () => {
    const clock = document.querySelector("[data-market-clock]");
    if (!clock) return;
    const timeNode = clock.querySelector("[data-clock-time]");
    const labelNode = clock.querySelector("[data-clock-label]");
    const countdownNode = clock.querySelector("[data-clock-countdown]");
    const nyFormatter = new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York",
      weekday: "short",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false
    });
    const localFormatter = new Intl.DateTimeFormat("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false
    });
    const weekdayIndex = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
    const openSecond = 9 * 3600 + 30 * 60;
    const closeSecond = 16 * 3600;
    const partsFor = (date) => Object.fromEntries(nyFormatter.formatToParts(date).map((part) => [part.type, part.value]));
    const addDays = (parts, days) => {
      const next = new Date(Date.UTC(Number(parts.year), Number(parts.month) - 1, Number(parts.day) + days, 12));
      return partsFor(next);
    };
    const dateKey = (parts) => Date.UTC(Number(parts.year), Number(parts.month) - 1, Number(parts.day));
    const nextWeekday = (parts) => {
      let candidate = parts;
      while (weekdayIndex[candidate.weekday] === 0 || weekdayIndex[candidate.weekday] === 6) {
        candidate = addDays(candidate, 1);
      }
      return candidate;
    };
    const formatDuration = (seconds) => {
      const safe = Math.max(0, Math.floor(seconds));
      const hours = String(Math.floor(safe / 3600)).padStart(2, "0");
      const minutes = String(Math.floor((safe % 3600) / 60)).padStart(2, "0");
      const secs = String(safe % 60).padStart(2, "0");
      return `${hours}:${minutes}:${secs}`;
    };
    const updateClock = () => {
      const now = new Date();
      const parts = partsFor(now);
      const weekday = weekdayIndex[parts.weekday];
      const currentSecond = Number(parts.hour) * 3600 + Number(parts.minute) * 60 + Number(parts.second);
      let label = "距离开盘";
      let targetParts = parts;
      let targetSecond = openSecond;
      let isOpen = false;
      if (weekday > 0 && weekday < 6 && currentSecond >= openSecond && currentSecond < closeSecond) {
        label = "距离收盘";
        targetSecond = closeSecond;
        isOpen = true;
      } else if (weekday > 0 && weekday < 6 && currentSecond < openSecond) {
        targetSecond = openSecond;
      } else {
        targetParts = nextWeekday(addDays(parts, 1));
        targetSecond = openSecond;
      }
      const dayDiff = Math.round((dateKey(targetParts) - dateKey(parts)) / 86400000);
      const remaining = dayDiff * 86400 + targetSecond - currentSecond;
      timeNode.textContent = localFormatter.format(now);
      labelNode.textContent = activeLanguage === "zh" ? label : (isOpen ? "to close" : "to open");
      countdownNode.textContent = formatDuration(remaining);
      clock.classList.toggle("is-open", isOpen);
    };
    updateClock();
    window.setInterval(updateClock, 1000);
  };
  bindMarketClock();

  const bindHoldingsLive = () => {
    const panel = document.querySelector("[data-holdings-live]");
    if (!panel) return;
    if (!document.querySelector("[data-holdings-rows]") || !document.querySelector("[data-holdings-summary]")) return;
    const seconds = Math.max(Number.parseInt(panel.dataset.refreshSeconds || "30", 10), 10);
    const refreshHoldings = () => {
      const requestUrl = new URL("/holdings/data", window.location.href);
      new URLSearchParams(window.location.search).forEach((value, key) => requestUrl.searchParams.set(key, value));
      panel.classList.add("is-loading");
      fetch(requestUrl, { headers: { "X-Requested-With": "fetch" }, cache: "no-store" })
        .then((response) => response.ok ? response.json() : Promise.reject())
        .then((payload) => {
          const rowsNode = document.querySelector("[data-holdings-rows]");
          const summaryNode = document.querySelector("[data-holdings-summary]");
          const countNode = document.querySelector("[data-holdings-count]");
          const summaryTemplate = document.createElement("template");
          summaryTemplate.innerHTML = payload.summary || "";
          const nextSummary = summaryTemplate.content.querySelector("[data-holdings-summary]");
          if (summaryNode && nextSummary) {
            summaryNode.replaceWith(nextSummary);
            applyLanguage(nextSummary);
          }
          if (rowsNode) rowsNode.innerHTML = payload.rows || "";
          if (countNode && Number.isFinite(Number(payload.count))) countNode.textContent = String(payload.count);
          if (rowsNode) applyLanguage(rowsNode);
        })
        .catch(() => {})
        .finally(() => panel.classList.remove("is-loading"));
    };
    refreshHoldings();
    setConnectedInterval(panel, refreshHoldings, seconds * 1000);
  };
  bindHoldingsLive();

  const bindTickerTape = () => {
    const tape = document.querySelector("[data-ticker-tape]");
    if (!tape) return;
    const seconds = Math.max(Number.parseInt(tape.dataset.refreshSeconds || "30", 10), 10);
    const tickerPrices = (root) => {
      const values = new Map();
      root.querySelectorAll(".ticker-item").forEach((item) => {
        const label = item.querySelector("b")?.textContent?.trim();
        const price = Number((item.querySelector("span")?.textContent || "").replace(/[^0-9.-]/g, ""));
        if (label && Number.isFinite(price)) values.set(label, price);
      });
      return values;
    };
    const refreshTape = () => {
      const previousPrices = tickerPrices(tape);
      fetch("/ticker-tape", { headers: { "X-Requested-With": "fetch" }, cache: "no-store" })
        .then((response) => response.ok ? response.text() : Promise.reject())
        .then((html) => {
          const template = document.createElement("template");
          template.innerHTML = html.trim();
          const nextTrack = template.content.querySelector(".ticker-track");
          const currentTrack = tape.querySelector(".ticker-track");
          if (!nextTrack || !currentTrack) return;
          currentTrack.innerHTML = nextTrack.innerHTML;
          currentTrack.querySelectorAll(".ticker-item").forEach((item) => {
            const label = item.querySelector("b")?.textContent?.trim();
            const price = Number((item.querySelector("span")?.textContent || "").replace(/[^0-9.-]/g, ""));
            const previous = label ? previousPrices.get(label) : undefined;
            if (!Number.isFinite(price) || !Number.isFinite(previous) || price === previous) return;
            item.classList.add(price > previous ? "price-tick-up" : "price-tick-down");
            window.setTimeout(() => item.classList.remove("price-tick-up", "price-tick-down"), 900);
          });
          applyLanguage(currentTrack);
        })
        .catch(() => {});
    };
    refreshTape();
    window.setInterval(refreshTape, seconds * 1000);
  };
  bindTickerTape();

  const bindSymbolPricePanel = () => {
    const panel = document.querySelector("[data-symbol-price-panel]");
    if (!panel) return;
    const ticker = panel.dataset.ticker;
    if (!ticker) return;
    const seconds = Math.max(Number.parseInt(panel.dataset.refreshSeconds || "30", 10), 10);
    const refreshPanel = () => {
      const current = document.querySelector("[data-symbol-price-panel]");
      if (!current) return;
      current.classList.add("is-loading");
      fetch(`/symbol/${encodeURIComponent(ticker)}/price`, { headers: { "X-Requested-With": "fetch" }, cache: "no-store" })
        .then((response) => response.ok ? response.text() : Promise.reject())
        .then((html) => {
          const template = document.createElement("template");
          template.innerHTML = html.trim();
          const nextPanel = template.content.querySelector("[data-symbol-price-panel]");
          if (!nextPanel) return;
          current.replaceWith(nextPanel);
          applyLanguage(nextPanel);
        })
        .catch(() => current.classList.remove("is-loading"));
    };
    setConnectedInterval(panel, refreshPanel, seconds * 1000);
  };
  bindSymbolPricePanel();

  const bindSymbolValuation = (root = document) => {
    root.querySelectorAll("[data-symbol-valuation]").forEach((panel) => {
      if (panel.dataset.valuationBound === "1") return;
      panel.dataset.valuationBound = "1";
      const ticker = panel.dataset.ticker || "symbol";
      const storageKey = `symbolValuation:2027:${ticker}`;
      const epsInput = panel.querySelector("[data-valuation-eps]");
      const multipleInputs = Array.from(panel.querySelectorAll("[data-valuation-multiple]"));
      const currentPrice = Number.parseFloat(panel.dataset.currentPrice || "");
      const usdCnyRate = Number.parseFloat(panel.dataset.usdCnyRate || "1");
      try {
        const saved = JSON.parse(localStorage.getItem(storageKey) || "{}");
        if (epsInput && saved.eps !== undefined) epsInput.value = saved.eps;
        multipleInputs.forEach((input) => {
          const key = input.dataset.valuationMultiple;
          if (key && saved[key] !== undefined) input.value = saved[key];
        });
      } catch {}

      const render = () => {
        const eps = Number.parseFloat(epsInput?.value || "");
        const saved = { eps: epsInput?.value || "" };
        multipleInputs.forEach((input) => {
          const key = input.dataset.valuationMultiple;
          const multiple = Number.parseFloat(input.value || "");
          if (key) saved[key] = input.value;
          const result = key ? panel.querySelector(`[data-valuation-result="${key}"]`) : null;
          const priceNode = result?.querySelector("strong");
          const upsideNode = result?.querySelector("small");
          if (!result || !priceNode || !upsideNode) return;
          if (!Number.isFinite(eps) || eps < 0 || !Number.isFinite(multiple) || multiple < 0) {
            priceNode.textContent = "-";
            upsideNode.textContent = "-";
            result.classList.remove("gain", "loss", "neutral");
            return;
          }
          const target = eps * multiple;
          const upside = Number.isFinite(currentPrice) && currentPrice > 0 ? (target / currentPrice) - 1 : null;
          const displayTarget = activeCurrency === "rmb" ? target * usdCnyRate : target;
          const displaySymbol = activeCurrency === "rmb" ? "\u00a5" : "$";
          priceNode.textContent = `${displaySymbol}${displayTarget.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
          const unavailableLabel = activeLanguage === "zh" ? repairMojibake(translatedText("Price unavailable")) : "Price unavailable";
          upsideNode.textContent = upside === null ? unavailableLabel : `${upside >= 0 ? "+" : ""}${(upside * 100).toFixed(1)}%`;
          result.classList.remove("gain", "loss", "neutral");
          result.classList.add(upside === null ? "neutral" : upside >= 0 ? "gain" : "loss");
        });
        localStorage.setItem(storageKey, JSON.stringify(saved));
      };
      panel.querySelectorAll("input").forEach((input) => input.addEventListener("input", render));
      render();
    });
  };
  bindSymbolValuation();

  const bindEarningsBetForm = () => {
    const form = document.querySelector("[data-earnings-bet-form]");
    if (!form) return;
    const picker = form.querySelector("[data-earnings-strategy-type]");
    const sections = Array.from(form.querySelectorAll("[data-earnings-strategy-section]"));
    const sync = () => {
      const active = picker?.value || "Stock";
      sections.forEach((section) => {
        const isActive = section.dataset.earningsStrategySection === active;
        section.hidden = !isActive;
        section.querySelectorAll("input,select,textarea").forEach((input) => {
          input.disabled = !isActive;
        });
      });
    };
    picker?.addEventListener("change", sync);
    sync();
  };
  bindEarningsBetForm();

  const bindOtherOptionForm = () => {
    const form = document.querySelector("[data-other-option-form]");
    if (!form) return;
    const picker = form.querySelector("[data-other-option-type]");
    const sections = Array.from(form.querySelectorAll("[data-other-option-section]"));
    const sync = () => {
      const active = picker?.value || "Single option";
      sections.forEach((section) => {
        const supportedTypes = (section.dataset.otherOptionSection || "").split("|");
        const isActive = supportedTypes.includes(active);
        section.hidden = !isActive;
        section.querySelectorAll("input,select,textarea").forEach((input) => {
          input.disabled = !isActive;
        });
      });
    };
    picker?.addEventListener("change", sync);
    sync();
  };
  bindOtherOptionForm();

  const bindUnifiedOptionForm = () => {
    const form = document.querySelector("[data-unified-option-form]");
    if (!form) return;
    const bookPicker = form.querySelector("[data-option-book]");
    const bookSections = Array.from(form.querySelectorAll("[data-option-book-section]"));
    const sellerStrategyPicker = form.querySelector("[data-seller-strategy]");
    const sellerSpreadFields = Array.from(form.querySelectorAll("[data-seller-spread-field]"));
    const sellerCondorFields = Array.from(form.querySelectorAll("[data-seller-condor-field]"));
    const buyerTypePicker = form.querySelector("[data-other-option-type]");
    const buyerSections = Array.from(form.querySelectorAll("[data-other-option-section]"));
    const syncSellerSections = () => {
      const isSellerActive = (bookPicker?.value || form.dataset.optionMode || "seller") === "seller";
      const strategy = sellerStrategyPicker?.value || "";
      const isCondor = strategy === "Iron Condor";
      const usesLongPut = isCondor || ["Put Credit Spread", "Call Credit Spread"].includes(strategy);
      sellerSpreadFields.forEach((section) => {
        const isActive = isSellerActive && usesLongPut;
        section.hidden = !isActive;
        section.querySelectorAll("input,select,textarea").forEach((input) => {
          input.disabled = !isActive;
          input.required = isActive;
        });
      });
      sellerCondorFields.forEach((section) => {
        const isActive = isSellerActive && isCondor;
        section.hidden = !isActive;
        section.querySelectorAll("input,select,textarea").forEach((input) => {
          input.disabled = !isActive;
          input.required = isActive;
        });
      });
      form.querySelector("[data-seller-strike-label]")?.replaceChildren(document.createTextNode(isCondor ? "Short put strike" : "Short strike"));
      form.querySelector("[data-seller-long-label]")?.replaceChildren(document.createTextNode(isCondor ? "Long put strike" : "Long strike"));
      form.querySelector("[data-seller-long-help]")?.replaceChildren(document.createTextNode(isCondor ? "Put-side protective wing." : "For credit spreads only."));
    };
    const syncBuyerSections = () => {
      const active = buyerTypePicker?.value || "Single option";
      buyerSections.forEach((section) => {
        const supportedTypes = (section.dataset.otherOptionSection || "").split("|");
        const isActive = supportedTypes.includes(active);
        section.hidden = !isActive;
        section.querySelectorAll("input,select,textarea").forEach((input) => {
          input.disabled = !isActive || bookPicker?.value !== "buyer";
        });
      });
    };
    const syncBook = () => {
      const active = bookPicker?.value || form.dataset.optionMode || "seller";
      bookSections.forEach((section) => {
        const isActive = section.dataset.optionBookSection === active;
        section.hidden = !isActive;
        section.querySelectorAll("input,select,textarea").forEach((input) => {
          input.disabled = !isActive;
        });
      });
      syncSellerSections();
      syncBuyerSections();
    };
    bookPicker?.addEventListener("change", syncBook);
    sellerStrategyPicker?.addEventListener("change", syncSellerSections);
    buyerTypePicker?.addEventListener("change", syncBuyerSections);
    syncBook();
  };
  bindUnifiedOptionForm();

  const bindDashboardSplitter = () => {
    const layout = document.querySelector("[data-dashboard-layout]");
    const splitter = document.querySelector("[data-dashboard-splitter]");
    if (!layout || !splitter) return;
    const storageKey = "optionsDashboardSideWidth";
    const savedWidth = Number(window.localStorage.getItem(storageKey));
    if (Number.isFinite(savedWidth) && savedWidth > 0) {
      layout.style.setProperty("--dashboard-side-width", `${Math.max(420, savedWidth)}px`);
    }
    splitter.addEventListener("dblclick", () => {
      layout.style.removeProperty("--dashboard-side-width");
      window.localStorage.removeItem(storageKey);
      splitter.classList.add("fx-split-reset");
      window.setTimeout(() => splitter.classList.remove("fx-split-reset"), 420);
      window.dispatchEvent(new Event("resize"));
    });
    splitter.addEventListener("pointerdown", (event) => {
      if (window.matchMedia("(max-width: 980px)").matches) return;
      event.preventDefault();
      splitter.setPointerCapture?.(event.pointerId);
      layout.classList.add("is-resizing");
      const bounds = layout.getBoundingClientRect();
      const minSide = Math.min(420, Math.max(320, bounds.width - 1100));
      const maxSide = Math.max(minSide, Math.min(780, bounds.width - 760));
      const move = (moveEvent) => {
        const next = Math.max(minSide, Math.min(maxSide, moveEvent.clientX - bounds.left));
        layout.style.setProperty("--dashboard-side-width", `${Math.round(next)}px`);
      };
      const stop = () => {
        layout.classList.remove("is-resizing");
        layout.classList.add("just-resized");
        window.setTimeout(() => layout.classList.remove("just-resized"), 320);
        window.dispatchEvent(new Event("resize"));
        const current = parseInt(getComputedStyle(layout).getPropertyValue("--dashboard-side-width"), 10);
        if (Number.isFinite(current)) window.localStorage.setItem(storageKey, String(current));
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", stop);
        window.removeEventListener("pointercancel", stop);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", stop);
      window.addEventListener("pointercancel", stop);
    });
  };
  bindDashboardSplitter();

  const bindSymbolsSplitter = () => {
    const layout = document.querySelector("[data-symbols-layout]");
    const splitter = document.querySelector("[data-symbols-splitter]");
    if (!layout || !splitter) return;
    const storageKey = "optionsSymbolsSidebarWidth";
    const savedWidth = Number(window.localStorage.getItem(storageKey));
    if (Number.isFinite(savedWidth) && savedWidth > 0) {
      layout.style.setProperty("--symbols-sidebar-width", `${Math.max(250, savedWidth)}px`);
    }
    splitter.addEventListener("dblclick", () => {
      layout.style.removeProperty("--symbols-sidebar-width");
      window.localStorage.removeItem(storageKey);
      splitter.classList.add("fx-split-reset");
      window.setTimeout(() => splitter.classList.remove("fx-split-reset"), 420);
      window.dispatchEvent(new Event("resize"));
    });
    splitter.addEventListener("pointerdown", (event) => {
      if (window.matchMedia("(max-width: 980px)").matches) return;
      event.preventDefault();
      splitter.setPointerCapture?.(event.pointerId);
      layout.classList.add("is-resizing");
      const bounds = layout.getBoundingClientRect();
      const minSide = 250;
      const maxSide = Math.max(minSide, Math.min(520, bounds.width - 720));
      const move = (moveEvent) => {
        const next = Math.max(minSide, Math.min(maxSide, moveEvent.clientX - bounds.left));
        layout.style.setProperty("--symbols-sidebar-width", `${Math.round(next)}px`);
      };
      const stop = () => {
        layout.classList.remove("is-resizing");
        window.dispatchEvent(new Event("resize"));
        const current = parseInt(getComputedStyle(layout).getPropertyValue("--symbols-sidebar-width"), 10);
        if (Number.isFinite(current)) window.localStorage.setItem(storageKey, String(current));
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", stop);
        window.removeEventListener("pointercancel", stop);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", stop);
      window.addEventListener("pointercancel", stop);
    });
  };
  bindSymbolsSplitter();

  const bindLedgerSplitters = () => {
    document.querySelectorAll("[data-ledger-layout]").forEach((layout) => {
      const splitter = layout.querySelector("[data-ledger-splitter]");
      if (!splitter) return;
      const layoutKey = layout.dataset.layoutKey || "ledger";
      const storageKey = `options${layoutKey[0].toUpperCase()}${layoutKey.slice(1)}SidebarWidth`;
      const savedWidth = Number(window.localStorage.getItem(storageKey));
      if (Number.isFinite(savedWidth) && savedWidth > 0) {
        layout.style.setProperty("--ledger-sidebar-width", `${Math.max(250, savedWidth)}px`);
      }
      splitter.addEventListener("dblclick", () => {
        layout.style.removeProperty("--ledger-sidebar-width");
        window.localStorage.removeItem(storageKey);
        splitter.classList.add("fx-split-reset");
        window.setTimeout(() => splitter.classList.remove("fx-split-reset"), 420);
        window.dispatchEvent(new Event("resize"));
      });
      splitter.addEventListener("pointerdown", (event) => {
        if (window.matchMedia("(max-width: 980px)").matches) return;
        event.preventDefault();
        splitter.setPointerCapture?.(event.pointerId);
        layout.classList.add("is-resizing");
        const bounds = layout.getBoundingClientRect();
        const minSide = 250;
        const minLedgerWidth = window.matchMedia("(min-width: 1201px)").matches ? 960 : 720;
        const maxSide = Math.max(minSide, Math.min(520, bounds.width - minLedgerWidth));
        const move = (moveEvent) => {
          const next = Math.max(minSide, Math.min(maxSide, moveEvent.clientX - bounds.left));
          layout.style.setProperty("--ledger-sidebar-width", `${Math.round(next)}px`);
        };
        const stop = () => {
          layout.classList.remove("is-resizing");
          window.dispatchEvent(new Event("resize"));
          const current = parseInt(getComputedStyle(layout).getPropertyValue("--ledger-sidebar-width"), 10);
          if (Number.isFinite(current)) window.localStorage.setItem(storageKey, String(current));
          window.removeEventListener("pointermove", move);
          window.removeEventListener("pointerup", stop);
          window.removeEventListener("pointercancel", stop);
        };
        window.addEventListener("pointermove", move);
        window.addEventListener("pointerup", stop);
        window.addEventListener("pointercancel", stop);
      });
    });
  };
  bindLedgerSplitters();

  const bindRagdollCompanion = () => {
    const companion = document.querySelector("[data-ragdoll-companion]");
    if (!companion) return;
    const cat = companion.querySelector("[data-ragdoll-cat]");
    const speech = companion.querySelector("[data-ragdoll-speech]");
    const actions = companion.querySelector("[data-ragdoll-actions]");
    const restore = companion.querySelector("[data-ragdoll-restore]");
    const poses = Array.from(companion.querySelectorAll("[data-ragdoll-pose]"));
    const spriteCanvas = companion.querySelector("[data-ragdoll-sprite]");
    const spriteContext = spriteCanvas?.getContext("2d");
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const spriteAnimations = {
      sleep: {
        src: "/static/dandan-sleep-sprite.png?v=20261019-2", columns: 4, rows: 3, frames: 12, fps: 9,
        xCuts: [0, 374, 736, 1091, 1448], yCuts: [0, 445, 776, 1086],
      },
      wake: {
        src: "/static/dandan-wake-sprite.png?v=20261019-2", columns: 4, rows: 2, frames: 8, fps: 9,
        xCuts: [0, 459, 905, 1321, 1774], yCuts: [0, 440, 887],
      },
    };
    const spriteImages = new Map();
    const spriteFrameCache = new Map();
    const positionKey = "dandanCompanionPosition";
    const hiddenKey = "dandanCompanionHidden";
    const napKey = "dandanCompanionNapping";
    const isZh = activeLanguage === "zh";
    const reminders = isZh
      ? ["\u5148\u770b\u98ce\u9669\uff0c\u518d\u770b\u6536\u76ca\u3002", "\u597d\u673a\u4f1a\u4e0d\u9700\u8981\u8ffd\u3002", "\u7559\u4e00\u70b9\u73b0\u91d1\uff0c\u4e5f\u7559\u4e00\u70b9\u8010\u5fc3\u3002", "\u590d\u76d8\u4e4b\u540e\u518d\u505a\u4e0b\u4e00\u7b14\u3002"]
      : ["Risk first, return second.", "Good setups do not need chasing.", "Keep some cash and some patience.", "Review first, then take the next trade."];
    let reminderIndex = 0;
    let speechTimer;
    let poseTimer;
    let blinkTimer;
    let spriteFrameRequest;
    let spriteAnimationId = 0;
    let dragState = null;

    const clampPosition = (x, y) => {
      const width = companion.offsetWidth || 182;
      const height = companion.offsetHeight || 168;
      return {
        x: Math.max(0, Math.min(x, window.innerWidth - width)),
        y: Math.max(76, Math.min(y, window.innerHeight - height)),
      };
    };
    const setPosition = (x, y, persist = false) => {
      const next = clampPosition(x, y);
      companion.style.left = `${Math.round(next.x)}px`;
      companion.style.top = `${Math.round(next.y)}px`;
      companion.style.right = "auto";
      companion.style.bottom = "auto";
      companion.classList.toggle("is-left-side", next.x < 280);
      if (persist) localStorage.setItem(positionKey, JSON.stringify(next));
    };
    const applySavedPosition = () => {
      try {
        const saved = JSON.parse(localStorage.getItem(positionKey) || "null");
        if (saved && Number.isFinite(saved.x) && Number.isFinite(saved.y)) setPosition(saved.x, saved.y);
      } catch (_error) {
        localStorage.removeItem(positionKey);
      }
    };
    const showSpeech = (message) => {
      window.clearTimeout(speechTimer);
      if (speech) speech.textContent = message;
      companion.classList.add("is-speaking");
      speechTimer = window.setTimeout(() => companion.classList.remove("is-speaking"), 2400);
    };
    const stopFrameAnimation = () => {
      spriteAnimationId += 1;
      if (spriteFrameRequest) window.cancelAnimationFrame(spriteFrameRequest);
      spriteFrameRequest = null;
      companion.classList.remove("is-frame-animating", "is-frame-playing");
      spriteContext?.clearRect(0, 0, spriteCanvas.width, spriteCanvas.height);
    };
    const setPose = (name) => {
      poses.forEach((pose) => pose.classList.toggle("is-active", pose.dataset.ragdollPose === name));
      companion.dataset.pose = name;
    };
    const cleanSpritePixels = (context, width, height) => {
      const imageData = context.getImageData(0, 0, width, height);
      const pixels = imageData.data;
      const labels = new Int32Array(width * height);
      const stack = new Int32Array(width * height);
      let label = 0;
      let largestLabel = 0;
      let largestSize = 0;
      for (let seed = 0; seed < labels.length; seed += 1) {
        if (labels[seed] || pixels[(seed * 4) + 3] < 20) continue;
        label += 1;
        let stackSize = 1;
        let componentSize = 0;
        stack[0] = seed;
        labels[seed] = label;
        while (stackSize) {
          const current = stack[--stackSize];
          componentSize += 1;
          const x = current % width;
          const y = Math.floor(current / width);
          for (let dy = -1; dy <= 1; dy += 1) {
            for (let dx = -1; dx <= 1; dx += 1) {
              if ((!dx && !dy) || x + dx < 0 || x + dx >= width || y + dy < 0 || y + dy >= height) continue;
              const next = current + dx + (dy * width);
              if (labels[next] || pixels[(next * 4) + 3] < 20) continue;
              labels[next] = label;
              stack[stackSize++] = next;
            }
          }
        }
        if (componentSize > largestSize) {
          largestSize = componentSize;
          largestLabel = label;
        }
      }
      for (let pixel = 0; pixel < labels.length; pixel += 1) {
        if (labels[pixel] !== largestLabel) pixels[(pixel * 4) + 3] = 0;
      }
      context.putImageData(imageData, 0, 0);
    };
    const buildSpriteFrame = (name, image, animation, frame) => {
      const cacheKey = `${name}:${frame}`;
      if (spriteFrameCache.has(cacheKey)) return spriteFrameCache.get(cacheKey);
      const frameCanvas = document.createElement("canvas");
      frameCanvas.width = spriteCanvas.width;
      frameCanvas.height = spriteCanvas.height;
      const context = frameCanvas.getContext("2d");
      const column = frame % animation.columns;
      const row = Math.floor(frame / animation.columns);
      const sourceLeft = animation.xCuts?.[column] ?? Math.round(column * image.naturalWidth / animation.columns);
      const sourceRight = animation.xCuts?.[column + 1] ?? Math.round((column + 1) * image.naturalWidth / animation.columns);
      const sourceTop = animation.yCuts?.[row] ?? Math.round(row * image.naturalHeight / animation.rows);
      const sourceBottom = animation.yCuts?.[row + 1] ?? Math.round((row + 1) * image.naturalHeight / animation.rows);
      const inset = 2;
      const sourceWidth = sourceRight - sourceLeft - (inset * 2);
      const sourceHeight = sourceBottom - sourceTop - (inset * 2);
      const outputPadding = 14;
      const scale = Math.min(
        (frameCanvas.width - (outputPadding * 2)) / sourceWidth,
        (frameCanvas.height - (outputPadding * 2)) / sourceHeight,
      );
      const width = sourceWidth * scale;
      const height = sourceHeight * scale;
      context.drawImage(
        image, sourceLeft + inset, sourceTop + inset, sourceWidth, sourceHeight,
        (frameCanvas.width - width) / 2, frameCanvas.height - outputPadding - height, width, height,
      );
      cleanSpritePixels(context, frameCanvas.width, frameCanvas.height);
      spriteFrameCache.set(cacheKey, frameCanvas);
      return frameCanvas;
    };
    const drawSpriteFrame = (name, image, animation, frame) => {
      if (!spriteContext || !spriteCanvas) return;
      spriteContext.clearRect(0, 0, spriteCanvas.width, spriteCanvas.height);
      spriteContext.drawImage(buildSpriteFrame(name, image, animation, frame), 0, 0);
    };
    const holdSpriteFrame = (name, frame, onReady) => {
      const animation = spriteAnimations[name];
      stopFrameAnimation();
      if (!animation || reducedMotion || !spriteContext) {
        onReady?.();
        return;
      }
      const animationId = spriteAnimationId;
      let image = spriteImages.get(name);
      if (!image) {
        image = new Image();
        image.decoding = "async";
        image.src = animation.src;
        spriteImages.set(name, image);
      }
      const render = () => {
        if (animationId !== spriteAnimationId || !image.naturalWidth) return;
        drawSpriteFrame(name, image, animation, frame);
        companion.classList.add("is-frame-animating");
        companion.classList.remove("is-frame-playing");
        onReady?.();
      };
      if (image.complete && image.naturalWidth) render();
      else {
        image.addEventListener("load", render, { once: true });
        image.addEventListener("error", () => onReady?.(), { once: true });
      }
    };
    const holdRestingFrame = (onReady) => {
      const napping = companion.classList.contains("is-napping");
      const name = napping ? "sleep" : "wake";
      const animation = spriteAnimations[name];
      setPose(napping ? "sleep" : "idle");
      holdSpriteFrame(name, animation.frames - 1, onReady);
    };
    const playSpriteAnimation = (name, onComplete) => {
      const animation = spriteAnimations[name];
      if (!animation || reducedMotion || !spriteContext) {
        onComplete?.();
        return;
      }
      stopFrameAnimation();
      const animationId = spriteAnimationId;
      let image = spriteImages.get(name);
      if (!image) {
        image = new Image();
        image.decoding = "async";
        image.src = animation.src;
        spriteImages.set(name, image);
      }
      const begin = () => {
        if (animationId !== spriteAnimationId || !image.naturalWidth) return;
        companion.classList.add("is-frame-animating", "is-frame-playing");
        const startedAt = performance.now();
        const frameDuration = 1000 / animation.fps;
        const step = (now) => {
          if (animationId !== spriteAnimationId) return;
          const frame = Math.min(animation.frames - 1, Math.floor((now - startedAt) / frameDuration));
          drawSpriteFrame(name, image, animation, frame);
          if (frame < animation.frames - 1) {
            spriteFrameRequest = window.requestAnimationFrame(step);
            return;
          }
          window.setTimeout(() => {
            if (animationId !== spriteAnimationId) return;
            spriteFrameRequest = null;
            companion.classList.remove("is-frame-playing");
            onComplete?.();
          }, frameDuration);
        };
        spriteFrameRequest = window.requestAnimationFrame(step);
      };
      if (image.complete && image.naturalWidth) begin();
      else {
        image.addEventListener("load", begin, { once: true });
        image.addEventListener("error", () => onComplete?.(), { once: true });
      }
    };
    const scheduleBlink = () => {
      window.clearTimeout(blinkTimer);
      if (reducedMotion || companion.classList.contains("is-napping") || companion.classList.contains("is-hidden")) return;
      blinkTimer = window.setTimeout(() => {
        if (companion.dataset.pose !== "idle" || companion.classList.contains("is-frame-playing")) {
          scheduleBlink();
          return;
        }
        stopFrameAnimation();
        setPose("pet");
        blinkTimer = window.setTimeout(() => {
          setPose("idle");
          scheduleBlink();
        }, 260);
      }, 4200 + Math.random() * 5200);
    };
    const returnToRestingPose = (delay = 0) => {
      window.clearTimeout(poseTimer);
      poseTimer = window.setTimeout(() => {
        holdRestingFrame();
      }, delay);
    };
    const playPurr = () => {
      try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        const context = new AudioContext();
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        const wobble = context.createOscillator();
        const wobbleGain = context.createGain();
        oscillator.type = "sine";
        oscillator.frequency.value = 52;
        wobble.type = "sine";
        wobble.frequency.value = 24;
        wobbleGain.gain.value = 8;
        gain.gain.setValueAtTime(.0001, context.currentTime);
        gain.gain.exponentialRampToValueAtTime(.018, context.currentTime + .08);
        gain.gain.setValueAtTime(.018, context.currentTime + 1.35);
        gain.gain.exponentialRampToValueAtTime(.0001, context.currentTime + 1.65);
        wobble.connect(wobbleGain).connect(oscillator.frequency);
        oscillator.connect(gain).connect(context.destination);
        oscillator.start();
        wobble.start();
        oscillator.stop(context.currentTime + 1.7);
        wobble.stop(context.currentTime + 1.7);
        oscillator.addEventListener("ended", () => context.close());
      } catch (_error) {
        // Keep the visual purr when browser audio is unavailable.
      }
    };
    const closeActions = () => {
      if (actions) actions.hidden = true;
      cat?.setAttribute("aria-expanded", "false");
    };
    const toggleActions = () => {
      if (!actions) return;
      actions.hidden = !actions.hidden;
      cat?.setAttribute("aria-expanded", String(!actions.hidden));
    };
    const updateNapLabel = () => {
      const napButton = companion.querySelector('[data-ragdoll-action="nap"]');
      if (!napButton) return;
      const napping = companion.classList.contains("is-napping");
      napButton.textContent = napping ? (isZh ? "\u53eb\u9192\u86cb\u86cb" : "Wake Dandan") : (isZh ? "\u8ba9\u86cb\u86cb\u4f11\u606f" : "Let Dandan nap");
    };

    if (localStorage.getItem(hiddenKey) === "1") companion.classList.add("is-hidden");
    if (localStorage.getItem(napKey) === "1") companion.classList.add("is-napping");
    if (!companion.classList.contains("is-hidden")) applySavedPosition();
    updateNapLabel();
    holdRestingFrame(() => companion.classList.add("is-ready"));

    cat?.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      const bounds = companion.getBoundingClientRect();
      dragState = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, left: bounds.left, top: bounds.top, moved: false };
      cat.setPointerCapture(event.pointerId);
      closeActions();
    });
    cat?.addEventListener("pointermove", (event) => {
      if (dragState && dragState.pointerId === event.pointerId) {
        const dx = event.clientX - dragState.startX;
        const dy = event.clientY - dragState.startY;
        if (Math.hypot(dx, dy) > 4) {
          dragState.moved = true;
          companion.classList.add("is-dragging");
          setPosition(dragState.left + dx, dragState.top + dy);
        }
        return;
      }
      const bounds = cat.getBoundingClientRect();
      const offset = (event.clientX - bounds.left) / bounds.width - 0.5;
      companion.style.setProperty("--cat-tilt", `${(offset * 10).toFixed(1)}deg`);
    });
    const finishDrag = (event) => {
      if (!dragState || dragState.pointerId !== event.pointerId) return;
      const moved = dragState.moved;
      dragState = null;
      companion.classList.remove("is-dragging");
      companion.style.setProperty("--cat-tilt", "0deg");
      if (cat?.hasPointerCapture(event.pointerId)) cat.releasePointerCapture(event.pointerId);
      if (moved) {
        const bounds = companion.getBoundingClientRect();
        setPosition(bounds.left, bounds.top, true);
      } else if (actions) {
        window.clearTimeout(blinkTimer);
        toggleActions();
        if (!companion.classList.contains("is-napping")) {
          stopFrameAnimation();
          setPose("wave");
          returnToRestingPose(1300);
        }
        showSpeech(companion.classList.contains("is-napping") ? (isZh ? "\u86cb\u86cb\u5728\u6253\u76f9\u3002" : "Dandan is dozing.") : (isZh ? "\u4eca\u5929\u4e5f\u8981\u7a33\u7a33\u7684\u3002" : "Steady trades today."));
      }
    };
    cat?.addEventListener("pointerup", finishDrag);
    cat?.addEventListener("pointercancel", finishDrag);
    cat?.addEventListener("click", (event) => {
      if (event.detail !== 0) return;
      toggleActions();
      if (!companion.classList.contains("is-napping")) {
        window.clearTimeout(blinkTimer);
        stopFrameAnimation();
        setPose("wave");
        returnToRestingPose(1300);
      }
      showSpeech(isZh ? "\u4eca\u5929\u4e5f\u8981\u7a33\u7a33\u7684\u3002" : "Steady trades today.");
    });
    cat?.addEventListener("pointerleave", () => {
      if (!dragState) companion.style.setProperty("--cat-tilt", "0deg");
    });

    companion.querySelectorAll("[data-ragdoll-action]").forEach((button) => {
      button.addEventListener("click", () => {
        const action = button.dataset.ragdollAction;
        if (action === "pet") {
          window.clearTimeout(blinkTimer);
          stopFrameAnimation();
          companion.classList.remove("is-petted");
          void companion.offsetWidth;
          companion.classList.add("is-petted", "is-purring");
          setPose("pet");
          playPurr();
          showSpeech(isZh ? "\u547c\u565c\u547c\u565c..." : "Prrrrr...");
          window.setTimeout(() => companion.classList.remove("is-petted", "is-purring"), 1800);
          returnToRestingPose(1850);
        } else if (action === "reminder") {
          window.clearTimeout(blinkTimer);
          stopFrameAnimation();
          setPose("wave");
          showSpeech(reminders[reminderIndex++ % reminders.length]);
          returnToRestingPose(1900);
        } else if (action === "nap") {
          window.clearTimeout(blinkTimer);
          stopFrameAnimation();
          const napping = companion.classList.toggle("is-napping");
          companion.classList.add("is-transitioning");
          localStorage.setItem(napKey, napping ? "1" : "0");
          updateNapLabel();
          setPose("stretch");
          window.clearTimeout(poseTimer);
          playSpriteAnimation(napping ? "sleep" : "wake", () => {
            companion.classList.remove("is-transitioning");
            setPose(napping ? "sleep" : "idle");
          });
          showSpeech(napping ? (isZh ? "\u5148\u772f\u4e00\u4f1a\u513f\u3002" : "A short nap.") : (isZh ? "\u9192\u5566\uff0c\u7ee7\u7eed\u770b\u76d8\u3002" : "Awake and watching."));
        } else if (action === "home") {
          localStorage.removeItem(positionKey);
          companion.style.removeProperty("left");
          companion.style.removeProperty("top");
          companion.style.removeProperty("right");
          companion.style.removeProperty("bottom");
          companion.classList.remove("is-left-side");
          showSpeech(isZh ? "\u56de\u5230\u6211\u7684\u89d2\u843d\u4e86\u3002" : "Back in my corner.");
        } else if (action === "hide") {
          window.clearTimeout(blinkTimer);
          stopFrameAnimation();
          companion.classList.add("is-hidden");
          localStorage.setItem(hiddenKey, "1");
          companion.style.removeProperty("left");
          companion.style.removeProperty("top");
          companion.style.removeProperty("right");
          companion.style.removeProperty("bottom");
        }
        closeActions();
      });
    });
    restore?.addEventListener("click", () => {
      companion.classList.remove("is-hidden");
      localStorage.setItem(hiddenKey, "0");
      applySavedPosition();
      showSpeech(isZh ? "\u6211\u56de\u6765\u4e86\u3002" : "I am back.");
      scheduleBlink();
    });
    document.addEventListener("pointerdown", (event) => {
      if (!companion.contains(event.target)) closeActions();
    });
    window.addEventListener("resize", () => {
      if (companion.classList.contains("is-hidden") || !companion.style.left) return;
      const bounds = companion.getBoundingClientRect();
      setPosition(bounds.left, bounds.top, true);
    });
  };
  bindRagdollCompanion();

  const bindOptionPositionGroups = () => {
    document.querySelectorAll("[data-option-group-toggle]").forEach((button) => {
      button.addEventListener("click", () => {
        const groupId = button.dataset.optionGroupToggle;
        const rows = document.querySelectorAll(`[data-option-group-row="${groupId}"]`);
        const expanded = button.getAttribute("aria-expanded") === "true";
        button.setAttribute("aria-expanded", String(!expanded));
        rows.forEach((row) => {
          row.hidden = expanded;
        });
      });
    });
  };
  bindOptionPositionGroups();

  const loadEarningsReminder = (force = false) => {
    const currentPanel = document.querySelector("[data-earnings-reminder]");
    if (!currentPanel) return;
    currentPanel.classList.add("is-loading");
    const requestUrl = force ? "/earnings-reminder?refresh=1" : "/earnings-reminder";
    fetch(requestUrl, { headers: { "X-Requested-With": "fetch" }, cache: "no-store" })
      .then((response) => response.ok ? response.text() : Promise.reject())
      .then((html) => {
        const template = document.createElement("template");
        template.innerHTML = html.trim();
        const nextPanel = template.content.querySelector("[data-earnings-reminder]");
        if (!nextPanel) return;
        currentPanel.replaceWith(nextPanel);
        applyLanguage(nextPanel);
      })
      .catch(() => currentPanel.classList.remove("is-loading"));
  };

  document.addEventListener("click", (event) => {
    const refresh = event.target.closest("[data-earnings-reminder-refresh]");
    if (!refresh) return;
    event.preventDefault();
    loadEarningsReminder(true);
  });
  loadEarningsReminder();

  const hydrateSoftPage = (root) => {
    if (!root) return;
    applyLanguage(root);
    bindLegacyTradeForm(root);
    bindPlaidConnect(root);
    bindSortableTables(root);
    bindDeleteButtons(root);
    bindPerformanceChart(root.querySelector(".performance-panel"));
    bindCapitalUsageCharts(root);
    bindJin10Feed();
    bindGreedyFearFeed();
    bindOptionsCalculator();
    bindPortfolioPie();
    bindPortfolioBenchmarks(root);
    bindPortfolioChart(root);
    syncPortfolioAccountSelection();
    bindPortfolioAutoSync();
    bindHoldingsLive();
    bindSymbolPricePanel();
    bindSymbolValuation(root);
    bindEarningsBetForm();
    bindOtherOptionForm();
    bindUnifiedOptionForm();
    bindDashboardSplitter();
    bindSymbolsSplitter();
    bindLedgerSplitters();
    bindOptionPositionGroups();
    bindDashboardHero(root);
    bindCollapsiblePanels(root);
    bindPolishEffects();
    loadEarningsReminder();
  };

  const syncNavigationState = (nextDocument) => {
    const currentNav = document.querySelector("header nav");
    const nextNav = nextDocument.querySelector("header nav");
    if (!currentNav || !nextNav) return;
    const nextLinks = Array.from(nextNav.querySelectorAll("a[href]"));
    currentNav.querySelectorAll("a[href]").forEach((link) => {
      const match = nextLinks.find((candidate) => candidate.getAttribute("href") === link.getAttribute("href"));
      link.classList.toggle("active", Boolean(match?.classList.contains("active")));
    });
    const nextMenus = Array.from(nextNav.querySelectorAll(".nav-menu"));
    currentNav.querySelectorAll(".nav-menu").forEach((menu, index) => {
      menu.classList.toggle("active", Boolean(nextMenus[index]?.classList.contains("active")));
    });
    document.dispatchEvent(new CustomEvent("option-ledger:navigation-updated"));
  };

  let softNavigationRequest = null;
  const softNavigate = async (target, pushHistory = true) => {
    const destination = new URL(target, location.href);
    if (activeLanguage === "zh" && !destination.searchParams.has("lang")) destination.searchParams.set("lang", "zh");
    const currency = localStorage.getItem("optionLedgerCurrency") || "usd";
    if (currency === "rmb" && !destination.searchParams.has("currency")) destination.searchParams.set("currency", "rmb");
    const currentMain = document.querySelector("main");
    if (!currentMain) {
      location.assign(destination.href);
      return;
    }
    softNavigationRequest?.abort();
    softNavigationRequest = new AbortController();
    document.documentElement.classList.add("is-soft-navigating");
    currentMain.setAttribute("aria-busy", "true");
    try {
      const response = await fetch(destination, {
        headers: { "X-Requested-With": "fetch" },
        cache: "no-store",
        signal: softNavigationRequest.signal
      });
      if (!response.ok) throw new Error(`Navigation failed: ${response.status}`);
      const nextDocument = new DOMParser().parseFromString(await response.text(), "text/html");
      const nextMain = nextDocument.querySelector("main");
      if (!nextMain) throw new Error("Navigation response is missing the main region.");
      const replacement = document.importNode(nextMain, true);
      currentMain.replaceWith(replacement);
      document.title = nextDocument.title || document.title;
      syncNavigationState(nextDocument);
      const finalUrl = new URL(response.url || destination.href, location.href);
      if (pushHistory) history.pushState({ softNavigation: true }, "", `${finalUrl.pathname}${finalUrl.search}${finalUrl.hash}`);
      document.documentElement.dataset.softNavigationCount = String(Number(document.documentElement.dataset.softNavigationCount || "0") + 1);
      hydrateSoftPage(replacement);
      window.scrollTo({ top: 0, behavior: "auto" });
    } catch (error) {
      if (error.name === "AbortError") return;
      location.assign(destination.href);
    } finally {
      document.documentElement.classList.remove("is-soft-navigating");
      document.querySelector("main")?.removeAttribute("aria-busy");
    }
  };

  const canSoftNavigate = (destination) => {
    if (destination.origin !== location.origin || destination.hash) return false;
    if (destination.pathname.startsWith("/static/")) return false;
    return !new Set([
      "/__reload_id", "/ticker-tape", "/performance", "/strategy-performance",
      "/capital-usage", "/performance-controls", "/calendar", "/market-news/data",
      "/sentiment/data", "/earnings-reminder", "/holdings/data"
    ]).has(destination.pathname) && !destination.pathname.endsWith("/price");
  };

  document.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest("a[href]");
    if (!link || link.target || link.hasAttribute("download") || link.hasAttribute("data-no-ajax")) return;
    const destination = new URL(link.href, location.href);
    if (!canSoftNavigate(destination)) return;
    event.preventDefault();
    softNavigate(destination.href);
  });

  document.addEventListener("submit", (event) => {
    if (event.defaultPrevented) return;
    const form = event.target.closest("form");
    if (!form || (form.method || "get").toLowerCase() !== "get" || form.target || form.hasAttribute("data-no-ajax")) return;
    const destination = new URL(form.action || location.href, location.href);
    destination.search = new URLSearchParams(new FormData(form)).toString();
    if (!canSoftNavigate(destination)) return;
    event.preventDefault();
    softNavigate(destination.href);
  });

  window.addEventListener("popstate", (event) => {
    if (event.state?.portfolioChartRange) return;
    softNavigate(location.href, false);
  });

  let reloadId = null;
  const syncReloadId = () => {
    fetch("/__reload_id", { cache: "no-store" })
      .then((response) => response.ok ? response.text() : null)
      .then((current) => {
        if (!current) return;
        if (reloadId && reloadId !== current) window.location.reload();
        reloadId = current;
      })
      .catch(() => {});
  };
  syncReloadId();
  window.setInterval(syncReloadId, 1000);
  applyLanguage();
});
