import asyncio
import logging
from datetime import datetime, timedelta
from loguru import logger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ChatMemberUpdated
from telegram.ext import ContextTypes
from telegram.error import TelegramError, BadRequest
from telegram.constants import ChatMemberStatus

from ...config.config_manager import VERIFICATION_REQUIRED, TARGET_GROUP_ID, ADMIN_ID
from ...data.db_manager import db_manager
from ...utils.message_utils import send_message_with_retry, edit_message_with_retry

# 用于跟踪用户验证状态的缓存
verification_cache = {}

# 用于跟踪用户验证失败次数，防止暴力尝试
verification_fail_counter = {}
# 最大允许的连续失败次数
MAX_VERIFICATION_FAILS = 5
# 失败计数器重置时间(秒)
FAIL_COUNTER_RESET_TIME = 1800  # 30分钟

async def start_verification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """启动用户验证流程"""
    if not VERIFICATION_REQUIRED:
        logger.info("验证功能已关闭，跳过验证流程")
        return True
        
    user = update.effective_user
    user_id = user.id
    chat_id = update.effective_chat.id
    
    # 记录验证请求
    logger.info(f"用户 {user_id} ({user.username or '无用户名'}) 请求验证")
    
    # 记录用户信息到数据库
    db_manager.add_user(
        user_id=user_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # 检查用户是否已验证
    if db_manager.is_user_verified(user_id):
        logger.info(f"用户 {user_id} 在数据库中已标记为验证通过，检查是否仍在群组")
        
        # 即使数据库显示已验证，也再次检查用户是否在群组中
        try:
            is_still_member = await verify_group_membership(context, user_id, force_check=True)
            if is_still_member:
                logger.info(f"用户 {user_id} 仍在群组中，无需重新验证")
                return True
            else:
                logger.warning(f"用户 {user_id} 虽在数据库中标记为已验证，但已不在群组中，需要重新验证")
                # 更新数据库状态
                db_manager.set_user_verified(user_id, False)
        except Exception as e:
            logger.error(f"检查用户 {user_id} 群组成员身份时出错: {e}")
            # 出错时保持用户状态不变，但继续显示验证消息
    
    # 构建验证消息
    verification_text = (
        "❗️ 需要验证 ❗️\n\n"
        "使用机器人前，您需要加入加拿大之家群组 @id520\n\n"
        "请按照以下步骤操作：\n"
        "1. 点击下方「加拿大之家」按钮加入群组\n"
        "2. 加入群组后，回到此处\n"
        "3. 点击「我已加入，点击验证」按钮完成验证\n\n"
        "验证成功后即可使用所有功能"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("加拿大之家", url="https://t.me/id520"),
            InlineKeyboardButton("我已加入，点击验证", callback_data="verify_membership")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await send_message_with_retry(
            context,
            chat_id=chat_id, 
            text=verification_text,
            reply_markup=reply_markup
        )
        logger.info(f"已向用户 {user_id} 发送验证消息")
        return False
    except Exception as e:
        logger.error(f"发送验证消息失败: {e}")
        return False

async def handle_verification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理验证回调查询"""
    query = update.callback_query
    user = query.from_user
    user_id = user.id
    
    await query.answer()
    
    # 检查是否在目标群组中，如果是则不响应
    if update.effective_chat.id == TARGET_GROUP_ID:
        logger.info(f"忽略来自目标群组 {update.effective_chat.id} 的验证回调")
        return
    
    if query.data == "verify_membership":
        # 检查是否达到最大失败次数
        if user_id in verification_fail_counter and verification_fail_counter[user_id]["count"] >= MAX_VERIFICATION_FAILS:
            last_fail_time = verification_fail_counter[user_id]["last_time"]
            elapsed_seconds = (datetime.now() - last_fail_time).total_seconds()
            
            if elapsed_seconds < FAIL_COUNTER_RESET_TIME:
                # 计算剩余等待时间
                remaining_minutes = int((FAIL_COUNTER_RESET_TIME - elapsed_seconds) / 60)
                
                # 提示用户稍后再试
                cooldown_message = (
                    f"⚠️ 验证失败次数过多，请在 {remaining_minutes} 分钟后再试。\n\n"
                    "如需帮助，请联系管理员。"
                )
                
                try:
                    await edit_message_with_retry(
                        context,
                        chat_id=query.message.chat_id,
                        message_id=query.message.message_id,
                        text=cooldown_message
                    )
                    logger.warning(f"用户 {user_id} 验证失败次数过多，进入冷却期")
                    return False
                except Exception as e:
                    logger.error(f"更新验证冷却消息失败: {e}")
                    return False
            else:
                # 重置失败计数器
                verification_fail_counter[user_id] = {"count": 0, "last_time": datetime.now()}
                logger.info(f"用户 {user_id} 验证冷却期已结束，重置失败计数")
        
        # 显示正在验证的临时消息
        try:
            await edit_message_with_retry(
                context,
                chat_id=query.message.chat_id,
                message_id=query.message.message_id,
                text="⏳ 正在验证您的群组成员身份，请稍候..."
            )
        except Exception as e:
            logger.error(f"更新验证中消息失败: {e}")
        
        # 每次点击验证按钮时，强制清除该用户的缓存，确保获取最新状态
        if user_id in verification_cache:
            verification_cache.pop(user_id, None)
            logger.info(f"用户 {user_id} 点击验证按钮，强制清除验证缓存")
        
        # 尝试验证，并根据结果处理，使用force_check=True参数强制重新验证
        verification_result = await verify_group_membership(context, user_id, force_check=True)
        
        if verification_result:
            # 验证成功
            db_manager.set_user_verified(user_id, True)
            # 重置失败计数
            if user_id in verification_fail_counter:
                verification_fail_counter.pop(user_id, None)
                
            success_message = "✅ 验证成功！您可以正常使用机器人功能了。"
            
            try:
                await edit_message_with_retry(
                    context,
                    chat_id=query.message.chat_id,
                    message_id=query.message.message_id,
                    text=success_message
                )
                logger.info(f"用户 {user_id} 验证成功")
                return True
            except Exception as e:
                logger.error(f"更新验证成功消息失败: {e}")
        else:
            # 验证失败，更新失败计数
            if user_id not in verification_fail_counter:
                verification_fail_counter[user_id] = {"count": 1, "last_time": datetime.now()}
            else:
                verification_fail_counter[user_id]["count"] += 1
                verification_fail_counter[user_id]["last_time"] = datetime.now()
                
            # 更新数据库状态
            db_manager.set_user_verified(user_id, False)
            
            # 获取缓存中的错误信息（如果有）
            error_info = ""
            if user_id in verification_cache and "error" in verification_cache[user_id]:
                error = verification_cache[user_id]["error"]
                if "Chat not found" in error:
                    error_info = "（机器人可能尚未加入目标群组或群组ID配置错误）"
                elif "kicked" in error.lower() or "banned" in error.lower():
                    error_info = "（您可能已被移出或封禁）"
            
            fail_count_info = ""
            if user_id in verification_fail_counter:
                count = verification_fail_counter[user_id]["count"]
                if count > 1:
                    fail_count_info = f"\n\n这是您的第 {count}/{MAX_VERIFICATION_FAILS} 次尝试。多次失败将暂时无法验证。"
            
            fail_message = (
                f"❌ 验证失败！您需要先加入加拿大之家群组 @id520。{error_info}\n\n"
                "请按照以下步骤操作：\n"
                "1. 点击下方「加拿大之家」按钮\n"
                "2. 加入群组\n"
                "3. 回到机器人，点击「我已加入，点击验证」\n\n"
                "如果您确信已加入群组但仍验证失败，请尝试：\n"
                "- 退出并重新加入群组\n"
                "- 等待几分钟后再次验证\n"
                "- 联系管理员协助解决" + fail_count_info
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("加拿大之家", url="https://t.me/id520"),
                    InlineKeyboardButton("我已加入，点击验证", callback_data="verify_membership")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await edit_message_with_retry(
                    context,
                    chat_id=query.message.chat_id,
                    message_id=query.message.message_id,
                    text=fail_message,
                    reply_markup=reply_markup
                )
                logger.warning(f"用户 {user_id} 验证失败，未加入目标群组")
                return False
            except Exception as e:
                logger.error(f"更新验证失败消息失败: {e}")
    
    return False

async def verify_group_membership(context, user_id, force_check=False):
    """验证用户是否已加入目标群组"""
    try:
        # 如果是管理员，直接通过验证
        if user_id == ADMIN_ID:
            logger.warning(f"管理员 {user_id} 验证，自动通过")
            return True
            
        # 尝试从缓存中获取验证结果（如果不是强制检查）
        if not force_check and user_id in verification_cache:
            cache_time = verification_cache[user_id]["time"]
            # 如果缓存时间在2分钟内，且缓存状态为True，则直接返回缓存结果
            # 只有当缓存显示用户已验证时才使用缓存，否则始终重新检查
            if (datetime.now() - cache_time).total_seconds() < 120 and verification_cache[user_id]["status"] == True:
                logger.debug(f"从缓存获取用户 {user_id} 的验证状态: {verification_cache[user_id]['status']}")
                return verification_cache[user_id]["status"]
        
        # 获取群组成员
        try:
            # 查询用户是否是群组成员
            chat_member = await context.bot.get_chat_member(TARGET_GROUP_ID, user_id)
            
            # 检查用户状态是否为member、administrator、creator或restricted
            # restricted状态的用户也是群组成员，只是权限受限
            valid_statuses = [
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR, 
                ChatMemberStatus.OWNER,
                ChatMemberStatus.RESTRICTED
            ]
            is_member = chat_member.status in valid_statuses
            
            if not is_member:
                logger.warning(f"用户 {user_id} 的群组状态为 {chat_member.status}，验证失败")
                # 如果用户不在群组中，标记其已离开
                try:
                    db_manager.mark_member_left_group(user_id, TARGET_GROUP_ID)
                except Exception as e:
                    logger.error(f"标记用户离开群组失败: {e}")
            else:
                logger.info(f"用户 {user_id} 在群组中，状态为 {chat_member.status}，验证成功")
                # 记录用户的群组成员信息
                try:
                    db_manager.add_group_member(
                        user_id=user_id,
                        group_id=TARGET_GROUP_ID,
                        username=getattr(chat_member.user, 'username', None),
                        first_name=getattr(chat_member.user, 'first_name', None),
                        last_name=getattr(chat_member.user, 'last_name', None),
                        status=chat_member.status
                    )
                except Exception as e:
                    logger.error(f"记录群组成员信息失败: {e}")
            
            # 更新缓存
            verification_cache[user_id] = {
                "status": is_member,
                "time": datetime.now()
            }
            
            logger.info(f"验证用户 {user_id} 是否在目标群组: {is_member}, 状态: {chat_member.status}")
            return is_member
            
        except TelegramError as e:
            logger.error(f"获取群组成员失败: {e}")
            
            # 添加详细的错误信息记录，便于排查问题
            error_detail = f"TARGET_GROUP_ID={TARGET_GROUP_ID}, user_id={user_id}, error={str(e)}"
            logger.error(f"详细错误信息: {error_detail}")
            
            # 如果出现错误，尝试重试验证
            try:
                logger.info(f"尝试重试验证用户 {user_id}")
                return await retry_verification(context, user_id)
            except Exception as retry_error:
                logger.error(f"重试验证也失败: {retry_error}")
                
                # 如果是Chat not found错误，标记缓存为无效
                verification_cache[user_id] = {
                    "status": False,
                    "time": datetime.now(),
                    "error": str(e)
                }
                
                # 验证失败，返回False
                return False
    except Exception as e:
        logger.error(f"验证用户群组成员身份时出错: {e}")
        return False

async def verify_user_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """验证用户是否有权限使用机器人功能"""
    if not VERIFICATION_REQUIRED:
        return True
        
    user_id = update.effective_user.id
    
    # 管理员始终有权限
    if user_id == ADMIN_ID:
        return True
    
    # 每次操作都重新检查用户是否在群组中，不依赖数据库状态
    try:
        # 首先尝试从TG API验证
        is_in_group = await verify_group_membership(context, user_id)
        
        if is_in_group:
            # 用户在群组中，更新数据库状态
            if not db_manager.is_user_verified(user_id):
                db_manager.set_user_verified(user_id, True)
                logger.info(f"用户 {user_id} 通过验证，已更新数据库状态")
            return True
        else:
            # 检查数据库中是否有记录表明用户在群组中
            # 这是一个备份机制，以防TG API出错
            if db_manager.is_user_in_group(user_id, TARGET_GROUP_ID):
                logger.warning(f"TG API显示用户 {user_id} 不在群组中，但数据库显示在群组中，允许访问")
                
                # 更新验证状态
                if not db_manager.is_user_verified(user_id):
                    db_manager.set_user_verified(user_id, True)
                
                return True
            
            # 两种方法都确认用户不在群组，清除验证状态
            db_manager.set_user_verified(user_id, False)
            logger.warning(f"用户 {user_id} 不在目标群组，已取消验证状态")
            # 启动验证流程
            await start_verification(update, context)
            return False
    except Exception as e:
        logger.error(f"验证用户访问权限时出错: {e}")
        
        # 出错时，检查数据库中的验证状态和群组成员状态
        try:
            # 首先检查数据库中的群组成员记录
            if db_manager.is_user_in_group(user_id, TARGET_GROUP_ID):
                logger.warning(f"API验证出错，但数据库显示用户 {user_id} 在群组中，允许访问")
                return True
                
            # 然后检查验证状态
            is_verified = db_manager.is_user_verified(user_id)
            
            if not is_verified:
                # 如果数据库显示未验证，启动验证流程
                await start_verification(update, context)
                return False
            
            # 数据库显示已验证，但API检查出错，暂时允许访问
            logger.warning(f"验证过程出错，用户 {user_id} 暂时保持之前的验证状态")
            return True
        except Exception as db_error:
            logger.error(f"检查数据库状态也失败: {db_error}")
            # 两种方法都失败，启动验证流程
            await start_verification(update, context)
            return False

# 重试逻辑
async def retry_verification(context, user_id, max_retries=3):
    """重试验证，最多尝试指定次数"""
    for attempt in range(max_retries):
        try:
            # 查询用户是否是群组成员
            chat_member = await context.bot.get_chat_member(TARGET_GROUP_ID, user_id)
            
            # 检查用户状态是否为member、administrator、creator或restricted
            # restricted状态的用户也是群组成员，只是权限受限
            valid_statuses = [
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR, 
                ChatMemberStatus.OWNER,
                ChatMemberStatus.RESTRICTED
            ]
            is_member = chat_member.status in valid_statuses
            
            # 更新缓存
            verification_cache[user_id] = {
                "status": is_member,
                "time": datetime.now()
            }
            
            logger.info(f"重试验证用户 {user_id}，尝试 #{attempt+1}，结果: {is_member}")
            return is_member
        except Exception as e:
            logger.warning(f"重试验证失败，尝试 #{attempt+1}: {e}")
            if attempt < max_retries - 1:
                # 等待一小段时间再重试
                await asyncio.sleep(1)
            else:
                # 最后一次尝试失败，更新缓存为失败状态
                verification_cache[user_id] = {
                    "status": False,
                    "time": datetime.now(),
                    "error": str(e),
                    "retries": attempt + 1
                }
                return False
    
    return False

# 周期性验证清理
async def periodic_verification_check(context: ContextTypes.DEFAULT_TYPE):
    """定期检查用户验证状态，清理无效的缓存和验证标记"""
    logger.info("开始周期性验证状态检查")
    try:
        # 1. 清理过期的验证缓存
        now = datetime.now()
        expired_users = []
        for user_id, cache_data in verification_cache.items():
            cache_time = cache_data["time"]
            # 缓存超过2小时则过期
            if (now - cache_time).total_seconds() > 7200:  # 2小时
                expired_users.append(user_id)
        
        # 从缓存中删除过期用户
        for user_id in expired_users:
            verification_cache.pop(user_id, None)
        
        logger.info(f"清理了 {len(expired_users)} 个过期的验证缓存")
        
        # 2. 清理验证失败计数器
        expired_counters = []
        for user_id, counter_data in verification_fail_counter.items():
            last_time = counter_data["last_time"]
            if (now - last_time).total_seconds() > FAIL_COUNTER_RESET_TIME:
                expired_counters.append(user_id)
        
        # 从失败计数器中删除过期记录
        for user_id in expired_counters:
            verification_fail_counter.pop(user_id, None)
        
        logger.info(f"清理了 {len(expired_counters)} 个过期的验证失败计数器")
        
        # 3. 检查已验证用户是否仍在群组中
        verified_users = db_manager.get_all_verified_users()
        check_count = 0
        
        for user in verified_users[:50]:  # 每次最多检查50个用户，避免超时
            user_id = user["user_id"]
            try:
                # 检查用户是否已离开群组
                user_left_group = await check_user_left_group(context, user_id, TARGET_GROUP_ID)
                check_count += 1
                
                # 如果用户已离开群组，更新验证状态
                if user_left_group:
                    db_manager.set_user_verified(user_id, False)
                    logger.info(f"周期检查：用户 {user_id} 已离开群组，取消验证状态")
                    
                    # 如果有缓存，也更新缓存
                    if user_id in verification_cache:
                        verification_cache[user_id]["status"] = False
                
                # 为了避免请求过于频繁，每检查10个用户暂停1秒
                if check_count % 10 == 0:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"周期检查用户 {user_id} 状态时出错: {e}")
                # 继续检查下一个用户
                continue
        
        logger.info(f"周期检查完成，共检查了 {check_count} 个已验证用户")
        
    except Exception as e:
        logger.error(f"执行周期性验证检查时出错: {e}")

# 处理群组消息，更新用户的群组成员状态
async def process_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理群组消息，更新用户的群组成员状态"""
    try:
        message = update.message or update.edited_message
        if not message:
            return
            
        user = message.from_user
        if not user:
            return
            
        chat = message.chat
        if not chat or chat.type not in ['group', 'supergroup']:
            # 不是群组消息，直接返回
            logger.debug(f"跳过非群组消息: chat_type={getattr(chat, 'type', 'unknown')}")
            return
            
        # 检查是否是目标群组
        if chat.id != TARGET_GROUP_ID:
            logger.debug(f"跳过非目标群组的消息: chat_id={chat.id}, target={TARGET_GROUP_ID}")
            return
            
        logger.info(f"处理来自目标群组的消息: user_id={user.id}, username={user.username}")
        
        # 更新用户的群组成员状态
        db_manager.add_group_member(
            user_id=user.id,
            group_id=chat.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            status="active"  # 由于用户发送了消息，所以肯定是活跃的
        )
        
        # 同时更新用户的验证状态
        if not db_manager.is_user_verified(user.id):
            db_manager.set_user_verified(user.id, True)
            logger.info(f"用户 {user.id} 在目标群组发送消息，自动更新为已验证状态")
        
        # 更新缓存
        verification_cache[user.id] = {
            "status": True,
            "time": datetime.now()
        }
        
        logger.debug(f"更新用户 {user.id} 在群组 {chat.id} 的活跃状态")
    except Exception as e:
        logger.error(f"处理群组消息更新用户状态时出错: {e}")
        # 记录更详细的错误信息以便调试
        logger.error(f"错误详情: {str(e)}", exc_info=True)

# 检查用户是否已被踢出或离开群组
async def check_user_left_group(context, user_id, group_id):
    """检查用户是否已被踢出或离开群组"""
    try:
        # 确保context.bot不为None
        if not context or not context.bot:
            logger.error(f"检查用户 {user_id} 时context或bot为None")
            return False

        chat_member = await context.bot.get_chat_member(group_id, user_id)
        if chat_member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
            # 用户已离开群组，更新数据库
            db_manager.mark_member_left_group(user_id, group_id)
            logger.info(f"检测到用户 {user_id} 已离开群组 {group_id}")
            return True
        return False
    except BadRequest as e:
        # 用户不存在或被Telegram系统限制
        if "user not found" in str(e).lower() or "user is deactivated" in str(e).lower():
            db_manager.mark_member_left_group(user_id, group_id)
            logger.info(f"用户 {user_id} 不存在或已停用，标记为已离开群组")
            return True
        logger.error(f"检查用户是否离开群组时出错: {e}")
        return False
    except Exception as e:
        logger.error(f"检查用户是否离开群组时出错: {e}")
        return False

# 处理群组成员状态变化
async def process_chat_member_updated(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理群组成员状态变化事件"""
    try:
        chat_member_updated = update.chat_member
        if not chat_member_updated:
            return
            
        # 只处理目标群组的变更
        if chat_member_updated.chat.id != TARGET_GROUP_ID:
            return
            
        # 获取用户信息
        user = chat_member_updated.new_chat_member.user
        user_id = user.id
        
        # 获取新旧状态
        old_status = chat_member_updated.old_chat_member.status
        new_status = chat_member_updated.new_chat_member.status
        
        logger.info(f"用户 {user_id} ({user.username or '无用户名'}) 在群组 {TARGET_GROUP_ID} 的状态从 {old_status} 变为 {new_status}")
        
        # 判断用户是加入还是离开
        valid_statuses = [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR, 
            ChatMemberStatus.OWNER,
            ChatMemberStatus.RESTRICTED
        ]
        
        if new_status in valid_statuses:
            # 用户加入或状态变更为有效状态
            logger.info(f"用户 {user_id} 加入或状态变为有效: {new_status}")
            
            # 更新群组成员信息
            db_manager.add_group_member(
                user_id=user_id,
                group_id=TARGET_GROUP_ID,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                status=new_status
            )
            
            # 更新验证状态
            db_manager.set_user_verified(user_id, True)
            
            # 更新缓存
            verification_cache[user_id] = {
                "status": True,
                "time": datetime.now()
            }
            
            logger.info(f"用户 {user_id} 加入群组，自动更新为已验证状态")
            
        elif old_status in valid_statuses and new_status not in valid_statuses:
            # 用户离开或被踢
            logger.info(f"用户 {user_id} 离开群组: {old_status} -> {new_status}")
            
            # 标记用户离开
            db_manager.mark_member_left_group(user_id, TARGET_GROUP_ID)
            
            # 更新验证状态
            db_manager.set_user_verified(user_id, False)
            
            # 更新缓存
            if user_id in verification_cache:
                verification_cache[user_id] = {
                    "status": False,
                    "time": datetime.now()
                }
            
            logger.info(f"用户 {user_id} 离开群组，更新为未验证状态")
    
    except Exception as e:
        logger.error(f"处理群组成员状态变化时出错: {e}")
        # 记录更详细的错误信息
        logger.error(f"错误详情: {str(e)}", exc_info=True)

def clear_verification_cache():
    """清空验证缓存，通常在重启机器人时调用"""
    verification_cache.clear()
    verification_fail_counter.clear()
    logger.info("已清空验证缓存和失败计数器") 