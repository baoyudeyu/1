import asyncio
import json
import logging
import re
import os
import sys
from datetime import datetime
from loguru import logger
from telegram.ext import ContextTypes
from time import time

from ..config.config_manager import BROADCAST_CONFIG
from ..data.db_manager import db_manager
from ..data.cache_manager import cache
from ..services.prediction import verify_prediction, auto_run_all_predictions
from ..services.broadcast import send_broadcast, check_latest_lottery, send_special_group_info, send_broadcast_message
from ..utils.utils_helper import fetch_lottery_data, parse_datetime, analyze_lottery_data
from ..utils.message_handler import is_broadcasting, check_broadcasting_status
from ..utils.message_utils import send_message_with_retry

# 定义特定群组ID
SPECIAL_GROUP_ID = -1002312536972

async def check_lottery_update(context: ContextTypes.DEFAULT_TYPE):
    """检查新开奖结果并更新数据库"""
    try:
        # 更新当前时间戳
        cache['current_time'] = time()
        
        # 获取最新开奖数据
        lottery_data = fetch_lottery_data(page=1, min_records=BROADCAST_CONFIG["HISTORY_COUNT"])
        if not lottery_data:
            logger.warning("获取开奖数据失败")
            return
            
        # 获取数据库中最新的期号
        latest_db_record = db_manager.get_latest_record()
        latest_db_qihao = latest_db_record[1] if latest_db_record else "0"
        
        # 检查是否有新数据
        new_records = []
        for record in lottery_data:
            if record['qihao'] > latest_db_qihao:
                new_records.append(record)
        
        # 如果没有新数据，返回
        if not new_records:
            logger.debug("没有新的开奖数据")
            return
            
        # 处理新数据
        for record in new_records:
            try:
                qihao = record['qihao']
                opentime_str = record['opentime']
                opennum = record['opennum']
                
                # 解析开奖时间
                opentime = parse_datetime(opentime_str)
                
                # 计算和值
                num_parts = opennum.split('+')
                total_sum = sum(int(n) for n in num_parts)
                
                # 分析开奖结果
                analysis = analyze_lottery_data(opennum, total_sum)
                is_big = analysis['is_big']
                is_odd = analysis['is_odd']
                combination_type = analysis['combination_type']
                
                # 插入数据库
                db_manager.save_lottery_record({
                    'qihao': qihao, 
                    'opentime': opentime, 
                    'opennum': opennum, 
                    'sum': total_sum, 
                    'is_big': is_big, 
                    'is_odd': is_odd, 
                    'combination_type': combination_type
                })
                
                logger.info(f"新增开奖记录: 期号={qihao}, 开奖号码={opennum}, 和值={total_sum}")
                
                # 验证预测结果
                try:
                    # 使用asyncio.create_task包装可能的非协程函数
                    if callable(verify_prediction):
                        # 如果是异步函数，使用await调用
                        if asyncio.iscoroutinefunction(verify_prediction):
                            await verify_prediction(context, qihao, opennum, total_sum, is_big, is_odd, combination_type)
                        # 如果是同步函数，使用run_in_executor调用
                        else:
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(None, lambda: verify_prediction(context, qihao, opennum, total_sum, is_big, is_odd, combination_type))
                except Exception as e:
                    logger.error(f"验证预测结果失败: {e}")
                
                # 自动运行所有预测
                try:
                    # 确保auto_run_all_predictions函数被正确调用
                    from ..services.prediction import auto_run_all_predictions
                    # 同样处理auto_run_all_predictions可能是同步函数的情况
                    if callable(auto_run_all_predictions):
                        if asyncio.iscoroutinefunction(auto_run_all_predictions):
                            await auto_run_all_predictions(context)
                        else:
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(None, lambda: auto_run_all_predictions(context))
                except Exception as e:
                    logger.error(f"自动运行预测失败: {e}")
                
            except Exception as e:
                logger.error(f"处理开奖记录失败: {e}")
                continue
        
        # 向特定群组发送信息，直接调用send_special_group_info，不再传入record参数
        # send_special_group_info函数会自己获取最新数据
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
            
            # 获取更新后的最新记录用于发送给其他用户
            updated_record = db_manager.get_latest_record()
            if updated_record:
                await send_broadcast_message(context, chat_id, updated_record)
            
    except Exception as e:
        logger.error(f"检查新开奖结果失败: {e}")

def initialize_lottery_data():
    """机器人启动时的初始化"""
    try:
        lottery_data = fetch_lottery_data(page=1, min_records=BROADCAST_CONFIG["HISTORY_COUNT"])
        if lottery_data:
            cache['last_lottery_data'] = lottery_data
            latest_record = lottery_data[0]
            
            # 保存所有获取到的记录
            for record in lottery_data:
                opentime = parse_datetime(record['opentime'])
                opennum = record['opennum']
                total_sum = int(record['sum'])
                qihao = record['qihao']
                
                analysis = analyze_lottery_data(opennum, total_sum)
                
                record_data = {
                    'qihao': qihao,
                    'opentime': opentime,
                    'opennum': opennum,
                    'sum': total_sum,
                    'is_big': analysis['is_big'],
                    'is_odd': analysis['is_odd'],
                    'combination_type': analysis['combination_type']
                }
                
                db_manager.save_lottery_record(record_data)
            
            logger.info(f"初始化完成，已保存{len(lottery_data)}条记录")
            return True
    except Exception as e:
        logger.error(f"初始化失败: {e}")
        return False