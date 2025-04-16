import html
import json
import traceback
import sys
import time
import threading
from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram.error import (
    Conflict, NetworkError, TimedOut, RetryAfter, 
    BadRequest, Forbidden, TelegramError
)

from ..config.config_manager import ADMIN_ID

# 全局状态跟踪
_error_counters = {
    "conflict": 0,
    "network": 0,
    "timeout": 0,
    "retry": 0,
    "general": 0,
    "last_reset": time.time()
}

# 错误计数器重置线程
def reset_error_counters():
    """每小时重置错误计数器"""
    while True:
        time.sleep(3600)  # 每小时重置一次
        _error_counters["conflict"] = 0
        _error_counters["network"] = 0
        _error_counters["timeout"] = 0
        _error_counters["retry"] = 0
        _error_counters["general"] = 0
        _error_counters["last_reset"] = time.time()
        logger.info("已重置错误计数器")

# 启动重置线程
reset_thread = threading.Thread(target=reset_error_counters, daemon=True)
reset_thread.start()

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理错误的回调函数，针对不同类型的错误进行专门处理"""
    if context.error is None:
        logger.warning("接收到空错误对象")
        return
    
    error = context.error
    error_type = type(error).__name__
    error_str = str(error)
    
    # 检查是否需要重置计数器
    current_time = time.time()
    if current_time - _error_counters["last_reset"] > 3600:
        for key in _error_counters:
            if key != "last_reset":
                _error_counters[key] = 0
        _error_counters["last_reset"] = current_time
    
    # 根据错误类型进行处理
    if isinstance(error, Conflict):
        _error_counters["conflict"] += 1
        
        # 处理冲突错误 - 多个getUpdates请求冲突
        if "terminated by other getUpdates request" in error_str:
            logger.error(f"检测到getUpdates冲突 (#{_error_counters['conflict']}): {error}")
            
            # 如果冲突次数过多，建议重启机器人
            if _error_counters["conflict"] >= 5:
                logger.critical("获取更新冲突次数过多，建议重启机器人")
                
                # 向管理员发送通知
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"⚠️ 严重警告：检测到多个bot实例运行\n\n在过去的时间内发生了{_error_counters['conflict']}次冲突错误。请检查系统中是否有多个相同bot实例在运行。\n\n建议立即重启机器人。"
                    )
                except Exception as e:
                    logger.error(f"向管理员发送冲突通知失败: {e}")
                
                # 如果冲突次数过多，为避免API被封禁，可以选择自动退出
                if _error_counters["conflict"] >= 10:
                    logger.critical("冲突错误次数过多，为保护API令牌，机器人将自动退出")
                    # 延迟退出，给通知发送留出时间
                    def delayed_exit():
                        time.sleep(5)
                        sys.exit(1)
                    threading.Thread(target=delayed_exit, daemon=True).start()
            return
    
    elif isinstance(error, NetworkError):
        _error_counters["network"] += 1
        logger.error(f"网络错误 (#{_error_counters['network']}): {error}")
        
        # 如果网络错误次数过多，通知管理员
        if _error_counters["network"] % 5 == 0:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"⚠️ 网络警告：检测到网络不稳定\n\n在过去的时间内发生了{_error_counters['network']}次网络错误。请检查服务器网络连接。"
                )
            except Exception as e:
                logger.error(f"向管理员发送网络错误通知失败: {e}")
        return
    
    elif isinstance(error, TimedOut):
        _error_counters["timeout"] += 1
        logger.error(f"请求超时 (#{_error_counters['timeout']}): {error}")
        
        # 如果超时错误次数过多，通知管理员
        if _error_counters["timeout"] % 5 == 0:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"⚠️ 超时警告：API请求响应缓慢\n\n在过去的时间内发生了{_error_counters['timeout']}次超时错误。建议检查网络质量或降低请求频率。"
                )
            except Exception as e:
                logger.error(f"向管理员发送超时错误通知失败: {e}")
        return
    
    elif isinstance(error, RetryAfter):
        _error_counters["retry"] += 1
        retry_seconds = error.retry_after if hasattr(error, 'retry_after') else "未知"
        logger.error(f"达到限制，需要等待 (#{_error_counters['retry']}): {error}，等待时间: {retry_seconds}秒")
        
        # 达到限制时通知管理员
        if _error_counters["retry"] <= 3:  # 只发送前几次通知，避免刷屏
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"⚠️ 限速警告：达到Telegram API限制\n\n需要等待{retry_seconds}秒后重试。请减少操作频率。"
                )
            except Exception as e:
                logger.error(f"向管理员发送限速通知失败: {e}")
        return
    
    # 其他一般错误
    _error_counters["general"] += 1
    
    # 记录错误信息
    logger.error(f"发生异常 (#{_error_counters['general']}): {error}")
    
    # 获取完整的错误堆栈
    tb_list = traceback.format_exception(None, error, error.__traceback__)
    tb_string = "".join(tb_list)
    
    # 记录详细错误信息
    logger.error(f"错误详情:\n{tb_string}")
    
    # 构建错误消息
    error_message = (
        f"发生错误: {error}\n\n"
        f"类型: {error_type}\n"
    )
    
    # 如果是更新引起的错误，添加更新信息
    if isinstance(update, Update) and update.effective_chat:
        error_message += f"聊天ID: {update.effective_chat.id}\n"
        if update.effective_user:
            error_message += f"用户ID: {update.effective_user.id}\n"
        if update.effective_message:
            error_message += f"消息ID: {update.effective_message.message_id}\n"
    
    # 只有非网络/超时/冲突错误，且错误次数不多时才向管理员发送通知
    # 避免大量错误消息刷屏
    if _error_counters["general"] <= 10 or _error_counters["general"] % 10 == 0:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"❌ 机器人发生错误 (#{_error_counters['general']})\n\n{error_message}\n\n详细错误已记录到日志"
            )
        except Exception as e:
            logger.error(f"向管理员发送错误通知失败: {e}") 