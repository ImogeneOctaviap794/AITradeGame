# 更新说明

## 本次更新内容

### 1. 优化AI决策逻辑 - 减少频繁交易

**问题：** AI每次都在频繁开仓平仓，过度交易

**解决：**
- 提示词中明确强调：对于现有持仓，默认HOLD，除非有明确理由才平仓
- 只有在失效条件触发或技术面明确反转时才平仓
- 避免因小幅波动而频繁调整仓位

### 2. 支持DeepSeek思考模型

**新增功能：**
- 自动检测和提取DeepSeek的`reasoning_content`字段
- 对话记录分为三部分：
  1. 用户提示词（完整的市场数据和指令）
  2. AI思考过程（DeepSeek的推理链）
  3. 交易决策（JSON格式）

**数据库变更：**
- conversations表新增`summary`字段（存储中文总结）
- `cot_trace`字段改为存储reasoning（AI思考）
- `user_prompt`字段存储完整提示词

### 3. 技术指标时间序列化

**改进：**
- 所有技术指标从单个值改为时间序列数组（最近10个值）
- 格式：`[oldest, ..., newest]`
- 包括：价格、EMA、MACD、RSI等

**示例：**
```
旧版: RSI (14-Period): 37.4
新版: RSI indicators (14-Period): [36.968, 36.968, 33.56, 35.343, 41.923, 41.988, 38.641, 40.14, 38.827, 44.74]
```

### 4. 添加运行统计

**新增信息：**
- 交易开始时间
- 总调用次数
- 运行时长（分钟）

**提示词开头：**
```
It has been {minutes} minutes since you started trading.
The current time is {timestamp} and you've been invoked {count} times.
```

## 使用方法

### 查看对话详情

在"AI对话"标签页，每条对话现在显示：

1. **中文总结**（自动展开）- 快速了解本次决策
2. **AI思考过程**（可折叠）- DeepSeek专属，查看推理链
3. **交易决策**（可折叠）- JSON格式的具体决策
4. **用户提示词**（可折叠）- 完整的市场数据和指令

### 重启使用

```bash
# 停止当前服务器 (Ctrl+C)
python app.py
```

## 技术细节

### DeepSeek Reasoning 支持

检测逻辑：
```python
if hasattr(message, 'reasoning_content') and message.reasoning_content:
    reasoning = message.reasoning_content
```

对于非DeepSeek模型，reasoning字段为空，不影响正常使用。

### 时间序列数据

从`market_data.py`的`calculate_technical_indicators()`返回：
- `mid_prices`: 最近10个收盘价
- `ema_20_series`: 最近10个EMA20值  
- `macd_series`: 最近10个MACD值
- `rsi_7_series`: 最近10个RSI(7)值
- `rsi_14_series`: 最近10个RSI(14)值
- `macd_4h_series`: 4小时周期MACD
- `rsi_14_4h_series`: 4小时周期RSI

## 注意事项

1. **首次运行**：运行统计会显示0，这是正常的
2. **DeepSeek模型**：需要使用支持reasoning的模型（如deepseek-reasoner）
3. **数据库**：已自动升级，无需手动操作

