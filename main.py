"""
完整的交易系统主程序 - Supervisor Pattern

使用LangGraph Supervisor架构：
1. 声明式图结构替代while循环
2. 状态持久化（程序崩溃不丢失数据）
3. 清晰的路由逻辑
4. 易于扩展和测试
"""

import os
import time
from datetime import datetime
from langfuse import observe

from src.config import load_config
from src.supervisor_graph import build_trading_supervisor
from src.enhanced_logging import setup_enhanced_logging, get_trade_logger, get_metrics_logger
from src.dashboard import get_dashboard, start_dashboard_server
from src.utils.candle_timer import CandleTimer, ExchangeTimeSynchronizer, parse_timeframe_to_minutes
from src.database.session import init_db
from src.database.persistence_manager import get_persistence_manager
from src.logger import get_logger

logger = get_logger(__name__)


@observe(name="Trading System - Supervisor Pattern")
def main():
    """
    主程序 - 极简Runner
    
    职责：
    1. 加载配置
    2. 初始化基础设施（日志、监控）
    3. 构建Supervisor Graph
    4. 定期"踢"一次图（Tick）
    5. 优雅处理异常
    """
    
    # ========== 1. 加载配置 ==========
    try:
        config = load_config()
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        print("Please check your .env file and try again.")
        return
    
    # 初始化数据库
    init_db()
    
    # ========== 2. 设置基础设施 ==========
    
    # 日志系统
    setup_enhanced_logging(
        log_dir=config.logging.log_dir,
        console_level=config.logging.level,
        file_level="DEBUG",
        structured=config.logging.structured
    )
    
    trade_logger = get_trade_logger()
    metrics_logger = get_metrics_logger()
    
    logger.info("="*70)
    logger.info(" "*20 + "TRADING SYSTEM - SUPERVISOR PATTERN")
    logger.info("="*70)
    logger.info(f"Trading Mode: {config.system.trading_mode}")
    logger.info(f"Exchange: {config.exchange.name} (Sandbox: {config.exchange.sandbox})")
    logger.info(f"Symbol: {os.getenv('TRADING_SYMBOL', 'BTC/USDT')}")
    logger.info(f"Timeframe: {config.timeframe.primary}")
    logger.info(f"Max Leverage: {config.risk.default_leverage}x")
    logger.info(f"Max Daily Loss: {config.risk.max_daily_loss_percent}%")
    logger.info("="*70)
    
    # 生产环境警告
    if config.system.trading_mode == "live" and not config.exchange.sandbox:
        logger.warning("\n" + "!"*70)
        logger.warning(" "*20 + "⚠️  PRODUCTION MODE - REAL MONEY AT RISK ⚠️")
        logger.warning("!"*70 + "\n")
        time.sleep(3)
    
    # 仪表盘
    dashboard = get_dashboard()
    dashboard.update_status("initializing")
    
    if os.getenv("ENABLE_DASHBOARD_SERVER", "false").lower() == "true":
        start_dashboard_server(port=8000)
        logger.info("✓ Dashboard server started at http://localhost:8000")
    
    # 心跳监控已移除 - 依赖 LangGraph persistence 和 OS 级别的进程监控
    
    # K线时间管理器
    import ccxt
    
    # 初始化交易所（用于时间同步）
    exchange = ccxt.bitget({
        'apiKey': os.getenv('BITGET_API_KEY', ''),
        'secret': os.getenv('BITGET_SECRET', ''),
        'password': os.getenv('BITGET_PASSWORD', ''),
        'enableRateLimit': True,
    })
    
    # 创建时间同步器
    time_sync = ExchangeTimeSynchronizer(
        exchange=exchange,
        sync_interval_minutes=60  # 每小时同步一次
    )
    
    # 初始时间同步
    try:
        sync_result = time_sync.sync_time()
        logger.info(
            f"🕐 Initial time sync: offset={sync_result['offset_ms']:.0f}ms, "
            f"latency={sync_result['latency_ms']:.0f}ms"
        )
    except Exception as e:
        logger.warning(f"⚠️  Time sync failed, using local time: {e}")
        time_sync = None  # 降级到本地时间
    
    # 创建K线定时器
    timeframe_minutes = parse_timeframe_to_minutes(config.timeframe.primary)
    candle_timer = CandleTimer(
        timeframe_minutes=timeframe_minutes,
        time_sync=time_sync,
        execution_buffer_ms=500  # 提前500ms唤醒
    )
    
    logger.info(
        f"🕐 Candle timer initialized: {timeframe_minutes}min candles, "
        f"buffer=500ms"
    )
    
    # ========== 3. 构建Supervisor Graph ==========
    
    logger.info("\n🏗️  Building supervisor graph...")
    
    # 创建checkpointer（使用with管理生命周期）
    db_path = os.path.join(config.system.data_dir, "trading_state.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # 使用with语句确保数据库连接在整个程序运行期间保持打开
    from langgraph.checkpoint.sqlite import SqliteSaver
    
    with SqliteSaver.from_conn_string(db_path) as checkpointer:
        logger.info(f"✓ Checkpointer created: {db_path}")
        
        # 构建图（注入checkpointer）
        app = build_trading_supervisor(checkpointer=checkpointer)
        
        logger.info("✓ Supervisor graph ready")
        
        # ========== 4. 配置会话 ==========
        
        symbol = os.getenv("TRADING_SYMBOL", "BTC/USDT")
        
        # thread_id 用于区分不同的交易会话
        # 如果你同时交易多个品种，可以为每个品种创建独立的thread
        thread_id = f"{symbol.replace('/', '_')}_{config.timeframe.primary}"
        
        config_dict = {
            "configurable": {
                "thread_id": thread_id
            }
        }
        
        # 初始状态（仅在首次运行时使用）
        initial_state = {
            "symbol": symbol,
            "exchange": config.exchange.name,
            "timeframe": timeframe_minutes,
            "status": "hunting",
            "account_balance": 10000.0,
            "position": None,
            "loop_count": 0,
            "daily_pnl": 0.0,
            "consecutive_losses": 0,
            "max_daily_loss_pct": config.risk.max_daily_loss_percent,
            "is_trading_enabled": True,
            "breakeven_locked": False,
            "followthrough_checked": False,
            "should_exit": False,
            "messages": [],
            "errors": []
        }
        
        logger.info(f"✓ Session configured: {thread_id}")
        logger.info("\n" + "="*70)
        logger.info(" "*25 + "🚀 SYSTEM LAUNCHED")
        logger.info("="*70 + "\n")
        
        # ========== 5. 主循环：定期Tick图 ==========
        
        tick_count = 0
        
        try:
            while True:
                # === 等待下一个K线收盘 ===
                if tick_count > 0:  # 跳过第一次（启动时立即执行）
                    timing_info = candle_timer.wait_until_next_candle()
                    logger.info(
                        f"🕐 Candle close: {timing_info['next_close'].strftime('%H:%M:%S')}, "
                        f"Latency: {timing_info['latency_ms']:.0f}ms"
                    )
                
                tick_count += 1
                
                logger.info(f"\n{'─'*70}")
                logger.info(f"⚡ Tick #{tick_count} @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"{'─'*70}")
                
                # --- 执行一次图运行 ---
                # LangGraph会自动从DB加载上次状态并合并新输入
                
                try:
                    start_time = time.time()
                    
                    # --- 1. 创建 Persistence Run ---
                    run_id = None
                    try:
                        with get_persistence_manager() as pm:
                            run = pm.create_run(
                                thread_id=thread_id,
                                symbol=symbol,
                                timeframe=config.timeframe.primary,
                                status="hunting" # Default, nodes will update it
                            )
                            run_id = run.id
                            logger.info(f"💾 Created Persistence Run: {run_id}")
                    except Exception as e:
                        logger.warning(f"⚠️  Failed to create persistence run: {e}")

                    # --- 2. 执行一次图运行 ---
                    # 传入空dict让图从DB恢复，或传入initial_state（首次）
                    tick_input = {"run_id": run_id}
                    if tick_count == 1:
                        tick_input = {**initial_state, "run_id": run_id}

                    result = app.invoke(
                        tick_input,
                        config=config_dict
                    )
                    
                    duration_ms = (time.time() - start_time) * 1000
                    metrics_logger.log_execution_time("supervisor_tick", duration_ms)
                    
                    # --- 提取结果 ---
                    current_status = result.get("status", "unknown")
                    has_position = result.get("position") is not None
                    has_order = result.get("pending_order_id") is not None
                    
                    logger.info(f"Status: {current_status}")
                    logger.info(f"Position: {'Yes' if has_position else 'No'}")
                    logger.info(f"Order: {'Yes' if has_order else 'No'}")
                    logger.info(f"Duration: {duration_ms:.1f}ms")
                    
                    # 更新仪表盘
                    dashboard.update_status(current_status)
                    dashboard.update_position(result.get("position"))
                    dashboard.record_execution_time("tick", duration_ms)
                    
                    # Check errors
                    errors = result.get("errors", [])
                    if errors:
                        logger.warning(f"⚠️  Errors in this tick: {len(errors)}")
                        for err in errors[-3:]:  # Only last 3
                            logger.warning(f"  - {err}")
                            dashboard.record_error(err)
                    
                    # Check warnings from nodes (e.g., execution visibility failures)
                    warnings = result.get("warnings", [])
                    if warnings:
                        logger.warning(f"⚠️  Warnings in this tick: {len(warnings)}")
                        for warn in warnings:
                            logger.warning(f"  - {warn}")
                    
                    # --- K线对齐模式 ---
                    # 所有状态都在K线收盘时执行（由candle_timer控制）
                    # 冷却模式可以跳过若干K线
                    
                    if current_status == "cooldown":
                        mode_emoji = "❄️"
                        mode_name = "COOLDOWN"
                        # TODO: 可以实现跳过N个K线的逻辑
                    elif has_position or has_order:
                        mode_emoji = "📊"
                        mode_name = "MANAGING"
                    else:
                        mode_emoji = "🔍"
                        mode_name = "HUNTING"
                    
                    logger.info(f"\n{mode_emoji} [{mode_name}] Tick complete.")
                    
                    # 定期保存仪表盘快照
                    if tick_count % 10 == 0:
                        dashboard.save_snapshot()
                    
                    # 定期打印仪表盘（可选）
                    if tick_count % 20 == 0:
                        dashboard.print_dashboard()
                    
                except Exception as e:
                    logger.exception(f"❌ Tick failed: {e}")
                    # logger.error(f"❌ Tick failed: {e}", exc_info=True)
                    dashboard.record_error(str(e))
                    
                    # 出错后短暂休眠然后重试
                    time.sleep(10)
        
        except KeyboardInterrupt:
            logger.info("\n\n" + "="*70)
            logger.info(" "*25 + "🛑 STOPPED BY USER")
            logger.info("="*70)
        
        except Exception as e:
            logger.error(f"\n💥 CRITICAL ERROR: {e}", exc_info=True)
            dashboard.record_error(f"Critical: {str(e)}")
        
        finally:
            # ========== 6. 清理 ==========
            
            logger.info("\n" + "="*70)
            logger.info(" "*25 + "SHUTTING DOWN...")
            logger.info("="*70)
            
            logger.info(f"\nTotal Ticks: {tick_count}")
            logger.info("State saved to DB. Next run will resume from here.")
            logger.info("\n✅ SHUTDOWN COMPLETE\n")


if __name__ == "__main__":
    main()
