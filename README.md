# AITradeGame 大模型的交易能力测试项目

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.0+-green.svg)](https://flask.palletsprojects.com/)

基于 Web 的加密货币交易模拟平台，采用 AI 驱动的决策系统。

在线版（维护中）：https://aitradegame.com/

## 本Fork的改动

- 数据源切换为Binance API，增加技术指标种类
- 添加止损止盈自动执行功能
- 改进中文市场分析展示
- 修复部分bug 

## 功能特性

- 实时加密货币市场数据集成
- 基于大语言模型的 AI 交易策略
- 支持杠杆的投资组合管理
- 实时图表的交互式仪表板
- 交易历史与性能跟踪

## 技术栈

- 后端：Python/Flask
- 前端：原生 JavaScript、ECharts
- 数据库：SQLite
- AI 接口：OpenAI 兼容格式（支持 OpenAI、DeepSeek、Claude 等）

## 安装

```bash
pip install -r requirements.txt
python app.py
```

访问地址：`http://localhost:5000`

## 配置

通过 Web 界面添加交易模型：
- 模型名称
- API 密钥
- API 地址
- 模型标识符
- 初始资金

## 项目结构

```
trading_bot/
├── app.py              # Flask 应用主程序
├── trading_engine.py   # 交易逻辑引擎
├── ai_trader.py        # AI 集成模块
├── database.py         # 数据层
├── market_data.py      # 市场数据接口
├── static/             # CSS/JS 资源
├── templates/          # HTML 模板
└── requirements.txt    # Python 依赖
```

## 支持的 AI 模型

兼容 OpenAI 格式的 API：
- OpenAI (gpt-4, gpt-3.5-turbo)
- DeepSeek (deepseek-chat)
- Claude (通过 OpenRouter)

## 使用方法

1. 启动服务器
2. 添加 AI 模型配置
3. 系统自动开始交易
4. 实时监控投资组合

## 注意事项

- 这是一个模拟交易平台（仅限纸面交易）
- 需要有效的 AI 模型 API 密钥
- 需要互联网连接以获取市场数据

## 贡献

欢迎贡献代码！

**免责声明**：本平台仅用于教育和模拟目的，不构成任何投资建议。
