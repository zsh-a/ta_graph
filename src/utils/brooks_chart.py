"""
Brooks-Style Chart Renderer
Generates clean, high-clarity charts matching Al Brooks' minimalist style.
"""

import os
import datetime
from typing import Literal, Any
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from matplotlib.axes import Axes

def create_brooks_style():
    """Create custom mplfinance style for Al Brooks charts"""
    marketcolors = mpf.make_marketcolors(
        up='#00b060',    # Vibrant Green
        down='#ff333a',  # Vibrant Red
        edge={'up': 'black', 'down': 'black'},
        wick={'up': 'black', 'down': 'black'},
        volume='in',
        alpha=1.0
    )
    
    style = mpf.make_mpf_style(
        base_mpf_style='charles',
        marketcolors=marketcolors,
        gridstyle='',  # No grid lines
        y_on_right=True,
        rc={
            'font.size': 9,
            'axes.labelsize': 10,
            'axes.titlesize': 11,
            'xtick.labelsize': 8,
            'ytick.labelsize': 8,
            'figure.facecolor': 'white',
            'axes.facecolor': 'white',
            'axes.edgecolor': 'black',
            'axes.linewidth': 1.0,
        }
    )
    
    return style

def get_swing_points(df: pd.DataFrame, window: int = 5) -> list[dict[str, Any]]:
    """
    Algorithmically identify significant Swing Highs and Swing Lows.
    A point is a swing point if it is the extreme within [t-window, t+window].
    """
    # Handle both capitalized and lowercase column names
    h_col = 'High' if 'High' in df.columns else 'high'
    l_col = 'Low' if 'Low' in df.columns else 'low'
    
    swings = []
    highs = df[h_col].values
    lows = df[l_col].values
    indices = df.index.values
    
    for i in range(window, len(df) - window):
        is_high = True
        is_low = True
        for j in range(i - window, i + window + 1):
            if i == j: continue
            if highs[j] >= highs[i]: is_high = False
            if lows[j] <= lows[i]: is_low = False
        
        if is_high:
            swings.append({
                'idx': int(i), 
                'price': float(highs[i]), 
                'type': 'H', 
                'bar_idx': int(i - (len(df) - 1))
            })
        elif is_low:
            swings.append({
                'idx': int(i), 
                'price': float(lows[i]), 
                'type': 'L', 
                'bar_idx': int(i - (len(df) - 1))
            })
            
    return swings

def annotate_swing_points(ax: Axes, df: pd.DataFrame, swings: list[dict[str, Any]]):
    """
    Visually label swing points with S1, S2, S3...
    """
    h_col = 'High' if 'High' in df.columns else 'high'
    l_col = 'Low' if 'Low' in df.columns else 'low'
    
    for i, s in enumerate(swings):
        # Use pre-calculated global index if available for consistency across charts
        s_id = s.get('global_s_idx', i+1)
        label = f"S{s_id}"
        # Position slightly offset from the extreme
        offset = (df[h_col].max() - df[l_col].min()) * 0.02
        y_pos = s['price'] + offset if s['type'] == 'H' else s['price'] - offset
        
        va = 'bottom' if s['type'] == 'H' else 'top'
        # High contrast label with box
        ax.text(
            s['idx'], y_pos, label,
            fontsize=10,
            fontweight='bold',
            color='white',
            va=va, ha='center',
            bbox=dict(boxstyle='round,pad=0.2', facecolor='#2c3e50', alpha=0.8, edgecolor='none'),
            zorder=10
        )

