import asyncio
import os
import sys
import json
import re
import random
from datetime import datetime
from loguru import logger
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from ..data.db_manager import db_manager
from ..prediction import predictor
from ..utils.message_utils import send_message_with_retry
from ..data.cache_manager import cache
from ..config.config_manager import PREDICTION_CONFIG, CACHE_CONFIG
from ..utils.utils_helper import format_prediction_message, analyze_lottery_data

async def send_prediction(context: ContextTypes.DEFAULT_TYPE, chat_id, prediction_type):
    """发送预测消息"""
    try:
        logger.info("开始获取预测数据...")
        # 根据预测类型获取不同数量的历史记录
        if prediction_type == 'kill_group':
            # 杀组预测需要更多的历史数据
            recent_records = db_manager.get_recent_records(100)  # 获取100条记录用于杀组预测
            if not recent_records or len(recent_records) < 10:
                logger.error(f"获取历史记录失败，当前记录数：{len(recent_records) if recent_records else 0}")
                return None
            logger.info(f"为杀组预测获取了 {len(recent_records)} 条历史记录")
        else:
            # 其他预测类型使用原来的10条记录
            recent_records = db_manager.get_recent_records(10)
            if not recent_records or len(recent_records) < 10:
                logger.error(f"获取历史记录失败，当前记录数：{len(recent_records) if recent_records else 0}")
                return None
            
        latest_qihao = recent_records[0][1]
        next_qihao = str(int(latest_qihao) + 1)
        logger.info(f"当前最新期号：{latest_qihao}，准备预测{next_qihao}期结果")
        
        # 检查缓存是否过期
        cache_key = f'last_prediction_message_{prediction_type}'
        current_time = datetime.now().timestamp()
        if (cache.get(cache_key) and 
            current_time - cache.get(f'last_prediction_time_{prediction_type}', 0) < CACHE_CONFIG["PREDICTION_TTL"] and
            cache.get(f'last_prediction_qihao_{prediction_type}') == next_qihao):
            logger.info("使用缓存的预测结果")
            message = cache[cache_key]
        else:
            logger.info("计算新的预测结果")
            prediction = predictor.calculate_prediction(recent_records, prediction_type)
            if prediction:
                try:
                    # 获取历史预测记录
                    prediction_history = db_manager.get_prediction_history(prediction_type)
                    
                    # 保存新预测
                    db_manager.save_prediction(prediction)
                    
                    # 检查是否有算法切换信息
                    switch_info = prediction.get('switch_info')
                    if switch_info:
                        switch_message = f"⚠️ 算法已从{switch_info['from_algo']}号切换为{switch_info['to_algo']}号\n"
                        switch_message += f"原因: {switch_info['reason']}\n\n"
                    else:
                        switch_message = ""
                    
                    # 格式化消息
                    message = format_prediction_message(prediction, prediction_history)
                    
                    # 如果有算法切换信息，添加到消息前面
                    if switch_info:
                        message = switch_message + message
                    
                    # 更新缓存
                    cache[cache_key] = message
                    cache[f'last_prediction_qihao_{prediction_type}'] = next_qihao
                    cache[f'last_prediction_time_{prediction_type}'] = current_time
                    
                    logger.info(f"预测结果已缓存：{prediction_type} {next_qihao}")
                except Exception as e:
                    logger.error(f"处理预测结果失败: {e}")
                    message = f"预测失败: {e}"
            else:
                message = "无法生成预测，请稍后再试"
        
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
        logger.error(f"发送预测消息失败: {e}")
        return None

async def start_prediction(update: Update, context: ContextTypes.DEFAULT_TYPE, prediction_type):
    """发送单次预测"""
    chat_id = update.effective_chat.id
    
    # 记录活跃聊天
    db_manager.add_active_chat(chat_id)
    
    # 发送预测
    message = await send_prediction(context, chat_id, prediction_type)
    if message:
        type_name = {
            'single_double': '单双',
            'big_small': '大小',
            'kill_group': '杀组',
            'double_group': '双组'
        }.get(prediction_type, prediction_type)
        
        logger.info(f"已发送{type_name}预测")
        return True
    else:
        return False

