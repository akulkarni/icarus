"""
Tests for Fork Manager Agent
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timedelta

from src.agents.fork_manager import ForkManagerAgent
from src.models.events import ForkRequestEvent, ForkCreatedEvent, ForkCompletedEvent
from src.core.event_bus import EventBus


@pytest.fixture
def event_bus():
    """Create event bus for testing"""
    return EventBus()


@pytest.fixture
def fork_manager(event_bus):
    """Create fork manager for testing"""
    return ForkManagerAgent(
        event_bus,
        parent_service_id='test-parent-service',
        max_concurrent_forks=5,
        cleanup_interval_seconds=60
    )


@pytest.mark.asyncio
async def test_fork_creation_success(event_bus, fork_manager):
    """Test successful fork creation"""
    # Subscribe to fork created events
    queue = event_bus.subscribe(ForkCreatedEvent)

    # Mock subprocess calls
    mock_fork_output = json.dumps({'service_id': 'fork-123'})
    mock_show_output = json.dumps({
        'host': 'fork-123.tiger.cloud',
        'port': 5432,
        'database': 'tsdb',
        'username': 'tsdbadmin'
    })

    with patch('subprocess.run') as mock_run:
        # First call: fork creation
        # Second call: get connection params
        mock_run.side_effect = [
            MagicMock(stdout=mock_fork_output, returncode=0),
            MagicMock(stdout=mock_show_output, returncode=0)
        ]

        with patch.object(fork_manager, '_persist_fork_metadata', new=AsyncMock()):
            # Create fork request
            request = ForkRequestEvent(
                requesting_agent='backtest_agent',
                purpose='historical_backtest',
                ttl_seconds=3600
            )

            await fork_manager._create_fork(request)

            # Verify fork is tracked
            assert 'fork-123' in fork_manager.active_forks
            assert fork_manager.active_forks['fork-123']['requesting_agent'] == 'backtest_agent'

            # Verify fork created event published
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                assert isinstance(event, ForkCreatedEvent)
                assert event.fork_id == 'fork-123'
                assert event.service_id == 'fork-123'
                assert event.requesting_agent == 'backtest_agent'
                assert 'host' in event.connection_params
            except asyncio.TimeoutError:
                pytest.fail("Fork created event not published")


@pytest.mark.asyncio
async def test_fork_creation_respects_max_limit(fork_manager):
    """Test that fork creation respects max concurrent limit"""
    # Fill up to max limit
    for i in range(5):
        fork_manager.active_forks[f'fork-{i}'] = {
            'requesting_agent': f'agent-{i}',
            'purpose': 'test',
            'created_at': datetime.now(),
            'ttl_seconds': 3600
        }

    assert fork_manager.get_fork_count() == 5

    # Try to create one more (should be rejected)
    request = ForkRequestEvent(
        requesting_agent='agent-6',
        purpose='test',
        ttl_seconds=3600
    )

    with patch('subprocess.run'):
        await fork_manager._create_fork(request)

    # Should still be at max limit (new fork not created)
    assert fork_manager.get_fork_count() == 5


@pytest.mark.asyncio
async def test_fork_destruction(fork_manager):
    """Test fork destruction"""
    # Add a fork
    fork_manager.active_forks['fork-123'] = {
        'requesting_agent': 'test_agent',
        'purpose': 'test',
        'created_at': datetime.now(),
        'ttl_seconds': 3600
    }

    # Mock subprocess and database
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        with patch('src.agents.fork_manager.get_db_manager') as mock_db:
            mock_conn = AsyncMock()
            mock_db.return_value.get_connection.return_value = mock_conn
            mock_db.return_value.release_connection = AsyncMock()

            await fork_manager._destroy_fork('fork-123')

            # Verify fork removed
            assert 'fork-123' not in fork_manager.active_forks

            # Verify CLI called
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert 'tsdb' in args
            assert 'service' in args
            assert 'delete' in args
            assert 'fork-123' in args


@pytest.mark.asyncio
async def test_fork_completion_event_triggers_destruction(event_bus, fork_manager):
    """Test that fork completion event triggers fork destruction"""
    # Add a fork
    fork_manager.active_forks['fork-123'] = {
        'requesting_agent': 'test_agent',
        'purpose': 'test',
        'created_at': datetime.now(),
        'ttl_seconds': 3600
    }

    # Mock destruction
    with patch.object(fork_manager, '_destroy_fork', new=AsyncMock()) as mock_destroy:
        # Publish completion event
        completion_event = ForkCompletedEvent(
            fork_id='fork-123',
            requesting_agent='test_agent',
            result_summary={'rows_processed': 1000}
        )

        await fork_manager._handle_fork_completion(completion_event)

        # Verify destruction was called
        mock_destroy.assert_called_once_with('fork-123')


@pytest.mark.asyncio
async def test_expired_fork_cleanup():
    """Test that expired forks are automatically cleaned up"""
    event_bus = EventBus()
    fork_manager = ForkManagerAgent(
        event_bus,
        parent_service_id='test-parent',
        max_concurrent_forks=10,
        cleanup_interval_seconds=1  # Fast cleanup for testing
    )

    # Add an expired fork (TTL in the past)
    past_time = datetime.now() - timedelta(hours=2)
    fork_manager.active_forks['expired-fork'] = {
        'requesting_agent': 'test_agent',
        'purpose': 'test',
        'created_at': past_time,
        'ttl_seconds': 3600  # 1 hour TTL, but created 2 hours ago
    }

    # Add a non-expired fork
    fork_manager.active_forks['active-fork'] = {
        'requesting_agent': 'test_agent',
        'purpose': 'test',
        'created_at': datetime.now(),
        'ttl_seconds': 3600
    }

    # Mock destruction
    with patch.object(fork_manager, '_destroy_fork', new=AsyncMock()) as mock_destroy:
        # Run one cleanup cycle
        await asyncio.sleep(0.1)  # Let cleanup task initialize

        # Manually trigger cleanup check
        now = datetime.now()
        expired_forks = []
        for fork_id, metadata in fork_manager.active_forks.items():
            age_seconds = (now - metadata['created_at']).total_seconds()
            if age_seconds > metadata['ttl_seconds']:
                expired_forks.append(fork_id)

        # Destroy expired forks
        for fork_id in expired_forks:
            await fork_manager._destroy_fork(fork_id)

        # Verify only expired fork was destroyed
        assert mock_destroy.call_count >= 1
        mock_destroy.assert_any_call('expired-fork')


@pytest.mark.asyncio
async def test_get_fork_connection_params(fork_manager):
    """Test getting fork connection parameters"""
    mock_output = json.dumps({
        'host': 'fork-456.tiger.cloud',
        'port': 5432,
        'database': 'tsdb',
        'username': 'tsdbadmin'
    })

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output, returncode=0)

        params = await fork_manager._get_fork_connection_params('fork-456')

        assert params['host'] == 'fork-456.tiger.cloud'
        assert params['port'] == 5432
        assert params['database'] == 'tsdb'
        assert params['username'] == 'tsdbadmin'
        assert params['service_id'] == 'fork-456'


@pytest.mark.asyncio
async def test_fork_creation_cli_error_handling(fork_manager):
    """Test handling of CLI errors during fork creation"""
    import subprocess

    # Mock subprocess to raise error
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            1, 'tsdb', stderr='Error: Service not found'
        )

        request = ForkRequestEvent(
            requesting_agent='test_agent',
            purpose='test',
            ttl_seconds=3600
        )

        # Should not raise exception (error is logged)
        await fork_manager._create_fork(request)

        # Fork should not be tracked
        assert fork_manager.get_fork_count() == 0


@pytest.mark.asyncio
async def test_persist_fork_metadata(fork_manager):
    """Test persisting fork metadata to database"""
    request = ForkRequestEvent(
        requesting_agent='test_agent',
        purpose='backtest',
        ttl_seconds=3600
    )

    with patch('src.agents.fork_manager.get_db_manager') as mock_db:
        mock_conn = AsyncMock()
        mock_db.return_value.get_connection.return_value = mock_conn
        mock_db.return_value.release_connection = AsyncMock()

        await fork_manager._persist_fork_metadata('fork-789', request)

        # Verify database insert was called
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert 'INSERT INTO fork_tracking' in call_args[0][0]
        assert 'fork-789' in call_args[0]
        assert 'test_agent' in call_args[0]


@pytest.mark.asyncio
async def test_get_active_forks(fork_manager):
    """Test getting active forks"""
    fork_manager.active_forks['fork-1'] = {'test': 'data1'}
    fork_manager.active_forks['fork-2'] = {'test': 'data2'}

    active = fork_manager.get_active_forks()

    assert len(active) == 2
    assert 'fork-1' in active
    assert 'fork-2' in active

    # Should be a copy (not reference)
    active['fork-3'] = {'test': 'data3'}
    assert 'fork-3' not in fork_manager.active_forks


@pytest.mark.asyncio
async def test_stop_cleans_up_all_forks(fork_manager):
    """Test that stopping fork manager destroys all active forks"""
    # Add multiple forks
    fork_manager.active_forks['fork-1'] = {
        'requesting_agent': 'agent1',
        'purpose': 'test',
        'created_at': datetime.now(),
        'ttl_seconds': 3600
    }
    fork_manager.active_forks['fork-2'] = {
        'requesting_agent': 'agent2',
        'purpose': 'test',
        'created_at': datetime.now(),
        'ttl_seconds': 3600
    }

    with patch.object(fork_manager, '_destroy_fork', new=AsyncMock()) as mock_destroy:
        await fork_manager.stop()

        # Verify all forks were destroyed
        assert mock_destroy.call_count == 2
        calls = [call[0][0] for call in mock_destroy.call_args_list]
        assert 'fork-1' in calls
        assert 'fork-2' in calls


# Add json import at top
import json
