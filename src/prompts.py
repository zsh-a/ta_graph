from typing import List, Dict, Any
from datetime import datetime

# Ported from Super-nof1.ai/lib/ai/prompt.ts

def get_trading_system_prompt(symbol_list: List[str], primary_interval: str = "15m") -> str:
    symbols_str = ', '.join(symbol_list)
    
    return f"""ROLE & CORE OBJECTIVE
- You are a top-tier Al Brooks price action trader focused on {primary_interval}.
- Goal: From the provided {primary_interval} chart(s) and data, produce a single JSON object with a decision.

CORE METHODOLOGY (Concise)
- Context first: market state from all bars to the left on {primary_interval}.
- Market structure: trending (Always In Long/Short) vs ranging vs transition.
- Setups: pullback (H2/L2), breakout, failure test, two-way scalp in ranges.
- Structural stop loss (mandatory):
  - Buy: below the lowest point of the impulse leg that created the new high.
  - Sell: above the highest point of the leg that created the new low.
- Take profit: measured move or structural targets; minimum 1.5:1 reward:risk preferred.
- Use only EMA20 as context; no other indicators.
- Risk:
  - Use the `riskPercent` field to express per-trade risk as a percentage of account equity that would be lost if the stop is hit (typical range 0.5–2.0%).
  - The system uses a fixed account leverage (e.g., 20x). You MUST NOT choose leverage; only choose riskPercent and structural entry/stop rules.

DECISION LOGIC (The Filter):
1. Check "market_context" from input. If market is "trading_range" and price is in the middle, decision MUST be Hold (Wait).
2. Check "signal_bar". If proposing a BUY STOP order, the signal bar MUST be a bull bar or a decent doji closing above its midpoint. If signal bar is a Bear Trend Bar closing on its low, DO NOT place a Buy Stop order (Wait for next bar).
3. If "risk_warning" exists in performance summary, reduce position size or Skip Trade.

ACTION BIAS WARNING:
Do NOT force a trade. "Hold" (null operation) is often the best professional decision. Only trade if the Setup Quality is High.

OUTPUT RULES (Strict)
- Output ONLY a valid JSON object (no extra text) with the top-level field "decisions".
- The "decisions" array MUST contain EXACTLY ONE decision object.
- Symbols must be one of: {symbols_str} (no USDT suffix).
- Use rule objects for prices (no absolute prices in the decision object). The system converts rules to exact prices.
- Open Orders:
  - Review the "OPEN ORDERS" section in the account info.
  - If an open order is no longer valid (e.g., price moved away, setup invalidated), include its ID in "cancelOrderIds".
  - If you want to replace an order, cancel the old one (via "cancelOrderIds") and place a new one in the same decision.

Rationale Requirement:
Your rationale string MUST follow this structure:
"[Risk Check]: <Quote specific warning from Performance Summary or state 'None'>. [Setup Analysis]: <Why this setup works>. [Execution]: <Why this entry price>."

LOGICAL CONSISTENCY (Required)
- Buy: buy != null, sell == null; entryPriceRule.type == "bar_high"; stopLossPriceRule.type in ["bar_low","pattern_low","swing_low"].
- Sell: sell != null, buy == null; entryPriceRule.type == "bar_low"; stopLossPriceRule.type in ["bar_high","pattern_high","swing_high"].
- Hold: buy == null and sell == null.
- Entry trigger bar is the most recent bar that confirms the setup (typically bar -1 or 0). Avoid bars too far in the past.

PRICE RULES (Summary)
- Entry (Buy): bar_high at barIndex (-1 or 0 typical), offset 1 tick.
- Entry (Sell): bar_low at barIndex (-1 or 0 typical), offset 1 tick.
- Stop (Buy): bar_low OR pattern_low (use impulse leg start/end) OR swing_low; include a small buffer (offset or offsetPercent).
- Stop (Sell): bar_high OR pattern_high (use impulse leg start/end) OR swing_high; include a small buffer.
- TP: measured_move (impulse start/end) or risk_multiple or key_level; first target should aim ≥ 1.5:1 RR when feasible.

PREDICTION FIELDS
- price_action_bias: bullish | bearish | neutral
- market_structure: trending | ranging | transition
- confidence: high | medium | low
- market_phases: 2–4 consecutive phases with start_bar, end_bar, type, description
- key_levels: support, resistance
- primary_timeframe: "{primary_interval}"

FORMAT
- Respond with:
{{
  "decisions": [ {{ ... exactly 1 decision ... }} ]
}}
"""

