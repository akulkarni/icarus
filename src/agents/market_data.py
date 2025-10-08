"""
Market Data Agent

Streams real-time price data from Binance WebSocket.
Publishes MarketTickEvent for each price update.
"""
import asyncio
import logging
from decimal import Decimal
from binance import AsyncClient, BinanceSocketManager
from src.agents.base import BaseAgent
from src.models.events import MarketTickEvent
from src.core.database import get_db_manager_sync
from src.core.config import get_config

logger = logging.getLogger(__name__)


class MarketDataAgent(BaseAgent):
    """
    Streams live market data from Binance.

    Publishes:
    - MarketTickEvent: Real-time price updates
    """

    def __init__(self, event_bus, symbols: list[str], config=None):
        super().__init__("market_data", event_bus)
        self.symbols = symbols  # e.g., ['BTCUSDT', 'ETHUSDT']
        self.client = None
        self.bm = None
        self.config = config or get_config().all

    async def start(self):
        """Start streaming market data"""
        self.logger.info(f"Starting market data for {self.symbols}")

        # Get market data config
        provider = self.config.get('market_data', {}).get('provider', 'binance.us')
        api_key = self.config.get('market_data', {}).get('api_key')
        api_secret = self.config.get('market_data', {}).get('api_secret')

        # Initialize Binance client with US endpoint if configured
        if provider == 'binance.us':
            self.logger.info("Using Binance.US API")
            self.client = await AsyncClient.create(
                api_key=api_key or None,
                api_secret=api_secret or None,
                tld='us'  # Use binance.us domain
            )
        else:
            self.logger.info("Using Binance.com API")
            self.client = await AsyncClient.create(
                api_key=api_key or None,
                api_secret=api_secret or None
            )

        self.bm = BinanceSocketManager(self.client)

        # Create tasks for each symbol
        tasks = [self._stream_symbol(symbol) for symbol in self.symbols]

        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            self.logger.error(f"Error in market data stream: {e}")
        finally:
            await self.stop()

    async def _stream_symbol(self, symbol: str):
        """Stream ticker data for a symbol"""
        self.logger.info(f"Starting stream for {symbol}")

        # Use ticker stream for real-time price updates
        ts = self.bm.symbol_ticker_socket(symbol)

        async with ts as tscm:
            while self._running:
                try:
                    msg = await tscm.recv()

                    if msg:
                        # Parse Binance ticker message
                        event = MarketTickEvent(
                            symbol=symbol,
                            price=Decimal(str(msg['c'])),  # Last price
                            volume=Decimal(str(msg['v']))  # 24h volume
                        )

                        # Publish to event bus
                        await self.publish(event)

                        # Also persist to database
                        await self._persist_tick(event)

                except Exception as e:
                    self.logger.error(f"Error processing tick for {symbol}: {e}")
                    await asyncio.sleep(1)  # Brief pause before retrying

    async def _persist_tick(self, event: MarketTickEvent):
        """Save tick to database"""
        db = get_db_manager_sync()

        try:
            conn = await db.get_connection()
            try:
                await conn.execute("""
                    INSERT INTO market_data (time, symbol, price, volume)
                    VALUES (NOW(), $1, $2, $3)
                """, event.symbol, event.price, event.volume)
            finally:
                await db.release_connection(conn)
        except Exception as e:
            self.logger.error(f"Failed to persist tick: {e}")

    async def stop(self):
        """Cleanup"""
        await super().stop()
        if self.client:
            await self.client.close_connection()
        self.logger.info("Market data agent stopped")