def verify_prediction(context=None, qihao=None, opennum=None, total_sum=None, is_big=None, is_odd=None, combination_type=None):
    """验证预测结果"""
    try:
        # 如果没有提供qihao，则获取最新开奖记录
        if not qihao or not opennum or total_sum is None:
            latest_record = db_manager.get_latest_record()
            if not latest_record:
                logger.error("获取最新开奖记录失败")
                return False  # 明确返回False而不是None
                
            qihao = latest_record[1]
            opennum = latest_record[3]
            total_sum = int(latest_record[4])
            
            # 分析开奖结果
            analysis = analyze_lottery_data(opennum, total_sum)
            is_big = analysis['is_big']
            is_odd = analysis['is_odd']
            combination_type = analysis['combination_type']
        
        # 验证各类型预测
        verified_any = False  # 跟踪是否验证了任何预测
        for pred_type in ['single_double', 'big_small', 'kill_group', 'double_group']:
            # 获取该期号的预测
            prediction = db_manager.get_prediction_by_qihao(qihao, pred_type)
            if not prediction:
                logger.debug(f"未找到{qihao}期的{pred_type}预测")
                continue
                
            verified_any = True  # 标记至少验证了一个预测
                
            # 验证预测结果
            is_correct = False
            try:
                if pred_type == 'single_double':
                    # 检查预测内容是否包含数字（如"小11"）
                    if re.search(r'\d+', prediction[2]):
                        # 如果包含数字，需要精确匹配
                        actual_result = '单' if is_odd else '双'
                        # 提取预测中的单双部分
                        pred_single_double = '单' if '单' in prediction[2] else '双'
                        is_correct = pred_single_double == actual_result
                    else:
                        # 原有逻辑
                        if "单" in prediction[2]:
                            is_correct = is_odd  # 如果预测包含"单"，则结果为单数时正确
                        else:  # "双"
                            is_correct = not is_odd  # 如果预测包含"双"，则结果为双数时正确
                elif pred_type == 'big_small':
                    # 检查预测内容是否包含数字（如"小11"）
                    if re.search(r'\d+', prediction[2]):
                        # 如果包含数字，需要精确匹配
                        actual_result = '大' if is_big else '小'
                        # 提取预测中的大小部分
                        pred_big_small = '大' if '大' in prediction[2] else '小'
                        is_correct = pred_big_small == actual_result
                    else:
                        # 原有逻辑
                        pred_size = "大" if "大" in prediction[2] else "小"
                        is_correct = (pred_size == "大" and is_big) or (pred_size == "小" and not is_big)
                elif pred_type == 'kill_group':
                    kill_target = prediction[2][1:] if len(prediction[2]) > 1 else ""
                    actual_result = f"{'大' if is_big else '小'}{'单' if is_odd else '双'}"
                    is_correct = kill_target != actual_result
                    
                    # 记录杀组预测结果详情，用于后续分析
                    logger.info(f"杀组预测验证: 期号={qihao}, 预测杀={kill_target}, 实际结果={actual_result}, 正确={is_correct}")
                    
                    # 更新算法性能数据
                    try:
                        # 提取使用的算法编号
                        algorithm_used = json.loads(prediction[4]) if prediction[4] else {}
                        algorithm_number = algorithm_used.get('kill_group', 1)
                        
                        # 更新算法性能
                        db_manager.update_algorithm_performance(
                            'kill_group', 
                            algorithm_number, 
                            is_correct
                        )
                    except Exception as e:
                        logger.error(f"更新杀组算法性能失败: {e}")
                elif pred_type == 'double_group':
                    # 双组预测验证逻辑
                    try:
                        # 处理双组预测格式
                        if ':' in prediction[2]:
                            pred_parts = prediction[2].split(':')[0].split('/')
                        else:
                            pred_parts = prediction[2].split('/')
                            
                        actual_result = f"{'大' if is_big else '小'}{'单' if is_odd else '双'}"
                        is_correct = any(combo == actual_result for combo in pred_parts)
                    except Exception as e:
                        logger.error(f"验证双组预测失败: {e}")
                        is_correct = False
            except Exception as e:
                logger.error(f"验证预测结果失败: {e}")
                continue
            
            # 更新预测结果，只传递必要的参数
            update_success = db_manager.update_prediction_result(qihao, pred_type, opennum, total_sum, is_correct)
            if not update_success:
                logger.error(f"更新预测结果失败: {qihao} {pred_type}")
                continue
                
            logger.info(f"验证预测结果: {qihao}期 {pred_type} {'正确' if is_correct else '错误'}")
            
            # 更新算法性能
            try:
                # 获取使用的算法号
                if prediction[5] and prediction[5].strip():  # 确保algorithm_used不为空
                    try:
                        algo_info = json.loads(prediction[5])
                        algo_num = algo_info.get(pred_type, 1)
                    except json.JSONDecodeError:
                        logger.error(f"解析算法信息失败: {prediction[5]}")
                        algo_num = 1
                else:
                    # 如果算法信息为空，使用默认算法号
                    logger.warning(f"算法信息为空，使用默认值")
                    algo_num = 1
                    
                # 确保算法号在有效范围内
                if algo_num < 1 or algo_num > 3:
                    logger.warning(f"算法号超出有效范围: {algo_num}，使用默认值1")
                    algo_num = 1
                
                # 针对单双和大小预测，强制使用算法1
                if pred_type in ['single_double', 'big_small']:
                    algo_num = 1
                    
                # 记录当前尝试更新的算法号
                logger.info(f"更新算法性能 - 类型: {pred_type}, 算法号: {algo_num}, 是否正确: {is_correct}")
                    
                # 更新算法性能
                predictor.update_algorithm_performance(pred_type, algo_num, is_correct)
            except Exception as e:
                logger.error(f"更新算法性能失败: {e}")
        
        return verified_any  # 返回是否验证了任何预测
    except Exception as e:
        logger.error(f"验证预测结果失败: {e}")
        return False  # 明确返回False而不是None