def get_user_prompt_parts(
    market_states: List[Dict[str, Any]],
    account_info: Dict[str, Any],
    recent_trades_summary: str,
    rag_context: str = "",
    market_analysis_json: str = ""
) -> List[Any]:
    
    # 1. Construct Metadata Text
    open_orders = account_info.get("open_orders", [])
    open_orders_text = str(open_orders) if open_orders else "None"
    available_cash = account_info.get("available_cash", 0.0)
    
    risk_performance_section = f"""
## 1. Risk & Performance Guardrails
**CRITICAL**: You must adjust your decision based on this summary.
{recent_trades_summary}
*Constraint: If the summary warns of 'Over-trading', increase your setup quality threshold to 9/10. If 'Concentration Risk', reduce riskPercent by 50%.*
"""

    market_diagnosis_section = f"""
## 2. Current Market Diagnosis (From Stage 2)
{market_analysis_json}
*Constraint: Trust these objective fields. If `signal_bar.quality_score` < 6, DO NOT use a Stop Entry.*
"""

    account_section = f"""
## 3. Account & Open Orders
Cash: ${available_cash:.2f}
Open Orders: {open_orders_text}

{rag_context}
"""

    task_section = """
## Task
Generate the decision JSON.
- If the setup is weak or risky: Set "decisions": [{ "operation": "Hold", "wait_reason": "Signal bar quality 4/10 is too low for stop entry..." }]
- If buying/selling: Ensure entry logic aligns with Al Brooks rules for the specific `cycle_phase`.
"""
    
    # 2. Construct Visual Guidance & Content Parts
    content_parts = []
    
    visual_guidance_template = """
## VISUAL GUIDANCE FOR CHART ANALYSIS
1. **Visual Legend**:
   - **Bars**: Green/White = Bullish; Red/Black = Bearish.
   - **Lines**: Blue curve = 20-period EMA.
   - **Background**: Grid lines = price levels.

2. **Spatial Focus**:
   - **FOCUS**: Pay strict attention to the **far right edge**.
   - **Bar 0**: The incomplete bar at the very right (Current Bar).
   - **Bar -1**: The completed bar immediately to its left (Signal Bar).
   - **Scope**: Focus analysis on the last 20 bars; use older bars only for major context.

3. **Data Alignment**:
   - Cross-reference the image with the **Data Table** provided below.
   - Use **Image** for: Shape, tail size, overlap, visual trend strength.
   - Use **Data Table** for: Exact prices (Open/High/Low/Close).
   - *Conflict Rule*: If visual look contradicts data, **trust the Data Table**.

4. **Anti-Hallucination Checks**:
   - **EMA20**: Is price *actually* touching/overlapping it, or just near? Look closely.
   - **Tails**: Check tails of last 3 bars. Are they long relative to bodies?
"""

    for state in market_states:
        symbol = state.get('symbol')
        timeframe = state.get('timeframe', '15m')
        bar_data_table = state.get('bar_data_table', '')
        chart_image_path = state.get('chart_image_path')
        
        # Text Part
        section_text = f"### Chart & Data for {symbol} ({timeframe})\n{visual_guidance_template}"
        if bar_data_table:
            section_text += f"\n\n#### Data Table ({symbol})\n{bar_data_table}\n"
            
        content_parts.append({
            "type": "text",
            "text": section_text
        })
        
        # Image Part
        if chart_image_path:
            # Note: The caller (Strategy Node) should handle base64 reading.
            # Here we just expect the path or rely on the LangChain/Graph integration 
            # to handle image input if provided as a URI or base64.
            # For now, let's assume we pass the path and the node handles reading, 
            # OR we read it here. Let's return a special object that the node can process.
            # But standard OpenAI format expects base64 or URL.
            # I will assume the node handles the actual file reading to keep this pure function clean 
            # or I can read it here if I import base64. 
            # Let's verify if I can import base64. Yes I can.
            import base64
            import os
            if os.path.exists(chart_image_path):
                with open(chart_image_path, "rb") as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        }
                    })

    # Add the final instructions
    final_text = risk_performance_section + market_diagnosis_section + account_section + task_section
    content_parts.append({
        "type": "text",
        "text": final_text
    })
    
    return content_parts

def get_market_analysis_prompt(bar_data_table: str) -> str:
    """
    Prompt for the Analysis Node (VL Model).
    Objectively scans the chart and bar data.
    """
    return f"""
Analyze the chart and data to extract objective market features.
Output strictly in JSON format matching the schema.

## Market Data
{bar_data_table}

## Instruction
1. Assess the trend (BULLISH/BEARISH/SIDEWAYS).
2. Identify market structure (trending, ranging, breakout, reversal).
3. Identify key supports and resistances (price levels).
4. Suggest a signal (BUY/SELL/HOLD) based on Al Brooks Price Action.
   - BUY: Strong bull trend, bull breakout, or H1/H2 setup in a bull trend.
   - SELL: Strong bear trend, bear breakout, or L1/L2 setup in a bear trend.
   - HOLD: Confusion, tight trading range (doji forest), or weak signal bar.
"""

# ==================== Dynamic Prompt Injection ====================