def annotate_bar_indices(
    ax: Axes,
    df: pd.DataFrame,
    num_bars: int = 20,
):
    """
    Add bar index annotations to the bottom of the chart.
    Optimized for VLM accuracy with rotated indices and zonal shading.
    """
    total_bars = len(df)
    start_idx = max(0, total_bars - num_bars)
    
    # Get y-axis limits to position at the bottom
    ymin, ymax = ax.get_ylim()
    y_range = ymax - ymin
    
    # Zonal Shading: Background color blocks every 10 bars (Zone A, B, C...)
    zone_colors = ['#f0f0f0', '#ffffff'] # Alternating light gray and white
    zone_alpha = 0.5
    
    # Per-bar vertical lines (Very faint for alignment)
    for i in range(total_bars):
        ax.axvline(x=i, color='gray', linestyle=':', linewidth=0.5, alpha=0.08, zorder=0)

    # Zones and Anchors (every 10 bars)
    zone_count = 0
    for i in range(0, total_bars, 10):
        end_idx = min(i + 10, total_bars)
        color = zone_colors[zone_count % 2]
        # Draw background zone
        ax.axvspan(i - 0.5, end_idx - 0.5, color=color, alpha=zone_alpha, zorder=0)
        
        # Add Zone Label at the top
        zone_label = chr(65 + (zone_count % 26)) # Zone A, B, C...
        ax.text(i + 4.5, ymax - y_range * 0.05, f"ZONE {zone_label}", 
                fontsize=9, color='gray', alpha=0.5, ha='center', weight='bold')
        
        # Draw stronger vertical anchor
        ax.axvline(x=i - 0.5, color='gray', linestyle='--', linewidth=0.8, alpha=0.3, zorder=1)
        zone_count += 1

    # Signal Bar Highlight (-1)
    signal_idx = total_bars - 1
    ax.axvspan(signal_idx - 0.5, signal_idx + 0.5, color='yellow', alpha=0.2, zorder=1)

    # Position indices in Z-pattern (alternating high/low) to prevent overlap
    y_pos_low = ymin + y_range * 0.015
    y_pos_high = ymin + y_range * 0.055
    
    for i in range(start_idx, total_bars):
        bar_index = i - total_bars + 1 # 0 = current, -1 = previous
        
        # Alternating position
        y_pos = y_pos_low if abs(bar_index) % 2 == 0 else y_pos_high
        
        # Color: Use a high-contrast dark blue for numbers
        color = '#1a237e' # Dark Blue
        if bar_index == 0: color = '#2e7d32' # Dark Green for current
        if bar_index == -1: color = '#c62828' # Dark Red for signal
        
        ax.annotate(
            str(bar_index),
            xy=(i, y_pos),
            fontsize=8,
            color=color,
            ha='center',
            va='center',
            weight='bold',
            rotation=90, # Rotated 90 degrees as suggested
            bbox=dict(
                boxstyle='round,pad=0.2', 
                facecolor='white', 
                alpha=0.9, 
                edgecolor='#e0e0e0',
                linewidth=0.5
            ),
            zorder=10
        )

