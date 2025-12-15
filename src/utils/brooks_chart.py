"""
Brooks-Style Chart Renderer
Generates clean, high-clarity charts matching Al Brooks' minimalist style.
"""

import os
import datetime
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from matplotlib import ticker
from typing import Optional, Literal

def create_brooks_style():
    """Create custom mplfinance style for Al Brooks charts"""
    marketcolors = mpf.make_marketcolors(
        up='white',
        down='black',
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

def annotate_bar_indices(
    ax,
    df: pd.DataFrame,
    num_bars: int = 20,
    offset: float = 0.3
):
    """
    Add bar index annotations to chart.
    
    Args:
        ax: Matplotlib axis
        df: DataFrame with OHLC data
        num_bars: Number of recent bars to annotate
        offset: Vertical offset multiplier for annotation position
    """
    # Get the last N bars
    total_bars = len(df)
    start_idx = max(0, total_bars - num_bars)
    
    for i in range(start_idx, total_bars):
        bar_index = i - total_bars  # Convert to negative index (0 = current)
        
        # Position annotation slightly above the high of the bar
        x_pos = i
        y_pos = df.iloc[i]['high'] * (1 + offset / 100)
        
        # Color: red for negative indices, green for current bar
        color = 'red' if bar_index < 0 else 'green'
        fontsize = 7 if bar_index < -10 else 8  # Smaller font for older bars
        
        ax.annotate(
            str(bar_index),
            xy=(x_pos, y_pos),
            fontsize=fontsize,
            color=color,
            ha='center',
            va='bottom',
            weight='bold'
        )

def save_brooks_chart(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    chart_type: Literal['primary', 'htf'] = 'primary',
    output_dir: str = 'charts',
    annotate_bars: bool = True,
    show_volume: bool = True,
    num_bars_display: int = 150
) -> str:
    """
    Generate and save a Brooks-style chart.
    
    Args:
        df: DataFrame with OHLC data (must have 'open', 'high', 'low', 'close', 'volume', 'ema20' columns)
        symbol: Trading symbol (e.g., "BTC/USDT")
        timeframe: Timeframe string (e.g., "15m", "1h")
        chart_type: 'primary' or 'htf' (for filename differentiation)
        output_dir: Directory to save charts
        annotate_bars: Whether to add bar index annotations
        show_volume: Whether to show volume panel
        num_bars_display: Number of bars to display on chart
        
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
    
    # Prepare data (last N bars)
    plot_df = df.tail(num_bars_display).copy()
    
    # Create Brooks style
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
    fig, axes = mpf.plot(
        plot_df,
        type='candle',
        style=brooks_style,
        title=f"{symbol} {timeframe} - Al Brooks Price Action",
        ylabel='Price',
        volume=show_volume,
        addplot=addplots if addplots else None,
        figsize=(16, 10),
        tight_layout=True,
        returnfig=True,
        warn_too_much_data=200  # Suppress warning for moderate data
    )
    
    # Add bar index annotations if requested
    if annotate_bars:
        main_ax = axes[0]  # Main price axis
        annotate_bar_indices(main_ax, plot_df, num_bars=20)
    
    # Save with high DPI for wick clarity
    fig.savefig(filename, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    
    return filename

def add_pattern_annotations(
    ax,
    df: pd.DataFrame,
    patterns: list,
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
