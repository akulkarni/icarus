"""
Icarus Trading System - Main Entry Point

Orchestrates all agents and manages system lifecycle.
"""
import asyncio
import logging
import signal
import sys
from decimal import Decimal

from src.core.config import load_config
from src.core.event_bus import get_event_bus_sync, close_event_bus
from src.core.database import get_db_manager_sync, close_db_manager

from src.agents.market_data import MarketDataAgent
from src.agents.strategy import StrategyAgent
from src.agents.strategies.momentum import MomentumStrategy
from src.agents.strategies.macd import MACDStrategy
from src.agents.execution import TradeExecutionAgent
from src.agents.meta_strategy import MetaStrategyAgent
from src.agents.fork_manager import ForkManagerAgent
from src.agents.risk_monitor import RiskMonitorAgent

logger = logging.getLogger(__name__)


class IcarusSystem:
    """Main system orchestrator"""

    def __init__(self):
        self.config = None
        self.event_bus = None
        self.db_manager = None
        self.agents = []
        self._shutdown_event = asyncio.Event()

    async def initialize(self):
        """Initialize system components"""
        logger.info("=" * 80)
        logger.info("ICARUS TRADING SYSTEM - INITIALIZING")
        logger.info("=" * 80)

        # Load configuration (if not already loaded)
        if self.config is None:
            logger.info("Loading configuration...")
            self.config = load_config()
            logger.info("Configuration loaded")

        # Initialize database
        logger.info("Initializing database connection...")
        self.db_manager = get_db_manager_sync()
        await self.db_manager.initialize()

        # Test database connection
        is_healthy = await self.db_manager.health_check()
        if not is_healthy:
            raise RuntimeError("Database health check failed")
        logger.info("Database connection established and healthy")

        # Create event bus
        logger.info("Creating event bus...")
        self.event_bus = get_event_bus_sync()
        logger.info("Event bus created")

        # Create agents
        logger.info("Creating agents...")
        await self._create_agents()
        logger.info(f"Created {len(self.agents)} agents")

    async def _create_agents(self):
        """Create all agent instances"""
        config = self.config.all

        # 1. Market Data Agent
        symbols = config['trading']['symbols']
        market_data_agent = MarketDataAgent(self.event_bus, symbols, config=config)
        self.agents.append(market_data_agent)
        logger.info(f"  - MarketDataAgent created for symbols: {symbols}")

        # 2. Strategy Agents
        strategy_names = []  # Collect strategy names

        # Momentum Strategy
        if config['strategies']['momentum']['enabled']:
            momentum_strategy = MomentumStrategy(
                self.event_bus,
                symbol=config['strategies']['momentum']['symbol'],
                ma_short=config['strategies']['momentum']['ma_short'],
                ma_long=config['strategies']['momentum']['ma_long'],
                warmup_period=config['strategies']['momentum']['warmup_period']
            )
            self.agents.append(momentum_strategy)
            strategy_names.append('momentum')  # Add name to list
            logger.info("  - MomentumStrategy created")

        # MACD Strategy
        if config['strategies']['macd']['enabled']:
            macd_strategy = MACDStrategy(
                self.event_bus,
                symbol=config['strategies']['macd']['symbol'],
                fast_period=config['strategies']['macd']['fast_period'],
                slow_period=config['strategies']['macd']['slow_period'],
                signal_period=config['strategies']['macd']['signal_period'],
                warmup_period=config['strategies']['macd']['warmup_period']
            )
            self.agents.append(macd_strategy)
            strategy_names.append('macd')  # Add name to list
            logger.info("  - MACDStrategy created")

        # 3. Execution Agent
        initial_capital = Decimal(str(config['trading']['initial_capital']))
        execution_agent = TradeExecutionAgent(
            self.event_bus,
            initial_capital=initial_capital,
            config=config
        )
        self.agents.append(execution_agent)
        logger.info(f"  - TradeExecutionAgent created (capital: ${initial_capital})")

        # 4. Meta-Strategy Agent
        meta_strategy_agent = MetaStrategyAgent(
            self.event_bus,
            strategies=strategy_names,  # Pass string list, not agent objects
            evaluation_interval_hours=config['meta_strategy']['evaluation_interval_hours']
        )
        self.agents.append(meta_strategy_agent)
        logger.info("  - MetaStrategyAgent created")

        # 5. Fork Manager Agent
        parent_service_id = config['tiger']['service_id']
        max_concurrent_forks = config['tiger']['max_concurrent_forks']
        fork_manager_agent = ForkManagerAgent(
            self.event_bus,
            parent_service_id=parent_service_id,
            max_concurrent_forks=max_concurrent_forks
        )
        self.agents.append(fork_manager_agent)
        logger.info(f"  - ForkManagerAgent created (parent service: {parent_service_id})")

        # 6. Risk Monitor Agent
        risk_config = config['risk']
        risk_monitor_agent = RiskMonitorAgent(
            self.event_bus,
            config=risk_config,  # Pass entire config dict
            initial_portfolio_value=initial_capital  # Use correct parameter name
        )
        self.agents.append(risk_monitor_agent)
        logger.info("  - RiskMonitorAgent created")

    async def start(self):
        """Start all agents"""
        logger.info("=" * 80)
        logger.info("STARTING ALL AGENTS")
        logger.info("=" * 80)

        # Start all agents concurrently
        tasks = []
        for agent in self.agents:
            logger.info(f"Starting agent: {agent.name}")
            tasks.append(asyncio.create_task(agent.run()))

        # Wait for shutdown signal
        await self._shutdown_event.wait()

        # Cancel all agent tasks
        logger.info("Stopping all agents...")
        for task in tasks:
            task.cancel()

        # Wait for all tasks to complete cancellation
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("All agents stopped")

    async def shutdown(self):
        """Shutdown system gracefully"""
        logger.info("=" * 80)
        logger.info("SHUTTING DOWN ICARUS SYSTEM")
        logger.info("=" * 80)

        # Stop all agents
        logger.info("Stopping agents...")
        for agent in self.agents:
            try:
                await agent.stop()
                logger.info(f"  - {agent.name} stopped")
            except Exception as e:
                logger.error(f"  - Error stopping {agent.name}: {e}")

        # Close event bus
        logger.info("Closing event bus...")
        await close_event_bus()

        # Close database connections
        logger.info("Closing database connections...")
        await close_db_manager()

        logger.info("=" * 80)
        logger.info("ICARUS SYSTEM SHUTDOWN COMPLETE")
        logger.info("=" * 80)

    def request_shutdown(self):
        """Request system shutdown"""
        logger.info("Shutdown requested")
        self._shutdown_event.set()


async def main():
    """Main entry point"""
    # Load configuration first
    from src.core.config import load_config
    from src.core.logging_setup import setup_logging

    config = load_config()
    setup_logging(config)

    system = IcarusSystem()
    system.config = config  # Pass config loaded in main()

    # Setup signal handlers
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        system.request_shutdown()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Initialize system
        await system.initialize()

        # Start system
        await system.start()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Cleanup
        await system.shutdown()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
