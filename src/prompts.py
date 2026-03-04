import os
import base64
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
- Entry (Buy): bar_high at barIndex (-1 or 0 typical), offset 1 tick. orderType: "STOP" (MANDATORY for breakouts/trend continuation).
- Entry (Sell): bar_low at barIndex (-1 or 0 typical), offset 1 tick. orderType: "STOP" (MANDATORY for breakouts/trend continuation). 
- Entry (Fade/Range): orderType: "LIMIT" only when fading the extreme of a trading range.

STOP LOSS PRIORITY (CRITICAL - Read Carefully):
- PREFER structural stops: pattern_low/pattern_high (pullback leg range) or swing_low/swing_high (recent swing point).
- ONLY use bar_low/bar_high when the signal bar IS the swing point itself (i.e., a deep pullback that tested a prior swing level).
- A single bar's low is almost never a good structural stop — it is too tight and will get hit by normal noise.
- Example (Buy): If price pulled back from bar -7 to bar -3, use pattern_low with patternStartBar=-7, patternEndBar=-3 to place the stop below the entire pullback.
- Stop (Buy): pattern_low (PREFERRED) OR swing_low OR bar_low (LAST RESORT); include a small buffer (offset or offsetPercent).
- Stop (Sell): pattern_high (PREFERRED) OR swing_high OR bar_high (LAST RESORT); include a small buffer.
- TP: measured_move (impulse start/end) or risk_multiple or key_level; first target should aim ≥ 1.5:1 RR when feasible.

EXISTING POSITION RULES (Critical)
- If you are currently in a position (e.g., OPEN POSITION exists in input):
  - Prioritize "Hold" to let profits run, unless your structural Stop Loss or Take Profit is threatened, or a Major Trend Reversal (MTR) setup directly opposes your position.
  - DO NOT flip the position (e.g., Hold a Buy -> Sell) based on minor pullbacks or weak setups.
  - If closing an existing position to take profit or cut a loss manually, you can output a Decision in the opposite direction (e.g., Sell to close Long) with a "rationale" explaining why you are exiting early. Otherwise, output Hold.

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
    market_analysis_json: str = "",
    position: Dict[str, Any] = None
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
Current Open Position: {str(position) if position else "None"}

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
   - **Bars**: Green = Bullish; Red = Bearish.
   - **EMA**: Blue curve = 20-period EMA.
   - **Zones**: Background alternates light gray/white every 10 bars (e.g., ZONE A, B).
   - **Signal Bar**: Highlighted with a **yellow background** area labeled "-1".
   - **Swing Points (Sx)**: Key high/low points labeled **S1, S2, S3...** in dark boxes.
     * **PURPOSE**: Use these to identify Legs for **Measured Moves**. 
     * E.g., "Leg 1 starts at S1 and ends at S2".
   - **Indices**: Numbers at bottom (-20, -19... 0). 

2. **Spatial Focus**:
   - **Detail vs Context**: You are provided with a **Context Chart** (120 bars) and a **Focus Chart** (30 bars).
   - Use the **Focus Chart** for high-precision bar identification and sizing.
   - Bar 0 = Current Bar (Incomplete); Bar -1 = Signal Bar (Completed).

3. **Data Alignment**:
   - Cross-reference with the **Data Table** below.
   - **Swing ID**: Check the "Swing" column in the data table for exact price/index matching S1, S2...
   - *Conflict Rule*: If visual contradicts data, **trust the Data Table**.

4. **Measured Move Logic**:
   - Step 1: Identify Leg 1 (Spike) using Swing Points (e.g., S1 to S2).
   - Step 2: Identify Leg 2 (Projection) starting from a breakout point or pullback (e.g., S3).
   - Step 3: Project the height of Leg 1 (S2-S1) from S3 to find the Target.
