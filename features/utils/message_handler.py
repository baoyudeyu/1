import asyncio
import json
import re
import os
import sys
import time
import threading
from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import (
    TelegramError, Forbidden, BadRequest,
    NetworkError, ChatMigrated, TimedOut
)

from ..config.config_manager import ADMIN_ID, BROADCAST_CONFIG, SPECIAL_GROUP_ID, TARGET_GROUP_ID
from ..data.db_manager import db_manager
from ..services.broadcast import start_broadcast, stop_broadcast
from ..services.prediction import start_prediction
from ..prediction import predictor
from ..utils.message_utils import send_message_with_retry
from ..services.verification.verification_service import verify_user_access

# 广播状态引用 - 初始化为False
is_broadcasting = False

# 命令处理锁 - 防止同一用户短时间内发送多个命令
_user_command_locks = {}
_user_last_command_time = {}
_command_cooldown = 2  # 命令冷却时间（秒）

# 添加播报功能处理函数
def start_broadcasting(chat_id):
    """启动开奖播报"""
    global is_broadcasting
    try:
        # 记录活跃聊天
        db_manager.add_active_chat(chat_id)
        # 检查是否有活跃聊天，并更新全局状态
        active_chats = db_manager.get_active_chats()
        is_broadcasting = len(active_chats) > 0
        logger.info(f"用户 {chat_id} 启动了开奖播报，当前活跃聊天数: {len(active_chats)}")
        return True
    except Exception as e:
        logger.error(f"启动开奖播报失败: {e}")
        return False

def stop_broadcasting(chat_id):
    """停止开奖播报"""
    global is_broadcasting
    try:
        # 移除活跃聊天
        db_manager.remove_active_chat(chat_id)
        
        # 检查是否还有其他活跃聊天
        active_chats = db_manager.get_active_chats()
        # 更新全局状态
        is_broadcasting = len(active_chats) > 0
        
        logger.info(f"用户 {chat_id} 停止了开奖播报，当前活跃聊天数: {len(active_chats)}")
        
        # 确保全局状态正确更新
        if not active_chats and is_broadcasting:
            is_broadcasting = False
            logger.warning("强制更新广播状态为非活跃")
            
        return True
    except Exception as e:
        logger.error(f"停止开奖播报失败: {e}")
        return False

# 检查是否有活跃的广播聊天
def check_broadcasting_status():
    """检查是否有活跃的广播聊天"""
    global is_broadcasting
    active_chats = db_manager.get_active_chats()
    # 确保全局状态与活跃聊天列表一致
    is_broadcasting = len(active_chats) > 0
    logger.debug(f"检查广播状态: 活跃聊天数={len(active_chats)}, 广播状态={is_broadcasting}")
    return is_broadcasting

# 命令冷却检查
def check_command_cooldown(user_id):
    """检查用户命令是否处于冷却期"""
    current_time = time.time()
    last_time = _user_last_command_time.get(user_id, 0)
    
    # 如果距离上次命令时间小于冷却时间，拒绝处理
    if current_time - last_time < _command_cooldown:
        return False
    
    # 更新最后命令时间
    _user_last_command_time[user_id] = current_time
    return True