async def auto_run_all_predictions(context: ContextTypes.DEFAULT_TYPE):
    """自动运行所有类型的预测"""
    try:
        logger.info("自动运行所有类型的预测开始")
        
        # 获取最新开奖记录
        latest_record = db_manager.get_latest_record()
        if not latest_record:
            logger.error("获取最新开奖记录失败")
            return False
            
        qihao = latest_record[1]
        
        # 计算下一期期号
        next_qihao = str(int(qihao) + 1)
        
        # 获取历史记录 - 移到循环外部，避免重复获取
        recent_records = db_manager.get_recent_records(30)
        if not recent_records:
            logger.error("获取历史记录失败")
            return False
        
        # 为每种预测类型进行预测
        for pred_type in ['single_double', 'big_small', 'kill_group', 'double_group']:
            # 检查是否已经有该期号的预测
            existing_prediction = db_manager.get_prediction_by_qihao(next_qihao, pred_type)
            if existing_prediction:
                logger.info(f"{next_qihao}期的{pred_type}预测已存在，跳过")
                continue
                
            # 根据预测类型进行预测
            try:
                # 进行预测
                prediction_result = predictor.predict(pred_type, recent_records)
                if not prediction_result:
                    logger.error(f"{pred_type}预测失败")
                    continue
                    
                # 获取算法信息
                algo_used = predictor.get_current_algorithm(pred_type)
                    
                # 构建预测数据
                prediction_data = {
                    'qihao': next_qihao,
                    'prediction': prediction_result,
                    'prediction_type': pred_type,
                    'algorithm_used': str(algo_used),
                    'created_at': datetime.now().isoformat()
                }
                
                # 保存预测
                db_manager.save_prediction(prediction_data)
                logger.info(f"已自动保存{pred_type}预测: {next_qihao}期, 内容: {prediction_result}")
                
            except Exception as e:
                logger.error(f"自动运行{pred_type}预测失败: {e}")
                continue
        
        logger.info("自动运行所有类型的预测完成")
        return True
        
    except Exception as e:
        logger.error(f"自动运行所有预测失败: {e}")
        return False 