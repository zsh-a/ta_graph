# Bitget 交易符号格式说明

## 重要：Symbol 格式要求

### Bitget 期货交易

Bitget 的**永续合约**（USDT 本位）需要使用特殊的 symbol 格式：

```
格式: {基础货币}/{报价货币}:{结算货币}
示例: BTC/USDT:USDT
```

### 正确格式 ✅

```python
# Bitget 永续合约
"BTC/USDT:USDT"    # Bitcoin USDT 永续
"ETH/USDT:USDT"    # Ethereum USDT 永续
"SOL/USDT:USDT"    # Solana USDT 永续
```

### 错误格式 ❌

```python
# 这些格式会失败
"BTC/USDT"         # 缺少结算货币后缀
"BTCUSDT"          # 无分隔符
"BTC-USDT"         # 错误的分隔符
```

## 自动格式化

我们的代码已经提供了 `normalize_symbol()` 辅助函数来自动处理：

```python
from src.trading.exchange_client import normalize_symbol

# 自动添加 :USDT 后缀
symbol = normalize_symbol("BTC/USDT", "bitget")
print(symbol)  # 输出: BTC/USDT:USDT

# 已经是正确格式则不变
symbol = normalize_symbol("ETH/USDT:USDT", "bitget")
print(symbol)  # 输出: ETH/USDT:USDT
```

## 在 place_order 中自动处理

`CCXTExchangeClient.place_order()` 方法会自动标准化 symbol：

```python
from src.trading.exchange_client import get_client

client = get_client("bitget")

# 可以使用简化格式，会自动转换
order = client.place_order(
    symbol="BTC/USDT",      # 会自动转为 BTC/USDT:USDT
    side="buy",
    order_type="limit",
    amount=0.001,
    price=90000
)
```

## 不同交易所对比

| 交易所 | 现货格式 | 永续合约格式 |
|--------|---------|-------------|
| Bitget | `BTC/USDT` | `BTC/USDT:USDT` ✅ |
| Binance | `BTC/USDT` | `BTC/USDT` |
| OKX | `BTC/USDT` | `BTC/USDT-SWAP` |

## 获取所有可用交易对

```python
from src.trading.exchange_client import get_client

client = get_client("bitget")

# 加载市场信息
markets = client.exchange.load_markets()

# 筛选 USDT 永续合约
usdt_futures = [
    symbol for symbol, market in markets.items()
    if market.get('type') == 'swap' and 'USDT' in symbol
]

print(usdt_futures[:5])
# ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT', ...]
```

## 常见错误

### 1. Symbol 格式错误

```python
# ❌ 错误
order = client.place_order("BTC/USDT", "buy", "market", 0.001)
# 可能报错: Invalid symbol

# ✅ 正确
order = client.place_order("BTC/USDT:USDT", "buy", "market", 0.001)
# 或者依赖自动转换
```

### 2. 现货 vs 合约

```python
# 现货交易 (spot)
client.exchange.options['defaultType'] = 'spot'
symbol = "BTC/USDT"

# 合约交易 (swap/futures)
client.exchange.options['defaultType'] = 'swap'
symbol = "BTC/USDT:USDT"  # 需要后缀
```

## 调试技巧

### 验证 Symbol 格式

```python
from src.trading.exchange_client import get_client, normalize_symbol

client = get_client("bitget")

# 测试 symbol
test_symbol = "BTC/USDT"
normalized = normalize_symbol(test_symbol, "bitget")
print(f"原始: {test_symbol}")
print(f"标准化: {normalized}")

# 检查市场是否存在
markets = client.exchange.load_markets()
if normalized in markets:
    print(f"✅ {normalized} 是有效的交易对")
    print(f"   类型: {markets[normalized]['type']}")
else:
    print(f"❌ {normalized} 不存在")
```

### 查看订单详情

```python
# 下单后检查
order = client.place_order("BTC/USDT", "buy", "limit", 0.001, 90000)
print(f"订单ID: {order.id}")
print(f"Symbol: {order.symbol}")  # 应显示 BTC/USDT:USDT
```

## 参考资料

- [Bitget API 文档](https://www.bitget.com/api-doc/contract/market/Get-All-Symbols)
- [CCXT Bitget 说明](https://docs.ccxt.com/#/exchanges/bitget)
- [永续合约介绍](https://www.bitget.com/zh-CN/mix/usdt/BTCUSDT)

## 总结

✅ **记住**：Bitget 永续合约必须使用 `{COIN}/USDT:USDT` 格式  
✅ **使用**：`normalize_symbol()` 辅助函数自动处理  
✅ **测试**：先在沙盒环境验证 symbol 格式