# 使用asyncio.wait_for包装任务，添加超时限制
async def run_with_timeout(coro, timeout=5):
    """使用超时运行协程"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"命令执行超时，已取消")
        return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理文本消息"""
    global is_broadcasting
    
    # 检查更新对象是否有效
    if not update or not update.effective_message:
        logger.warning("收到无效更新对象")
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # 记录消息时间戳
    msg_time = update.effective_message.date.timestamp()
    current_time = time.time()
    
    # 忽略过旧的消息（超过30秒）
    if current_time - msg_time > 30:
        logger.debug(f"忽略过旧的消息：{update.effective_message.text[:20]}...")
        return
    
    # 命令冷却检查 - 防止用户快速发送多个命令
    if not check_command_cooldown(user_id):
        logger.debug(f"用户 {user_id} 命令处于冷却期，忽略")
        return
    
    # 过滤群组消息，只处理私聊消息和特定群组的消息
    if update.effective_chat.type in ['group', 'supergroup']:
        # 如果是指定的特殊群组，允许处理
        if chat_id == SPECIAL_GROUP_ID:
            pass  # 继续处理
        else:
            # 其他群组直接忽略
            logger.debug(f"忽略非特定群组的消息: {chat_id}")
            return
    
    # 获取消息文本
    text = update.message.text
    
    # 管理员特殊命令，不需要验证直接处理
    if user_id == ADMIN_ID:
        # 管理员命令处理略...
        # 此处省略已有的管理员命令处理代码
        
        # 新增管理员命令：刷新状态
        if text == "刷新机器人状态":
            await update.message.reply_text("🔄 正在刷新机器人状态...")
            
            # 清理过期锁
            for uid in list(_user_command_locks.keys()):
                if current_time - _user_last_command_time.get(uid, 0) > 60:
                    _user_command_locks.pop(uid, None)
            
            # 重新检查广播状态
            old_status = is_broadcasting
            new_status = check_broadcasting_status()
            
            # 清理命令时间记录
            old_count = len(_user_last_command_time)
            _user_last_command_time.clear()
            
            await update.message.reply_text(
                f"✅ 机器人状态已刷新\n"
                f"- 广播状态: {old_status} → {new_status}\n"
                f"- 已清理 {old_count} 条命令记录\n"
                f"- 当前时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            return
    
    # 每次都重新验证用户权限，确保退出群组的用户不能使用机器人
    try:
        # 设置验证超时，防止验证过程卡死
        has_access = await run_with_timeout(
            verify_user_access(update, context),
            timeout=5
        )
        
        if has_access is None:  # 超时
            logger.warning(f"用户 {user_id} 验证超时")
            await update.message.reply_text("⚠️ 验证超时，请稍后再试")
            return
            
        if not has_access:
            # 如果验证失败，不继续执行
            logger.info(f"用户 {user_id} 验证失败，无法处理消息: {text[:20]}...")
            return
    except Exception as e:
        logger.error(f"验证用户访问权限时出错: {e}")
        await update.message.reply_text("⚠️ 验证过程出错，请稍后再试")
        return
    
    # 处理简单命令 - 优先处理简单的状态切换命令
    if text == "开奖播报":
        # 先更新状态，再启动广播
        start_broadcasting(chat_id)
        # 使用非阻塞方式启动广播
        asyncio.create_task(start_broadcast(update, context))
    elif text == "停止播报":
        # 先停止广播，再更新状态
        stop_broadcasting(chat_id)
        await stop_broadcast(update, context)
    
    # 处理预测命令 - 这些命令可能耗时较长，使用异步任务执行
    elif text.startswith(("单双预测", "大小预测", "杀组预测", "双组预测")):
        # 提取预测类型
        pred_mapping = {
            "单双预测": "single_double",
            "大小预测": "big_small",
            "杀组预测": "kill_group",
            "双组预测": "double_group"
        }
        
        for key, value in pred_mapping.items():
            if text.startswith(key):
                pred_type = value
                # 发送等待消息
                await update.message.reply_text(f"🔄 正在生成{key}，请稍候...")
                # 启动异步任务执行预测，设置较长的超时时间
                asyncio.create_task(
                    run_with_timeout(
                        start_prediction(update, context, pred_type),
                        timeout=30  # 预测操作可能需要更长时间
                    )
                )
                break
    else:
        # 其他命令 - 可根据需要扩展
        pass

async def handle_algorithm_switch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理算法切换命令"""
    text = update.message.text
    
    # 解析命令格式：切换算法 [类型] [算法号]
    # 例如：切换算法 单双 2
    pattern = r"切换算法\s+(\S+)\s+(\d+)"
    match = re.match(pattern, text)
    
    if not match:
        await update.message.reply_text(
            "❌ 命令格式错误\n"
            "正确格式：切换算法 [类型] [算法号]\n"
            "例如：切换算法 单双 2\n\n"
            "可用类型：单双、大小、杀组、双组\n"
            "可用算法：1-3号"
        )
        return
        
    type_name = match.group(1)
    algo_num = int(match.group(2))
    
    # 类型名称映射
    type_map = {
        "单双": "single_double",
        "大小": "big_small",
        "杀组": "kill_group",
        "双组": "double_group"
    }
    
    if type_name not in type_map:
        await update.message.reply_text(f"❌ 未知预测类型: {type_name}\n可用类型：单双、大小、杀组、双组")
        return
        
    pred_type = type_map[type_name]
    
    # 检查算法号是否有效
    if algo_num < 1 or algo_num > 3:
        await update.message.reply_text(f"❌ 无效的算法号: {algo_num}\n可用算法：1-3号")
        return
        
    # 切换算法
    old_algo = predictor.current_algorithms.get(pred_type, 1)
    predictor.current_algorithms[pred_type] = algo_num
    
    # 获取算法性能
    performance = db_manager.get_algorithm_performance(pred_type)
    algo_info = next((p for p in performance if p['algorithm_number'] == algo_num), None)
    
    if algo_info:
        success_rate = algo_info['success_rate'] * 100
        performance_text = f"准确率: {success_rate:.1f}% ({algo_info['total_count']}期)"
    else:
        performance_text = "暂无性能数据"
    
    await update.message.reply_text(
        f"✅ 已将{type_name}预测算法从{old_algo}号切换为{algo_num}号\n"
        f"📊 {algo_num}号算法{performance_text}"
    )
    
    # 记录算法切换
    logger.info(f"手动切换算法: {pred_type} 从 {old_algo}号 到 {algo_num}号") 