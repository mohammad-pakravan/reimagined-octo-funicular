"""
Tests for referral system with event integration.
Tests that events (points_multiplier and referral_reward) correctly affect referral coin rewards.
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from core.points_manager import PointsManager
from core.event_engine import EventEngine
from db.models import Event, CoinRewardSetting
from db.crud import (
    get_coins_for_activity,
    get_active_events,
    get_user_points,
    get_points_history,
)


class TestReferralEvents:
    """Test referral system with event integration."""
    
    @pytest.mark.asyncio
    async def test_referral_profile_complete_without_events(self):
        """Test referral profile completion without any active events."""
        # Mock database session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Mock get_coins_for_activity
        async def mock_get_coins(session, activity_type: str):
            if activity_type == "referral_profile_complete":
                return 200  # 200 coins for referrer
            elif activity_type == "referral_referred_signup":
                return 100  # 100 coins for referred user
            return None
        
        # Mock get_coin_reward_setting
        async def mock_get_coin_reward_setting(session, activity_type: str):
            mock_setting = MagicMock()
            if activity_type == "referral_profile_complete":
                mock_setting.is_active = True
                mock_setting.coins_amount = 200
                return mock_setting
            elif activity_type == "referral_referred_signup":
                mock_setting.is_active = True
                mock_setting.coins_amount = 100
                return mock_setting
            return None
        
        # Mock get_active_events
        async def mock_get_active_events(session, event_type=None):
            return []
        
        with patch('core.points_manager.get_db') as mock_get_db, \
             patch('db.crud.get_coin_reward_setting', side_effect=mock_get_coin_reward_setting), \
             patch('core.event_engine.get_db') as mock_event_db, \
             patch('core.event_engine.get_active_events', side_effect=mock_get_active_events) as mock_get_events, \
             patch('core.event_engine.EventEngine.handle_referral_reward', return_value=False), \
             patch('core.points_manager.add_points', return_value=True), \
             patch('core.event_engine.EventEngine.track_challenge_progress', return_value=[]):
            
            mock_get_db.return_value.__aiter__.return_value = [mock_session]
            mock_event_db.return_value.__aiter__.return_value = [mock_session]
            
            # Test award_referral_profile_complete
            result = await PointsManager.award_referral_profile_complete(
                referrer_id=1,
                referred_id=2
            )
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_referral_profile_complete_with_points_multiplier_all_sources(self):
        """Test referral profile completion with points_multiplier event for all sources."""
        # Mock database session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Create mock event with multiplier 2.0 for all sources (empty apply_to_sources)
        mock_event = MagicMock(spec=Event)
        mock_event.id = 1
        mock_event.event_type = "points_multiplier"
        mock_event.config_json = json.dumps({"multiplier": 2.0})
        
        # Mock get_coin_reward_setting
        async def mock_get_coin_reward_setting(session, activity_type: str):
            mock_setting = MagicMock()
            if activity_type == "referral_profile_complete":
                mock_setting.is_active = True
                mock_setting.coins_amount = 200
                return mock_setting
            elif activity_type == "referral_referred_signup":
                mock_setting.is_active = True
                mock_setting.coins_amount = 100
                return mock_setting
            return None
        
        # Mock get_active_events
        async def mock_get_active_events(session, event_type=None):
            if event_type == "points_multiplier":
                return [mock_event]
            return []
        
        with patch('core.points_manager.get_db') as mock_get_db, \
             patch('db.crud.get_coin_reward_setting', side_effect=mock_get_coin_reward_setting), \
             patch('core.event_engine.get_db') as mock_event_db, \
             patch('core.event_engine.get_active_events', side_effect=mock_get_active_events) as mock_get_events, \
             patch('core.event_engine.EventEngine.handle_referral_reward', return_value=False), \
             patch('core.points_manager.add_points') as mock_add_points, \
             patch('db.crud.get_or_create_event_participant', return_value=MagicMock()), \
             patch('core.event_engine.EventEngine.track_challenge_progress', return_value=[]):
            
            mock_get_db.return_value.__aiter__.return_value = [mock_session]
            mock_event_db.return_value.__aiter__.return_value = [mock_session]
            
            # Test award_referral_profile_complete
            result = await PointsManager.award_referral_profile_complete(
                referrer_id=1,
                referred_id=2
            )
            
            assert result is True
            
            # Verify that add_points was called with multiplied coins
            # Referrer should get 200 * 2 = 400 coins
            # Referred should get 100 * 2 = 200 coins
            calls = mock_add_points.call_args_list
            assert len(calls) == 2
            
            # Check referrer points (first call)
            # add_points signature: (session, user_id, points, type, source, description, related_user_id)
            referrer_call = calls[0]
            assert referrer_call[0][1] == 1  # referrer_id (second arg)
            assert referrer_call[0][2] == 400  # 200 * 2 = 400 coins (third arg)
            assert referrer_call[0][4] == "referral_profile_complete"  # source (fifth arg)
            
            # Check referred user points (second call)
            # add_points signature: (session, user_id, points, type, source, description, related_user_id)
            referred_call = calls[1]
            assert referred_call[0][1] == 2  # referred_id (second arg)
            assert referred_call[0][2] == 200  # 100 * 2 = 200 coins (third arg)
            assert referred_call[0][4] == "referral_profile_complete"  # source (fifth arg)
    
    @pytest.mark.asyncio
    async def test_referral_profile_complete_with_points_multiplier_specific_source(self):
        """Test referral profile completion with points_multiplier event for specific source."""
        # Mock database session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Create mock event with multiplier 2.0 only for referral_profile_complete
        mock_event = MagicMock(spec=Event)
        mock_event.id = 1
        mock_event.event_type = "points_multiplier"
        mock_event.config_json = json.dumps({
            "multiplier": 2.0,
            "apply_to_sources": ["referral_profile_complete"]
        })
        
        # Mock get_coin_reward_setting
        async def mock_get_coin_reward_setting(session, activity_type: str):
            mock_setting = MagicMock()
            if activity_type == "referral_profile_complete":
                mock_setting.is_active = True
                mock_setting.coins_amount = 200
                return mock_setting
            elif activity_type == "referral_referred_signup":
                mock_setting.is_active = True
                mock_setting.coins_amount = 100
                return mock_setting
            return None
        
        # Mock get_active_events
        async def mock_get_active_events(session, event_type=None):
            if event_type == "points_multiplier":
                return [mock_event]
            return []
        
        with patch('core.points_manager.get_db') as mock_get_db, \
             patch('db.crud.get_coin_reward_setting', side_effect=mock_get_coin_reward_setting), \
             patch('core.event_engine.get_db') as mock_event_db, \
             patch('core.event_engine.get_active_events', side_effect=mock_get_active_events) as mock_get_events, \
             patch('core.event_engine.EventEngine.handle_referral_reward', return_value=False), \
             patch('core.points_manager.add_points') as mock_add_points, \
             patch('db.crud.get_or_create_event_participant', return_value=MagicMock()), \
             patch('core.event_engine.EventEngine.track_challenge_progress', return_value=[]):
            
            mock_get_db.return_value.__aiter__.return_value = [mock_session]
            mock_event_db.return_value.__aiter__.return_value = [mock_session]
            
            # Test award_referral_profile_complete
            result = await PointsManager.award_referral_profile_complete(
                referrer_id=1,
                referred_id=2
            )
            
            assert result is True
            
            # Verify that add_points was called with multiplied coins
            calls = mock_add_points.call_args_list
            assert len(calls) == 2
            
            # Check referrer points (first call) - should be multiplied
            # add_points signature: (session, user_id, points, type, source, description, related_user_id)
            referrer_call = calls[0]
            assert referrer_call[0][1] == 1  # referrer_id (second arg)
            assert referrer_call[0][2] == 400  # 200 * 2 = 400 coins (third arg)
            assert referrer_call[0][4] == "referral_profile_complete"  # source (fifth arg)
            
            # Check referred user points (second call) - should be multiplied
            referred_call = calls[1]
            assert referred_call[0][1] == 2  # referred_id (second arg)
            assert referred_call[0][2] == 200  # 100 * 2 = 200 coins (third arg)
            assert referred_call[0][4] == "referral_profile_complete"  # source (fifth arg)
    
    @pytest.mark.asyncio
    async def test_referral_profile_complete_with_points_multiplier_excluded_source(self):
        """Test referral profile completion with points_multiplier event that excludes referral."""
        # Mock database session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Create mock event with multiplier 2.0 only for chat_success (not referral)
        mock_event = MagicMock(spec=Event)
        mock_event.id = 1
        mock_event.event_type = "points_multiplier"
        mock_event.config_json = json.dumps({
            "multiplier": 2.0,
            "apply_to_sources": ["chat_success", "daily_login"]
        })
        
        # Mock get_coin_reward_setting
        async def mock_get_coin_reward_setting(session, activity_type: str):
            mock_setting = MagicMock()
            if activity_type == "referral_profile_complete":
                mock_setting.is_active = True
                mock_setting.coins_amount = 200
                return mock_setting
            elif activity_type == "referral_referred_signup":
                mock_setting.is_active = True
                mock_setting.coins_amount = 100
                return mock_setting
            return None
        
        with patch('core.points_manager.get_db') as mock_get_db, \
             patch('db.crud.get_coin_reward_setting', side_effect=mock_get_coin_reward_setting), \
             patch('core.event_engine.get_db') as mock_event_db, \
             patch('core.event_engine.get_active_events', return_value=[mock_event]) as mock_get_events, \
             patch('core.event_engine.EventEngine.handle_referral_reward', return_value=False), \
             patch('core.points_manager.add_points') as mock_add_points, \
             patch('core.event_engine.EventEngine.track_challenge_progress', return_value=[]):
            
            mock_get_db.return_value.__aiter__.return_value = [mock_session]
            mock_event_db.return_value.__aiter__.return_value = [mock_session]
            
            # Test award_referral_profile_complete
            result = await PointsManager.award_referral_profile_complete(
                referrer_id=1,
                referred_id=2
            )
            
            assert result is True
            
            # Verify that add_points was called with original coins (not multiplied)
            calls = mock_add_points.call_args_list
            assert len(calls) == 2
            
            # Check referrer points (first call) - should NOT be multiplied
            # add_points signature: (session, user_id, points, type, source, description, related_user_id)
            referrer_call = calls[0]
            assert referrer_call[0][1] == 1  # referrer_id (second arg)
            assert referrer_call[0][2] == 200  # 200 coins (not multiplied) (third arg)
            assert referrer_call[0][4] == "referral_profile_complete"  # source (fifth arg)
            
            # Check referred user points (second call) - should NOT be multiplied
            referred_call = calls[1]
            assert referred_call[0][1] == 2  # referred_id (second arg)
            assert referred_call[0][2] == 100  # 100 coins (not multiplied) (third arg)
            assert referred_call[0][4] == "referral_profile_complete"  # source (fifth arg)
    
    @pytest.mark.asyncio
    async def test_referral_profile_complete_with_referral_reward_event(self):
        """Test referral profile completion with referral_reward event (premium instead of coins)."""
        # Mock database session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Create mock event with premium reward
        mock_event = MagicMock(spec=Event)
        mock_event.id = 1
        mock_event.event_type = "referral_reward"
        mock_event.event_name = "Test Referral Event"
        mock_event.config_json = json.dumps({"premium_days": 7})
        
        # Mock user
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.premium_expires_at = None
        mock_user.is_premium = False
        
        # Mock get_coin_reward_setting
        async def mock_get_coin_reward_setting(session, activity_type: str):
            mock_setting = MagicMock()
            if activity_type == "referral_profile_complete":
                mock_setting.is_active = True
                mock_setting.coins_amount = 200
                return mock_setting
            elif activity_type == "referral_referred_signup":
                mock_setting.is_active = True
                mock_setting.coins_amount = 100
                return mock_setting
            return None
        
        # Mock get_active_events
        async def mock_get_active_events(session, event_type=None):
            if event_type == "referral_reward":
                return [mock_event]
            return []
        
        with patch('core.points_manager.get_db') as mock_get_db, \
             patch('db.crud.get_coin_reward_setting', side_effect=mock_get_coin_reward_setting), \
             patch('core.event_engine.get_db') as mock_event_db, \
             patch('core.event_engine.get_active_events', side_effect=mock_get_active_events) as mock_get_events, \
             patch('core.event_engine.get_event_participant', return_value=None) as mock_get_participant, \
             patch('db.crud.get_referral_count', return_value=1), \
             patch('core.event_engine.get_user_by_id', return_value=mock_user), \
             patch('db.crud.create_premium_subscription', return_value=MagicMock()), \
             patch('db.crud.create_event_reward', return_value=MagicMock()), \
             patch('core.event_engine.get_or_create_event_participant') as mock_get_participant, \
             patch('core.points_manager.add_points') as mock_add_points, \
             patch('core.event_engine.EventEngine.track_challenge_progress', return_value=[]):
            
            # Create mock participant with has_received_reward attribute
            mock_participant = MagicMock()
            mock_participant.has_received_reward = False
            mock_get_participant.return_value = mock_participant
            
            mock_get_db.return_value.__aiter__.return_value = [mock_session]
            mock_event_db.return_value.__aiter__.return_value = [mock_session]
            
            # Test award_referral_profile_complete
            result = await PointsManager.award_referral_profile_complete(
                referrer_id=1,
                referred_id=2
            )
            
            assert result is True
            
            # Verify that add_points was called only for referred user (not referrer)
            # Because referral_reward event gives premium to referrer instead of coins
            calls = mock_add_points.call_args_list
            assert len(calls) == 1  # Only referred user gets coins
            
            # Check referred user points (should still get coins)
            # add_points signature: (session, user_id, points, type, source, description, related_user_id)
            referred_call = calls[0]
            assert referred_call[0][1] == 2  # referred_id (second arg)
            assert referred_call[0][2] == 100  # 100 coins (third arg)
            assert referred_call[0][4] == "referral_profile_complete"  # source (fifth arg)
    
    @pytest.mark.asyncio
    async def test_apply_points_multiplier_with_empty_apply_to_sources(self):
        """Test that points_multiplier applies to all sources when apply_to_sources is empty."""
        # Mock database session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Create mock event with multiplier 2.0 and empty apply_to_sources
        mock_event = MagicMock(spec=Event)
        mock_event.id = 1
        mock_event.event_type = "points_multiplier"
        mock_event.config_json = json.dumps({"multiplier": 2.0})
        
        async def mock_get_active_events(session, event_type=None):
            return [mock_event]
        
        with patch('core.event_engine.get_db') as mock_get_db, \
             patch('core.event_engine.get_active_events', side_effect=mock_get_active_events), \
             patch('db.crud.get_or_create_event_participant', return_value=MagicMock()) as mock_participant:
            
            mock_get_db.return_value.__aiter__.return_value = [mock_session]
            
            # Test apply_points_multiplier with referral_profile_complete source
            result = await EventEngine.apply_points_multiplier(
                user_id=1,
                base_points=200,
                source="referral_profile_complete"
            )
            
            # Should be multiplied (2.0 * 200 = 400)
            assert result == 400
    
    @pytest.mark.asyncio
    async def test_apply_points_multiplier_with_specific_source(self):
        """Test that points_multiplier applies only to specified sources."""
        # Mock database session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Create mock event with multiplier 2.0 only for chat_success
        mock_event = MagicMock(spec=Event)
        mock_event.id = 1
        mock_event.event_type = "points_multiplier"
        mock_event.config_json = json.dumps({
            "multiplier": 2.0,
            "apply_to_sources": ["chat_success"]
        })
        
        async def mock_get_active_events(session, event_type=None):
            return [mock_event]
        
        with patch('core.event_engine.get_db') as mock_get_db, \
             patch('core.event_engine.get_active_events', side_effect=mock_get_active_events) as mock_get_events:
            
            mock_get_db.return_value.__aiter__.return_value = [mock_session]
            
            # Test apply_points_multiplier with chat_success source (should be multiplied)
            result1 = await EventEngine.apply_points_multiplier(
                user_id=1,
                base_points=100,
                source="chat_success"
            )
            assert result1 == 200  # 100 * 2 = 200
            
            # Test apply_points_multiplier with referral_profile_complete source (should NOT be multiplied)
            result2 = await EventEngine.apply_points_multiplier(
                user_id=1,
                base_points=200,
                source="referral_profile_complete"
            )
            assert result2 == 200  # Not multiplied (original value)
    
    @pytest.mark.asyncio
    async def test_apply_points_multiplier_with_referral_source(self):
        """Test that points_multiplier applies to referral_profile_complete when specified."""
        # Mock database session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Create mock event with multiplier 2.0 for referral_profile_complete
        mock_event = MagicMock(spec=Event)
        mock_event.id = 1
        mock_event.event_type = "points_multiplier"
        mock_event.config_json = json.dumps({
            "multiplier": 2.0,
            "apply_to_sources": ["referral_profile_complete"]
        })
        
        async def mock_get_active_events(session, event_type=None):
            return [mock_event]
        
        with patch('core.event_engine.get_db') as mock_get_db, \
             patch('core.event_engine.get_active_events', side_effect=mock_get_active_events) as mock_get_events, \
             patch('db.crud.get_or_create_event_participant', return_value=MagicMock()) as mock_participant:
            
            mock_get_db.return_value.__aiter__.return_value = [mock_session]
            
            # Test apply_points_multiplier with referral_profile_complete source (should be multiplied)
            result = await EventEngine.apply_points_multiplier(
                user_id=1,
                base_points=200,
                source="referral_profile_complete"
            )
            assert result == 400  # 200 * 2 = 400
            
            # Test apply_points_multiplier with chat_success source (should NOT be multiplied)
            result2 = await EventEngine.apply_points_multiplier(
                user_id=1,
                base_points=100,
                source="chat_success"
            )
            assert result2 == 100  # Not multiplied (original value)
    
    @pytest.mark.asyncio
    async def test_referral_profile_complete_coins_from_database(self):
        """Test that referral coins are read from database correctly."""
        # Mock database session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Mock coin reward settings
        async def mock_get_coin_reward_setting(session, activity_type: str):
            mock_setting = MagicMock()
            if activity_type == "referral_profile_complete":
                mock_setting.is_active = True
                mock_setting.coins_amount = 500
                return mock_setting
            elif activity_type == "referral_referred_signup":
                mock_setting.is_active = True
                mock_setting.coins_amount = 300
                return mock_setting
            return None
        
        # Mock get_active_events
        async def mock_get_active_events(session, event_type=None):
            return []
        
        with patch('core.points_manager.get_db') as mock_get_db, \
             patch('db.crud.get_coin_reward_setting', side_effect=mock_get_coin_reward_setting), \
             patch('core.event_engine.get_db') as mock_event_db, \
             patch('core.event_engine.get_active_events', side_effect=mock_get_active_events) as mock_get_events, \
             patch('core.event_engine.EventEngine.handle_referral_reward', return_value=False), \
             patch('core.points_manager.add_points') as mock_add_points, \
             patch('core.event_engine.EventEngine.track_challenge_progress', return_value=[]):
            
            mock_get_db.return_value.__aiter__.return_value = [mock_session]
            mock_event_db.return_value.__aiter__.return_value = [mock_session]
            
            # Test award_referral_profile_complete
            result = await PointsManager.award_referral_profile_complete(
                referrer_id=1,
                referred_id=2
            )
            
            assert result is True
            
            # Verify that coins were read from database
            calls = mock_add_points.call_args_list
            assert len(calls) == 2
            
            # Check referrer points (should be from database: 500)
            # add_points signature: (session, user_id, points, type, source, description, related_user_id)
            referrer_call = calls[0]
            assert referrer_call[0][2] == 500  # From database (third arg)
            
            # Check referred user points (should be from database: 300)
            referred_call = calls[1]
            assert referred_call[0][2] == 300  # From database (third arg)
    
    @pytest.mark.asyncio
    async def test_referral_profile_complete_fallback_to_settings(self):
        """Test that referral coins fallback to settings when not in database."""
        # Mock database session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Mock coin reward settings (all return None - not in database)
        async def mock_get_coin_reward_setting(session, activity_type: str):
            return None  # Not in database
        
        # Mock settings object
        mock_settings_obj = MagicMock()
        mock_settings_obj.POINTS_REFERRAL_REFERRER = 500
        mock_settings_obj.POINTS_REFERRAL_REFERRED = 200
        
        with patch('core.points_manager.get_db') as mock_get_db, \
             patch('db.crud.get_coin_reward_setting', side_effect=mock_get_coin_reward_setting), \
             patch('core.event_engine.get_db') as mock_event_db, \
             patch('core.event_engine.get_active_events', return_value=[]) as mock_get_events, \
             patch('core.event_engine.EventEngine.handle_referral_reward', return_value=False), \
             patch('core.points_manager.add_points') as mock_add_points, \
             patch('core.points_manager.settings', mock_settings_obj), \
             patch('core.event_engine.EventEngine.track_challenge_progress', return_value=[]):
            
            mock_get_db.return_value.__aiter__.return_value = [mock_session]
            mock_event_db.return_value.__aiter__.return_value = [mock_session]
            
            # Test award_referral_profile_complete
            result = await PointsManager.award_referral_profile_complete(
                referrer_id=1,
                referred_id=2
            )
            
            assert result is True
            
            # Verify that coins were from settings (fallback)
            calls = mock_add_points.call_args_list
            assert len(calls) == 2
            
            # Check referrer points (should be from settings: 500)
            # add_points signature: (session, user_id, points, type, source, description, related_user_id)
            referrer_call = calls[0]
            assert referrer_call[0][2] == 500  # From settings (third arg)
            
            # Check referred user points (should be from settings: 200)
            referred_call = calls[1]
            assert referred_call[0][2] == 200  # From settings (third arg)