def save_brooks_chart(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    chart_type: Literal['primary', 'htf'] = 'primary',
    output_dir: str = 'charts',
    annotate_bars: bool = True,
    show_volume: bool = True,
    num_bars_display: int = 150,
    focus_num_bars: int | None = None,
    swings: list[dict[str, Any]] | None = None
) -> str:
    """
    Generate and save a Brooks-style chart.
    
    Args:
        df: DataFrame with OHLC data
        symbol: Trading symbol
        timeframe: Timeframe string
        chart_type: 'primary' or 'htf'
        output_dir: Directory to save charts
        annotate_bars: Whether to add bar index annotations
        show_volume: Whether to show volume panel
        num_bars_display: Default number of bars to display
        focus_num_bars: If set, crops to only the LAST N bars (e.g., 30) for high-detail
        
    Returns:
        str: Absolute path to saved chart image
    """
    # Ensure output directory exists
    charts_dir = os.path.abspath(output_dir)
    if not os.path.exists(charts_dir):
        os.makedirs(charts_dir)
    
    # Generate filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_symbol = symbol.replace("/", "")
    filename = f"{charts_dir}/{safe_symbol}_{timeframe}_{chart_type}_{timestamp}.png"
    
    # Prepare data (handle Focus mode)
    display_count = focus_num_bars if focus_num_bars else num_bars_display
    plot_df = df.tail(display_count).copy()
    
    # Adjust filename for focus mode
    suffix = f"_focus{focus_num_bars}" if focus_num_bars else ""
    filename = f"{charts_dir}/{safe_symbol}_{timeframe}_{chart_type}{suffix}_{timestamp}.png"
    brooks_style = create_brooks_style()
    
    # Prepare EMA plot
    addplots = []
    if 'ema20' in plot_df.columns:
        addplots.append(
            mpf.make_addplot(
                plot_df['ema20'],
                color='blue',
                width=1.5,
                label='EMA20'
            )
        )
    
    # Create figure
    plot_kwargs = dict(
        type='candle',
        style=brooks_style,
        title=f"{symbol} {timeframe} - Al Brooks Price Action",
        ylabel='Price',
        volume=show_volume,
        figsize=(16, 12), # Increased height for rotated labels
        tight_layout=False, # Manual layout adjustment
        returnfig=True,
        warn_too_much_data=300
    )
    
    if addplots:
        plot_kwargs['addplot'] = addplots

    fig, axes = mpf.plot(plot_df, **plot_kwargs)
    
    # Manual padding adjustment for rotated indices
    fig.subplots_adjust(bottom=0.15, top=0.92, right=0.95, left=0.08)
    
    # Add annotations
    main_ax = axes[0]
    
    # 1. Swing Point labels (S1, S2...) - Target recognition for Measured Moves
    if swings is None:
        # Fallback to local calculation if not provided
        swings = get_swing_points(plot_df, window=5)
    
    # We need to filter global swings to only those visible in plot_df
    # and map them to the correct local x-axis index
    visible_swings = []
    # Get the global indices of the bars in plot_df
    plot_indices = plot_df.index
    
    # Get the start integer index of plot_df relative to df
    # Since plot_df = df.tail(n), its start integer index is len(df) - len(plot_df)
    total_len = len(df)
    plot_len = len(plot_df)
    start_pos = total_len - plot_len
    
    for s_idx, s in enumerate(swings):
        # s['idx'] is the integer position in the original df
        if s['idx'] >= start_pos and s['idx'] < total_len:
            # Calculate local x position (relative to plot_df start)
            local_x = s['idx'] - start_pos
            
            # Create a copy with adjusted local index for annotation
            s_local = s.copy()
            s_local['idx'] = local_x
            s_local['global_s_idx'] = s_idx + 1 # Keep the S1, S2 name stable
            visible_swings.append(s_local)

    annotate_swing_points(main_ax, plot_df, visible_swings)
    
    # 2. Bar index annotations if requested
    if annotate_bars:
        annotate_bar_indices(main_ax, plot_df, num_bars=20)
    
    # Save with high DPI for wick clarity
    fig.savefig(filename, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    
    return filename

def add_pattern_annotations(
    ax: Axes,
    df: pd.DataFrame,
    patterns: list[dict[str, Any]],
    pattern_type: Literal['wedge', 'channel', 'trading_range', 'measured_move']
):
    """
    Add visual annotations for detected Brooks patterns.
    
    Args:
        ax: Matplotlib axis
        df: DataFrame with OHLC data
        patterns: List of pattern dicts with keys: type, start_bar, end_bar, description
        pattern_type: Type of pattern to annotate
        
    Example pattern dict:
        {
            'type': 'wedge',
            'start_bar': -30,
            'end_bar': -1,
            'description': 'Wedge Top (3 pushes up with lower highs)',
            'bars': [-30, -20, -10]  # The 3 push points
        }
    """
    total_bars = len(df)
    
    for pattern in patterns:
        if pattern['type'] != pattern_type:
            continue
        
        start_idx = total_bars + pattern['start_bar']
        end_idx = total_bars + pattern['end_bar']
        
        if pattern_type == 'wedge':
            # Draw lines connecting the 3 push points
            push_bars = pattern.get('bars', [])
            if len(push_bars) >= 3:
                xs = [total_bars + b for b in push_bars]
                ys = [df.iloc[x]['high'] for x in xs]  # For wedge top
                
                ax.plot(xs, ys, color='red', linestyle='--', linewidth=2, alpha=0.7)
                
                # Annotate
                ax.annotate(
                    'WEDGE',
                    xy=(xs[-1], ys[-1]),
                    xytext=(10, 10),
                    textcoords='offset points',
                    fontsize=10,
                    color='red',
                    weight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.5)
                )
        
        elif pattern_type == 'trading_range':
            # Draw horizontal lines at support and resistance
            support = pattern.get('support')
            resistance = pattern.get('resistance')
            
            if support and resistance:
                ax.axhline(y=support, color='green', linestyle='--', linewidth=1.5, alpha=0.7)
                ax.axhline(y=resistance, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
                
                # Label
                ax.text(
                    start_idx + (end_idx - start_idx) / 2,
                    (support + resistance) / 2,
                    'TRADING RANGE',
                    fontsize=11,
                    color='purple',
                    weight='bold',
                    ha='center',
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8)
                )
        
        elif pattern_type == 'measured_move':
            # Draw arrow showing measured move target
            impulse_start = pattern.get('impulse_start_bar')
            impulse_end = pattern.get('impulse_end_bar')
            target_price = pattern.get('target_price')
            
            if impulse_start and impulse_end and target_price:
                start_idx = total_bars + impulse_start
                end_idx = total_bars + impulse_end
                
                # Draw impulse leg
                ax.annotate(
                    '',
                    xy=(end_idx, df.iloc[end_idx]['high']),
                    xytext=(start_idx, df.iloc[start_idx]['low']),
                    arrowprops=dict(
                        arrowstyle='<->',
                        color='orange',
                        linewidth=2
                    )
                )
                
                # Draw target line
                ax.axhline(
                    y=target_price,
                    color='orange',
                    linestyle=':',
                    linewidth=2,
                    alpha=0.7
                )
                
                # Label target
                ax.text(
                    total_bars - 5,
                    target_price,
                    f'MM Target: {target_price:.2f}',
                    fontsize=9,
                    color='orange',
                    weight='bold',
                    va='bottom',
                    ha='right',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8)
                )

# Example usage
if __name__ == "__main__":
    # Test with sample data
    import numpy as np
    
    # Generate sample OHLC data
    dates = pd.date_range('2024-01-01', periods=200, freq='15min')
    np.random.seed(42)
    
    close = 45000 + np.cumsum(np.random.randn(200) * 100)
    high = close + np.abs(np.random.randn(200) * 50)
    low = close - np.abs(np.random.randn(200) * 50)
    open_price = close + np.random.randn(200) * 30
    volume = np.random.randint(1000, 10000, 200)
    
    df = pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)
    
    # Calculate EMA20
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    
    # Generate chart
    chart_path = save_brooks_chart(
        df=df,
        symbol="BTC/USDT",
        timeframe="15m",
        chart_type="primary",
        annotate_bars=True,
        show_volume=True
    )
    
    print(f"Brooks chart saved to: {chart_path}")
