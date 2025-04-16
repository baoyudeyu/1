from datetime import datetime
from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes
import asyncio
import random

from ..data.db_manager import db_manager
from ..utils.message_utils import send_message_with_retry
from ..data.cache_manager import cache
from ..config.config_manager import CACHE_CONFIG, BROADCAST_CONFIG
from ..utils.utils_helper import format_broadcast_message, format_lottery_record, fetch_lottery_data, parse_datetime, analyze_lottery_data
from ..services.prediction import start_prediction

# 定义特定群组ID
SPECIAL_GROUP_ID = -1002312536972

# 记录最新处理的期号
latest_processed_qihao = None

async def send_broadcast(context: ContextTypes.DEFAULT_TYPE, chat_id=None):
    """发送开奖播报"""
    try:
        # 获取最近的开奖记录
        recent_records = db_manager.get_recent_records(10)  # 使用配置中的BROADCAST_HISTORY_COUNT
        if not recent_records:
            logger.error("获取开奖记录失败")
            return None
            
        # 检查缓存是否过期
        cache_key = 'last_broadcast_message'
        current_time = datetime.now().timestamp()
        if (cache.get(cache_key) and 
            current_time - cache.get('last_broadcast_time', 0) < CACHE_CONFIG["BROADCAST_TTL"]):
            logger.info("使用缓存的播报消息")
            message = cache[cache_key]
        else:
            logger.info("生成新的播报消息")
            message = format_broadcast_message(recent_records)
            cache[cache_key] = message
            cache['last_broadcast_time'] = current_time
            
        # 如果指定了聊天ID，发送消息
        if chat_id:
            # 使用重试机制发送消息，设置为广播模式
            await send_message_with_retry(
                context,
                chat_id=chat_id,
                text=message,
                parse_mode='MarkdownV2',
                broadcast_mode=True
            )
        return message
    except Exception as e:
        logger.error(f"发送开奖播报失败: {e}")
        return None

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """启动开奖播报"""
    chat_id = update.effective_chat.id
    
    # 记录活跃聊天
    db_manager.add_active_chat(chat_id)
    
    # 发送初始播报
    message = await send_broadcast(context, chat_id)
    if message:
        await update.message.reply_text("✅ 开奖播报已启动，将实时推送最新开奖结果")
    else:
        await update.message.reply_text("❌ 启动开奖播报失败，请稍后再试")

async def stop_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """停止开奖播报"""
    chat_id = update.effective_chat.id
    
    # 移除活跃聊天
    db_manager.remove_active_chat(chat_id)
    
    await update.message.reply_text("✅ 开奖播报已停止")

