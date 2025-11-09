"""
Event handlers for users to view and participate in events.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from datetime import datetime

from db.database import get_db
from db.crud import (
    get_user_by_telegram_id,
    get_visible_events,
    get_event_participant,
    get_event_participant_count,
)
from core.event_engine import EventEngine
from bot.keyboards.engagement import get_engagement_menu_keyboard

router = Router()


@router.callback_query(F.data == "events:list")
async def events_list(callback: CallbackQuery):
    """Show active events to user."""
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        events = await get_visible_events(db_session)
        
        if not events:
            await callback.message.edit_text(
                "🎯 ایونت‌ها\n\n"
                "در حال حاضر هیچ ایونت فعالی وجود ندارد.\n\n"
                "💡 ایونت‌ها شامل:\n"
                "• ضریب امتیاز (مثلاً 2x امتیاز)\n"
                "• پاداش معرفی (پریمیوم)\n"
                "• چالش با قرعه‌کشی",
                reply_markup=get_engagement_menu_keyboard()
            )
            await callback.answer()
            return
        
        text = "🎯 ایونت‌های فعال\n\n"
        
        for event in events:
            now = datetime.utcnow()
            days_left = (event.end_date - now).days
            
            # Get user progress
            participant = await get_event_participant(db_session, event.id, user.id)
            progress = participant.progress_value if participant else 0
            
            text += f"🎉 {event.event_name}\n"
            
            if event.event_description:
                text += f"{event.event_description}\n"
            
            # Show event-specific info
            if event.event_type == "points_multiplier":
                import json
                config = json.loads(event.config_json) if event.config_json else {}
                multiplier = config.get("multiplier", 1.0)
                text += f"✨ ضریب امتیاز: {multiplier}x\n"
            
            elif event.event_type == "referral_reward":
                import json
                config = json.loads(event.config_json) if event.config_json else {}
                premium_days = config.get("premium_days", 0)
                text += f"💎 پاداش: {premium_days} روز پریمیوم برای هر معرفی\n"
            
            elif event.event_type == "challenge_lottery":
                import json
                config = json.loads(event.config_json) if event.config_json else {}
                target_metric = config.get("target_metric", "")
                target_value = config.get("target_value", 0)
                reward_type = config.get("reward_type", "")
                reward_value = config.get("reward_value", 0)
                
                metric_names = {
                    "chat_count": "چت",
                    "referral_count": "معرفی",
                    "like_count": "لایک"
                }
                
                text += f"🎯 چالش: {metric_names.get(target_metric, target_metric)} = {target_value}\n"
                text += f"🏆 پاداش: {reward_value} {reward_type}\n"
                text += f"📊 پیشرفت شما: {progress}/{target_value}\n"
            
            text += f"⏰ {days_left} روز باقی مانده\n\n"
        
        text += "💡 با انجام فعالیت‌های مختلف در ایونت‌ها شرکت کنید!"
        
        await callback.message.edit_text(text, reply_markup=get_engagement_menu_keyboard())
        await callback.answer()


@router.callback_query(F.data.startswith("event:progress:"))
async def event_progress(callback: CallbackQuery):
    """Show user's progress in a specific event."""
    try:
        event_id = int(callback.data.split(":")[-1])
    except ValueError:
        await callback.answer("❌ خطا", show_alert=True)
        return
    
    user_id = callback.from_user.id
    
    async for db_session in get_db():
        user = await get_user_by_telegram_id(db_session, user_id)
        if not user:
            await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
            return
        
        from db.crud import get_event_by_id
        event = await get_event_by_id(db_session, event_id)
        if not event:
            await callback.answer("❌ ایونت یافت نشد.", show_alert=True)
            return
        
        # Get user progress
        progress_info = await EventEngine.get_user_event_progress(user.id, event_id)
        
        if not progress_info:
            await callback.answer("❌ اطلاعات یافت نشد.", show_alert=True)
            return
        
        info = progress_info[0]
        
        text = f"📊 پیشرفت شما در ایونت\n\n"
        text += f"🎯 {event.event_name}\n\n"
        text += f"📈 پیشرفت: {info['progress']}\n"
        
        if event.event_type == "challenge_lottery":
            text += f"🎯 هدف: {info.get('target_value', 0)}\n"
            text += f"📊 معیار: {info.get('target_metric', '')}\n"
            
            if info['progress'] >= info.get('target_value', 0):
                text += "\n✅ شما واجد شرایط قرعه‌کشی هستید!\n"
            else:
                remaining = info.get('target_value', 0) - info['progress']
                text += f"\n⏳ {remaining} تا واجد شرایط شدن\n"
        
        elif event.event_type == "points_multiplier":
            import json
            config = json.loads(event.config_json) if event.config_json else {}
            multiplier = config.get("multiplier", 1.0)
            text += f"✨ ضریب فعال: {multiplier}x\n"
            text += "\n💡 هر امتیازی که می‌گیری با این ضریب محاسبه می‌شه!"
        
        elif event.event_type == "referral_reward":
            import json
            config = json.loads(event.config_json) if event.config_json else {}
            premium_days = config.get("premium_days", 0)
            text += f"💎 پاداش: {premium_days} روز پریمیوم\n"
            text += "\n💡 هر معرفی جدید = پاداش پریمیوم!"
        
        await callback.message.edit_text(text, reply_markup=get_engagement_menu_keyboard())
        await callback.answer()