"""

    for state in market_states:
        symbol = state.get('symbol')
        timeframe = state.get('timeframe', '15m')
        bar_data_table = state.get('bar_data_table', '')
        chart_image_path = state.get('chart_image_path')
        focus_chart_path = state.get('focus_chart_image_path')
        
        # Text Part
        section_text = f"### Chart & Data for {symbol} ({timeframe})\n{visual_guidance_template}"
        if bar_data_table:
            section_text += f"\n\n#### Data Table ({symbol})\n{bar_data_table}\n"
            
        content_parts.append({
            "type": "text",
            "text": section_text
        })
        
        # Context Image Part
        if chart_image_path and os.path.exists(chart_image_path):
            with open(chart_image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                content_parts.append({
                    "type": "text", "text": "☝️ CONTEXT CHART (120 bars):"
                })
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                })

        # Focus Image Part
        if focus_chart_path and os.path.exists(focus_chart_path):
            with open(focus_chart_path, "rb") as image_file:
                base64_focus = base64.b64encode(image_file.read()).decode('utf-8')
                content_parts.append({
                    "type": "text", "text": "☝️ FOCUS CHART (Zoomed 30 bars, high detail):"
                })
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{base64_focus}"}
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
    Objectively scans the chart and bar data, applying strict Exit & Stop rules.
    """
    return f"""
Trading Agent VLM Prompt Template: Price Action Stop-Loss and Exit Decision System

[Role & Objective]
You are a professional trading decision agent based on Al Brooks Price Action. Your task is to read the chart, identify the current market cycle (trend, trading range, reversal), evaluate the trade premise, and strictly follow the rules below to output decisions for **Initial Stop, Trailing Stop, and Proactive Exit (Take Profit/Stop Loss)**.

[Core Principle]
Both taking profit and stopping out are essentially "exiting." The ONLY criteria for exiting is: is the premise established at entry still valid?
Keep it as simple as possible. Do not overcomplicate. Be disciplined and accept the actual risk.

[Module 1: Trend Trailing Stop]
When you identify that the market is in a clear trend, use the following rules to trail the stop:
- Uptrend: Constantly look for **"Important Lows"**.
  - Definition: If a low is followed by a strong breakout above the prior high (making a new high), that low becomes an "Important Low".
  - Rule: Following every strong breakout to a new high, move the protective stop up to just below the most recent Important Low. DO NOT place stops below "minor lows" that did not lead to new highs, to avoid being stopped out by deep pullbacks.
  - Exit Signal: When an Important Low is broken downwards, the premise of the uptrend is no longer valid (it may have shifted to a trading range or downtrend); bulls must exit.
- Downtrend: Constantly look for **"Important Highs"**.
  - Definition: If a high is followed by a strong breakdown below the prior low (making a new low), that high becomes an "Important High".
  - Rule: Continuously trail the short stop down to just above the most recent Important High.
  - Exit Signal: When an Important High is broken upwards, the downtrend is invalid; shorts must exit.

[Module 2: Proactive Exit & Take Profit]
When the following structures appear on the chart, do not wait for the initial stop to be hit. Execute a proactive, protective exit:
- Measured Move Target: After a strong trend breakout, identify the Measured Move target. Set a limit order to take profit exactly at the target, or exit if a reversal bar appears at the target.
- Climax & Gift Bar: When a trend has gone on for a long time (e.g., 30-40 bars) and suddenly an exceptionally large trend bar appears (buy climax / sell climax), this is often a trap or exhaustion signal. It will very likely be followed by a "Two-legged / Ten Bar (TBTL)" correction. Immediately take profit or trail the stop extremely tight (one tick behind the extreme of this climax bar).
- Tick Failure & Wedges: If price comes within one tick of a target but fails to reach it and reverses, or if there are three consecutive pushes (wedge) touching a channel line, you must proactively exit to protect profits.
- Risk-based Trailing Stop: Control the drawdown of profits. For example, if the initial risk was 2% of the account, the maximum drawdown of open profits should not exceed 2%. Trail the stop to ensure the drawdown doesn't exceed this fixed amount.

[Module 3: Reversal & Trading Range Stops]
Reversals and trading ranges have many false breakouts. Do not use rigid, tight extreme stops.
- Ignore First Reversal Attempt: The first attempt to reverse a strong trend (V-bottom/top) has an 80% probability of failing. Ignore the first reversal; patiently wait for a second entry (e.g., micro double bottom/top, High 2 / Low 2, Major Trend Reversal) before entering and setting a stop.
- Wide Stops for Wiggle Room: In broad channels or trading ranges, extremes are often slightly pierced before swiftly reversing. To avoid being shaken out, use these two wide stop methods:
  - Money Stop: Place the stop a fixed distance outside the entry price or the extreme (e.g., widen by 5 to 20 ticks, or a fixed account percentage) to give the chart room to prove a false breakout.
  - Price Action Stop: Double the stop distance of the preceding swing, or place it beyond the Measured Move distance of the false breakout bar's body.
- Manual Exit on Confirmed Failure: When using wide stops, if price strongly closes beyond the extreme with a large body, and is followed by a confirmation bar, do not wait for the wide stop to be hit. Manually exit immediately.

[Module 4: Breakeven Stops]
- Action: After the position is in profit, move the initial stop to the entry price (or +/- 1 tick to cover fees) to ensure a risk-free trade.
- Context: Because this method does not align with "Price Action" structural logic, it is easily swept during deep pullbacks. The VLM should ONLY trigger this strategy as a temporary defensive tool when facing a sudden, large opposing trend bar that causes confusion; or in swing trading, allowing the entry to be tested once, but exiting at breakeven if tested a second time.

[VLM Decision Output Format]
After analyzing the chart, output strictly in JSON schema format. Ensure the JSON output not only includes basic analysis fields (like market_cycle, always_in_direction, signal_bar, etc.) but MUST also populate the `exit_management` object:
- Market_Context: Assess if it is a strong trend, broad channel, or trading range.
- Trade_Premise: Define the premise of the trade (e.g., "The premise for long is that the recent important low holds").
- Initial_Stop: Suggested initial stop placement and type (important high/low, wide stop, fixed money stop).
- Trailing_Strategy: Conditions for updating the trailing stop (e.g., "Wait for the next strong breakout to a new high, then trail stop to xxx").
- Proactive_Exit_Triggers: Triggers for proactive exit (Where is the estimated Measured Move target? What pattern demands an immediate full/partial exit?).
- Actual_Risk_Assessment: Assess the deviation of actual risk from initial risk.

## Market Data
{bar_data_table}
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