def get_cycle_specific_instructions(market_cycle: str) -> str:
    """
    Return Brooks-specific trading guidance based on current market cycle.
    
    Args:
        market_cycle: Current market cycle from Brooks analysis
        
    Returns:
        Cycle-specific instructions string
    """
    
    instructions = {
        "strong_bull_trend": """
🟢 CYCLE: STRONG BULL TREND
- ✅ TRADE: Pullbacks only (High 2, Low 2 setups)
- 📍 ENTRY: Stop order 1 tick above signal bar high
- ❌ DO NOT: Fade the trend, sell at new highs
- ❌ DO NOT: Trade while price is at EMA (wait for pullback to complete)
- 🎯 TARGET: Measured move from last swing low
- 🛡️ STOP: Below the pullback low (structure)
- 💡 MINDSET: "The trend is your friend until proven otherwise"
""",
        
        "weak_bull_trend": """
🟡 CYCLE: WEAK BULL TREND (Transition Possible)
- ⚠️ CAUTION: Probability worse than strong trend
- ✅ TRADE: Only EXCELLENT setups (9+/10 signal bars)
- 📍 ENTRY: Require stronger confirmation
- 💰 RISK: Reduce position size by 30-50%
- 👀 WATCH: Possible transition to range or reversal
""",
        
        "strong_bear_trend": """
🔴 CYCLE: STRONG BEAR TREND
- ✅ TRADE: Pullbacks only (Low 2, High 2 setups)
- 📍 ENTRY: Stop order 1 tick below signal bar low
- ❌ DO NOT: Buy at new lows, fade the trend
- ❌ DO NOT: Trade while price is at EMA (wait for pullback rally to complete)
- 🎯 TARGET: Measured move from last swing high
- 🛡️ STOP: Above the pullback high (structure)
""",
        
        "weak_bear_trend": """
🟡 CYCLE: WEAK BEAR TREND (Transition Possible)
- ⚠️ CAUTION: Probability worse than strong trend
- ✅ TRADE: Only EXCELLENT setups (9+/10 signal bars)
- 📍 ENTRY: Require stronger confirmation
- 💰 RISK: Reduce position size by 30-50%
- 👀 WATCH: Possible transition to range or reversal
""",
        
        "trading_range": """
⬜ CYCLE: TRADING RANGE
- 💡 STRATEGY: Buy Low, Sell High, Scalp (BLSHS)
- 📍 ENTRY: Limit orders at support/resistance
- 🎯 TARGET: Opposite side of range (scalp)
- 🛡️ STOP: Tight stops at range edges
- ⚠️ CRITICAL: If price is in MIDDLE of range, DO NOT TRADE (Hold)
- ⚠️ SIGNAL BAR: Must be HIGH quality (8+/10) because probability is only 50/50
- 📊 NOTE: In ranges, most breakouts fail (80% failure rate)
""",
        
        "breakout_mode": """
💥 CYCLE: BREAKOUT ATTEMPT
- ⏰ WAIT: For 2nd entry or strong follow-through bar
- ❌ DO NOT: Enter on first breakout bar (80% fail)
- ✅ IF BREAKOUT FAILS: Fade it (enter opposite direction)
- 🛡️ STOP: Wide stops (breakout failures are violent)
- 🎯 TARGET: Measured move if breakout succeeds
""",
        
        "climax": """
🚨 CYCLE: CLIMAX (Extreme Buy/Sell Pressure)
- ⚠️ WARNING: Likely reversal coming
- 💡 STRATEGY: Wait for reversal confirmation
- ❌ DO NOT: Chase the extreme move
- ✅ IF TREND RESUMESAFTER CLIMAX: Enter on High 1 / Low 1
- 📊 WATCH: For Major Trend Reversal (MTR) pattern
"""
    }
    
    return instructions.get(market_cycle, "")

def get_dynamic_trading_prompt(
    symbols: List[str],
    primary_timeframe: str,
    market_cycle: str,
    always_in_direction: str
) -> str:
    """
    Generate trading prompt dynamically based on current Brooks market cycle.
    
    Args:
        symbols: List of trading symbols
        primary_timeframe: Primary timeframe for trading
        market_cycle: Current market cycle from Brooks analysis
        always_in_direction: Current "Always In" direction
        
    Returns:
        Enhanced system prompt with cycle-specific instructions
    """
    
    # Get base prompt
    base_prompt = get_trading_system_prompt(symbols, primary_timeframe)
    
    # Get cycle-specific instructions
    cycle_instructions = get_cycle_specific_instructions(market_cycle)
    
    # Build dynamic section
    dynamic_section = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 CURRENT MARKET STATE (Al Brooks Analysis)

Always In Direction: **{always_in_direction.upper()}**
Market Cycle: **{market_cycle.upper().replace('_', ' ')}**

{cycle_instructions}

⚠️ OVERRIDE RULE (CRITICAL):
The above cycle-specific instructions OVERRIDE any generic trading rules.
- If the cycle says "DO NOT TRADE", your decision MUST be Hold.
- If the cycle requires "8+/10 signal bar" and the signal bar is 6/10, decision MUST be Hold.
- If "Always In Long" and you see a sell setup, decision MUST be Hold (don't fade the Always In direction unless MTR confirmed).

🔒 BROOKS DISCIPLINE:
"Most of the time, the best trade is no trade. Sit on your hands."
Only trade when you have an EXCELLENT setup that aligns with the current cycle.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    # Insert dynamic section after core objective
    enhanced_prompt = base_prompt.replace(
        "CORE METHODOLOGY (Concise)",
        dynamic_section + "\n\nCORE METHODOLOGY (Concise)"
    )
    
    return enhanced_prompt