async def send_special_group_info(context, record):
    """向特定群组发送开奖信息和所有预测类型"""
    global latest_processed_qihao
    
    try:
        # 主动从API获取最新数据，不再依赖传入的record参数
        from ..utils.utils_helper import fetch_lottery_data, parse_datetime, analyze_lottery_data
        from ..data.db_manager import db_manager
        from ..config.config_manager import BROADCAST_CONFIG
        
        # 获取API的最新数据
        lottery_data = fetch_lottery_data(page=1, min_records=1)
        if not lottery_data or len(lottery_data) == 0:
            logger.error("从API获取最新开奖数据失败")
            return
            
        latest_api_record = lottery_data[0]
        latest_qihao = latest_api_record.get('qihao', '')
        
        # 检查是否已经处理过该期号
        if latest_qihao == latest_processed_qihao:
            logger.info(f"期号 {latest_qihao} 已处理，跳过")
            return
        
        # 获取数据库中最新的记录，用于比较
        db_latest_record = db_manager.get_latest_record()
        db_latest_qihao = db_latest_record[1] if db_latest_record else "0"
        
        # 如果API的期号比数据库的更新，保存到数据库
        if latest_qihao > db_latest_qihao:
            logger.info(f"发现更新的期号: API={latest_qihao}, 数据库={db_latest_qihao}")
            
            # 解析并保存API数据
            opentime = parse_datetime(latest_api_record['opentime'])
            opennum = latest_api_record['opennum']
            total_sum = sum(int(n) for n in opennum.split('+'))
            
            # 分析开奖结果
            analysis = analyze_lottery_data(opennum, total_sum)
            
            # 构建记录数据
            record_data = {
                'qihao': latest_qihao,
                'opentime': opentime,
                'opennum': opennum,
                'sum': total_sum,
                'is_big': analysis['is_big'],
                'is_odd': analysis['is_odd'],
                'combination_type': analysis['combination_type']
            }
            
            # 保存到数据库
            db_manager.save_lottery_record(record_data)
            logger.info(f"已保存最新开奖记录: {latest_qihao}")
            
            # 重新获取最新记录，确保数据已更新
            updated_record = db_manager.get_latest_record()
            if not updated_record or updated_record[1] != latest_qihao:
                logger.warning(f"数据库最新记录不匹配: 期望={latest_qihao}, 实际={updated_record[1] if updated_record else 'None'}")
        
        # 更新最新处理的期号
        latest_processed_qihao = latest_qihao
        
        # 1. 发送开奖信息 - 使用最新获取的数据
        recent_records = db_manager.get_recent_records(10)
        if recent_records:
            message = format_broadcast_message(recent_records)
            await send_message_with_retry(context, SPECIAL_GROUP_ID, message, parse_mode='MarkdownV2', broadcast_mode=True)
        
        # 添加随机延迟
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # 2. 发送单双预测
        await start_prediction_for_group(context, 'single_double')
        
        # 添加随机延迟
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # 3. 发送大小预测
        await start_prediction_for_group(context, 'big_small')
        
        # 添加随机延迟
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # 4. 发送双组预测
        await start_prediction_for_group(context, 'double_group')
        
        # 添加随机延迟
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # 5. 发送杀组预测
        await start_prediction_for_group(context, 'kill_group')
        
        logger.info(f"已向特定群组 {SPECIAL_GROUP_ID} 发送期号 {latest_qihao} 的所有信息")
    except Exception as e:
        logger.error(f"向特定群组发送信息失败: {e}")

async def start_prediction_for_group(context, pred_type):
    """为特定群组启动预测"""
    try:
        # 创建一个模拟更新对象，以便调用预测函数
        class MockUpdate:
            def __init__(self, chat_id):
                self.effective_chat = MockChat(chat_id)
                self.message = MockMessage(chat_id)
                
        class MockChat:
            def __init__(self, chat_id):
                self.id = chat_id
                
        class MockMessage:
            def __init__(self, chat_id):
                self.chat_id = chat_id
                self.chat = MockChat(chat_id)
                
            async def reply_text(self, text, parse_mode=None, reply_markup=None):
                await send_message_with_retry(context, self.chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup, broadcast_mode=True)
        
        # 创建模拟更新对象
        mock_update = MockUpdate(SPECIAL_GROUP_ID)
        
        # 调用预测函数
        await start_prediction(mock_update, context, pred_type)
    except Exception as e:
        logger.error(f"为特定群组启动预测失败: {e}")

async def check_latest_lottery(context):
    """检查最新开奖结果并处理"""
    try:
        # 直接调用send_special_group_info，不传入参数
        await send_special_group_info(context, None)
        
        # 检查活跃聊天
        active_chats = db_manager.get_active_chats()
        if not active_chats:
            return
            
        # 给除了特定群组外的其他活跃聊天发送广播
        for chat_id in active_chats:
            # 跳过特定群组，避免重复发送
            if chat_id == SPECIAL_GROUP_ID:
                continue
                
            # 获取当前最新记录
            latest_record = db_manager.get_latest_record()
            if latest_record:
                await send_broadcast_message(context, chat_id, latest_record)
    except Exception as e:
        logger.error(f"检查最新开奖结果失败: {e}")

async def send_broadcast_message(context, chat_id, record):
    """向指定聊天发送广播消息"""
    try:
        # 格式化消息
        message = format_broadcast_message([record])
        
        # 使用重试机制发送消息，设置为广播模式
        await send_message_with_retry(
            context,
            chat_id=chat_id,
            text=message,
            parse_mode='MarkdownV2',
            broadcast_mode=True  # 使用广播模式，发送失败后不重试
        )
        logger.debug(f"已向聊天 {chat_id} 发送播报消息")
        return True
    except Exception as e:
        logger.error(f"向聊天 {chat_id} 发送播报消息失败: {e}")
        return False 