import asyncio
import random
from loguru import logger
from telegram.error import (
    TelegramError, Forbidden, BadRequest,
    NetworkError, TimedOut
)

from ..data.db_manager import db_manager

def escape_markdown(text):
    """转义Markdown特殊字符，以便在MarkdownV2模式下正确显示"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    # 不转义反引号，因为我们使用它作为代码格式
    # 但确保反引号是成对出现的
    
    # 先检查并修复不成对的反引号
    backquote_count = text.count('`')
    if backquote_count % 2 != 0:
        # 如果反引号数量不是偶数，添加一个额外的反引号到末尾
        text += '`'
        logger.warning("检测到不成对的反引号，已自动修复")
    
    # 转义其他特殊字符
    escaped_text = text
    for char in special_chars:
        escaped_text = escaped_text.replace(char, f'\\{char}')
    
    # 检查是否有未转义的圆括号，这是常见问题源
    if '(' in escaped_text and '\\(' not in escaped_text:
        logger.warning(f"转义后仍存在未转义的左括号，可能导致解析失败")
    if ')' in escaped_text and '\\)' not in escaped_text:
        logger.warning(f"转义后仍存在未转义的右括号，可能导致解析失败")
    
    return escaped_text

async def send_message_with_retry(context, chat_id, text, parse_mode=None, reply_markup=None, max_retries=5, retry_delay=2, broadcast_mode=False):
    """发送消息，带重试机制
    
    broadcast_mode: 是否为广播模式，如果是广播模式则发送失败后不进行重试
    """
    retries = 0
    
    # 如果使用MarkdownV2，对文本进行转义
    # 注意：对于HTML和Markdown模式，我们尝试确保反引号是成对的
    if parse_mode in ['MarkdownV2', 'Markdown', 'HTML']:
        # 检查反引号是否成对
        backquote_count = text.count('`')
        if backquote_count % 2 != 0:
            # 如果反引号数量不是偶数，添加一个额外的反引号到末尾
            text += '`'
            logger.warning("检测到不成对的反引号，已自动修复")
    
    original_text = text
    if parse_mode == 'MarkdownV2':
        text = escape_markdown(text)
        # 如果转义前后文本不同，记录日志以便调试
        if original_text != text:
            logger.debug(f"文本已被转义用于MarkdownV2格式")
    
    # 广播模式下最多只尝试一次
    actual_max_retries = 0 if broadcast_mode else max_retries
    
    while retries <= actual_max_retries:
        try:
            # 添加随机小延迟，避免多个请求同时发送
            await asyncio.sleep(random.uniform(0.1, 0.5))
            
            return await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                # 增加连接超时时间
                connect_timeout=15,
                read_timeout=15
            )
        except BadRequest as e:
            if "can't parse entities" in str(e).lower():
                error_msg = f"解析实体失败 {chat_id}: {e}"
                logger.error(error_msg)
                
                # 如果是MarkdownV2模式出错，尝试使用预格式化文本块
                if parse_mode == 'MarkdownV2':
                    logger.warning("尝试使用预格式化文本块代替普通文本")
                    try:
                        # 使用预格式化文本块（代码块）包装内容
                        formatted_text = f"```\n{original_text}\n```"
                        return await context.bot.send_message(
                            chat_id=chat_id,
                            text=formatted_text,
                            parse_mode=parse_mode,
                            reply_markup=reply_markup
                        )
                    except Exception as code_block_e:
                        logger.error(f"预格式化文本块尝试也失败: {code_block_e}")
                
                # 尝试降级处理 - 移除解析模式重试
                logger.warning("尝试不使用解析模式重新发送")
                try:
                    return await context.bot.send_message(
                        chat_id=chat_id,
                        text=original_text,  # 使用原始未转义文本
                        parse_mode=None,  # 不使用解析模式
                        reply_markup=reply_markup
                    )
                except Exception as inner_e:
                    logger.error(f"降级处理也失败: {inner_e}")
                return None
        except Forbidden as e:
            logger.error(f"权限错误，无法发送消息到 {chat_id}: {e}")
            # 用户可能已阻止机器人，移除活跃聊天
            db_manager.remove_active_chat(chat_id)
            return None
        except BadRequest as e:
            if "chat not found" in str(e).lower():
                logger.error(f"聊天不存在 {chat_id}: {e}")
                db_manager.remove_active_chat(chat_id)
                return None
            elif "message is too long" in str(e).lower():
                # 消息太长，尝试分段发送
                logger.warning(f"消息太长，尝试分段发送: {e}")
                chunks = split_message(text)
                for chunk in chunks:
                    await asyncio.sleep(0.5)  # 避免发送过快
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=chunk,
                        parse_mode=parse_mode
                    )
                return None
            else:
                logger.error(f"发送消息失败 {chat_id}: {e}")
                retries += 1
        except NetworkError as e:
            error_str = str(e)
            logger.error(f"网络错误 {chat_id}: {e}")
            # 特别处理RemoteProtocolError错误
            if "RemoteProtocolError" in error_str or "Server disconnected" in error_str:
                logger.warning(f"检测到服务器断开连接错误，延长等待时间后重试")
                if not broadcast_mode:
                    await asyncio.sleep(retry_delay * 2 * retries)  # 对于这种错误，增加更长的等待时间
            retries += 1
        except TimedOut as e:
            logger.error(f"发送消息超时 {chat_id}: {e}")
            retries += 1
        except TelegramError as e:
            logger.error(f"Telegram错误 {chat_id}: {e}")
            retries += 1
        except Exception as e:
            error_str = str(e)
            logger.error(f"发送消息未知错误 {chat_id}: {e}")
            # 特别处理RemoteProtocolError错误
            if "RemoteProtocolError" in error_str or "Server disconnected" in error_str:
                logger.warning(f"检测到服务器断开连接错误，延长等待时间后重试")
                if not broadcast_mode:
                    await asyncio.sleep(retry_delay * 2 * retries)  # 对于这种错误，增加更长的等待时间
            retries += 1
            
        if retries <= actual_max_retries:
            # 使用指数退避+随机抖动
            jitter = random.uniform(0.1, 1.0)
            wait_time = retry_delay * (2 ** retries) * jitter
            
            # 广播模式下不记录重试信息
            if not broadcast_mode:
                logger.info(f"重试发送消息，等待 {wait_time:.2f} 秒后第 {retries} 次重试")
            
            await asyncio.sleep(wait_time)
    
    return None

def split_message(text, max_length=4096):
    """将长消息分割成多个部分"""
    if len(text) <= max_length:
        return [text]
        
    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break
            
        # 尝试在换行处分割
        split_index = text[:max_length].rfind('\n')
        if split_index == -1:  # 没有找到换行符
            split_index = max_length
            
        parts.append(text[:split_index])
        text = text[split_index:].lstrip()
        
    return parts 

async def edit_message_with_retry(context, chat_id, message_id, text, parse_mode=None, reply_markup=None, max_retries=5, retry_delay=2):
    """编辑消息，带重试机制"""
    retries = 0
    
    # 如果使用MarkdownV2，对文本进行转义
    # 对于HTML和Markdown模式，我们尝试确保反引号是成对的
    if parse_mode in ['MarkdownV2', 'Markdown', 'HTML']:
        # 检查反引号是否成对
        backquote_count = text.count('`')
        if backquote_count % 2 != 0:
            # 如果反引号数量不是偶数，添加一个额外的反引号到末尾
            text += '`'
            logger.warning("编辑消息: 检测到不成对的反引号，已自动修复")
    
    original_text = text
    if parse_mode == 'MarkdownV2':
        text = escape_markdown(text)
        # 如果转义前后文本不同，记录日志以便调试
        if original_text != text:
            logger.debug(f"编辑消息: 文本已被转义用于MarkdownV2格式")
    
    while retries <= max_retries:
        try:
            # 添加随机小延迟，避免多个请求同时发送
            await asyncio.sleep(random.uniform(0.1, 0.5))
            
            return await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                # 增加连接超时时间
                connect_timeout=15,
                read_timeout=15
            )
        except BadRequest as e:
            # 处理消息未修改的错误
            if "message is not modified" in str(e).lower():
                logger.info(f"消息未修改，内容相同: {chat_id}, {message_id}")
                return None  # 不需要重试，这不是真正的错误
            elif "chat not found" in str(e).lower():
                logger.error(f"聊天不存在 {chat_id}: {e}")
                db_manager.remove_active_chat(chat_id)
                return None
            elif "can't parse entities" in str(e).lower():
                error_msg = f"编辑消息时解析实体失败 {chat_id}: {e}"
                logger.error(error_msg)
                
                # 如果是MarkdownV2模式出错，尝试使用预格式化文本块
                if parse_mode == 'MarkdownV2':
                    logger.warning("尝试使用预格式化文本块代替普通文本")
                    try:
                        # 使用预格式化文本块（代码块）包装内容
                        formatted_text = f"```\n{original_text}\n```"
                        return await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=formatted_text,
                            parse_mode=parse_mode,
                            reply_markup=reply_markup
                        )
                    except Exception as code_block_e:
                        logger.error(f"预格式化文本块尝试也失败: {code_block_e}")
                
                # 尝试降级处理 - 移除解析模式重试
                logger.warning("尝试不使用解析模式重新编辑")
                try:
                    return await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=original_text,  # 使用原始未转义文本
                        parse_mode=None,  # 不使用解析模式
                        reply_markup=reply_markup
                    )
                except Exception as inner_e:
                    logger.error(f"降级处理也失败: {inner_e}")
                return None
            else:
                logger.error(f"编辑消息失败 {chat_id}, {message_id}: {e}")
                retries += 1
        except Forbidden as e:
            logger.error(f"权限错误，无法编辑消息 {chat_id}: {e}")
            db_manager.remove_active_chat(chat_id)
            return None
        except NetworkError as e:
            error_str = str(e)
            logger.error(f"网络错误 {chat_id}: {e}")
            # 特别处理RemoteProtocolError错误
            if "RemoteProtocolError" in error_str or "Server disconnected" in error_str:
                logger.warning(f"编辑消息时检测到服务器断开连接错误，延长等待时间后重试")
                await asyncio.sleep(retry_delay * 2 * retries)  # 对于这种错误，增加更长的等待时间
            retries += 1
        except TimedOut as e:
            logger.error(f"编辑消息超时 {chat_id}: {e}")
            retries += 1
        except TelegramError as e:
            logger.error(f"Telegram错误 {chat_id}: {e}")
            retries += 1
        except Exception as e:
            error_str = str(e)
            logger.error(f"编辑消息未知错误 {chat_id}: {e}")
            # 特别处理RemoteProtocolError错误
            if "RemoteProtocolError" in error_str or "Server disconnected" in error_str:
                logger.warning(f"编辑消息时检测到服务器断开连接错误，延长等待时间后重试")
                await asyncio.sleep(retry_delay * 2 * retries)  # 对于这种错误，增加更长的等待时间
            retries += 1
            
        if retries <= max_retries:
            # 使用指数退避+随机抖动
            jitter = random.uniform(0.1, 1.0)
            wait_time = retry_delay * (2 ** retries) * jitter
            logger.info(f"重试编辑消息，等待 {wait_time:.2f} 秒后第 {retries} 次重试")
            await asyncio.sleep(wait_time)
    
    return None