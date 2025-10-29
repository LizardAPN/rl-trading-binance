#!/usr/bin/env python3
"""
Live trading script for Bybit integration
"""
import argparse
import asyncio
import logging
import os
import sys
from typing import List
import importlib.util

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bybit_trading.engine import BybitTradingEngine
from bybit_trading.config import TradingMode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("live_trading.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def load_config(config_path: str):
    """
    Load configuration from a Python file
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Loaded configuration object
    """
    try:
        spec = importlib.util.spec_from_file_location("config", config_path)
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)
        return config_module.cfg
    except Exception as e:
        logger.error(f"Error loading config from {config_path}: {str(e)}")
        raise

def parse_arguments():
    """
    Parse command line arguments
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Bybit Live Trading Script")
    
    parser.add_argument(
        "config",
        help="Path to configuration file"
    )
    
    parser.add_argument(
        "--mode",
        choices=[TradingMode.DEMO, TradingMode.PAPER, TradingMode.LIVE],
        default=TradingMode.DEMO,
        help="Trading mode (demo, paper, live)"
    )
    
    parser.add_argument(
        "--symbols",
        help="Comma-separated list of trading symbols (overrides config)"
    )
    
    return parser.parse_args()

async def main():
    """
    Main entry point for the live trading script
    """
    # Parse command line arguments
    args = parse_arguments()
    
    # Load configuration
    try:
        cfg = load_config(args.config)
    except Exception as e:
        logger.error(f"Failed to load configuration: {str(e)}")
        return 1
    
    # Determine trading symbols
    if args.symbols:
        symbols = args.symbols.split(",")
        symbols = [s.strip() for s in symbols if s.strip()]
    else:
        symbols = getattr(cfg.live_trading, "symbols", ["BTCUSDT"])
    
    if not symbols:
        logger.error("No trading symbols specified")
        return 1
    
    # Get trading mode
    mode = args.mode
    
    # Prepare configuration for trading engine
    engine_config = {
        "check_interval": getattr(cfg.live_trading, "check_interval", 60),
        "max_position_pct": getattr(cfg.live_trading, "max_position_pct", 0.1),
        "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", "")
    }
    
    # Override with config values if available
    if hasattr(cfg.live_trading, "telegram_alerts") and cfg.live_trading.telegram_alerts:
        engine_config["telegram_bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN", "")
        engine_config["telegram_chat_id"] = os.getenv("TELEGRAM_CHAT_ID", "")
    
    logger.info(f"Starting live trading in {mode} mode")
    logger.info(f"Trading symbols: {symbols}")
    
    # Create and start trading engine
    engine = BybitTradingEngine(
        mode=mode,
        symbols=symbols,
        config=engine_config
    )
    
    try:
        # Start the trading engine
        success = await engine.start()
        if not success:
            logger.error("Failed to start trading engine")
            return 1
            
        # Keep running until interrupted
        while engine.running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return 1
    finally:
        # Stop the engine
        engine.stop()
    
    logger.info("Live trading stopped")
    return 0

if __name__ == "__main__":
    # Run the async main function
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
