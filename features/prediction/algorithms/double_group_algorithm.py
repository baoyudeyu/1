"""
双组预测算法模块，专门处理双组预测逻辑
"""
import random
from loguru import logger
from features.prediction.utils.prediction_utils import generate_special_numbers, get_last_digit
import numpy as np
import json
from datetime import datetime

class DoubleGroupAlgorithm:
    """双组预测算法类，处理双组预测的相关逻辑"""
    
    # 记录上次推荐的组合，用于避免连续推荐相同组合
    last_recommended_combos = []
    # 记录上次推荐时间，用于判断是否需要重置记录
    last_recommendation_time = datetime.now()
    
    @staticmethod
    def predict_double_group(records, algo_num=1):
        """双组预测
        分析历史数据，预测下一期可能出现的双组合（大小+单双）并生成两个特码
        
        Args:
            records: 历史开奖记录
            algo_num: 算法变异系数，决定预测多样性
            
        Returns:
            str: 双组预测结果，格式为"大单/小双:[12,34]"
        """
        try:
            if not records or len(records) < 10:
                logger.warning("记录不足，无法进行双组预测")
                return "大单/小双:[01,15]"
            
            # 检查上次推荐时间，如果超过1小时，重置记录
            current_time = datetime.now()
            if (current_time - DoubleGroupAlgorithm.last_recommendation_time).total_seconds() > 3600:
                DoubleGroupAlgorithm.last_recommended_combos = []
                logger.info("重置双组推荐记录")
            
            # 更新推荐时间
            DoubleGroupAlgorithm.last_recommendation_time = current_time
                
            # 分析最近的记录，计算各种组合的概率
            recent_records = records[:30]  # 最近30期记录
            combo_counts = {
                '大单': 0,
                '大双': 0,
                '小单': 0,
                '小双': 0
            }
            
            # 统计各种组合的出现频率
            for record in recent_records:
                try:
                    is_big = bool(record[5])
                    is_odd = bool(record[6])
                    
                    if is_big and is_odd:
                        combo_counts['大单'] += 1
                    elif is_big and not is_odd:
                        combo_counts['大双'] += 1
                    elif not is_big and is_odd:
                        combo_counts['小单'] += 1
                    else:
                        combo_counts['小双'] += 1
                except (IndexError, TypeError) as e:
                    logger.error(f"处理记录失败: {e}")
                    continue
            
            # 计算各组合的概率
            total_count = sum(combo_counts.values())
            if total_count == 0:
                # 默认平均分布
                for combo in combo_counts:
                    combo_counts[combo] = 0.25
            else:
                for combo in combo_counts:
                    combo_counts[combo] = combo_counts[combo] / total_count
            
            # 分析最近5期的结果，降低连续出现组合的权重
            recent_5_records = records[:5]  # 最近5期
            recent_combos = []
            
            for record in recent_5_records:
                try:
                    is_big = bool(record[5])
                    is_odd = bool(record[6])
                    
                    if is_big and is_odd:
                        recent_combos.append('大单')
                    elif is_big and not is_odd:
                        recent_combos.append('大双')
                    elif not is_big and is_odd:
                        recent_combos.append('小单')
                    else:
                        recent_combos.append('小双')
                except (IndexError, TypeError):
                    continue
            
            # 调整权重 - 降低最近出现频繁的组合权重
            for combo in combo_counts:
                # 计算最近5期中该组合出现的次数
                recent_count = recent_combos.count(combo)
                # 如果最近出现频繁，降低权重
                if recent_count >= 2:
                    combo_counts[combo] *= (1 - 0.1 * recent_count)
                    logger.info(f"组合'{combo}'最近出现{recent_count}次，降低权重")
                
                # 如果最近10期未出现，增加权重
                if combo not in recent_combos and combo_counts[combo] < 0.3:
                    combo_counts[combo] *= 1.5
                    logger.info(f"组合'{combo}'最近未出现，增加权重")
            
            # 避免连续推荐相同组合
            if DoubleGroupAlgorithm.last_recommended_combos:
                for combo in DoubleGroupAlgorithm.last_recommended_combos:
                    if combo in combo_counts:
                        combo_counts[combo] *= 0.7
                        logger.info(f"组合'{combo}'上次已推荐，降低权重")
            
            # 根据算法变异系数增加随机性
            if algo_num >= 2:
                # 增加随机因子
                for combo in combo_counts:
                    random_factor = 0.8 + random.random() * 0.4  # 0.8-1.2的随机因子
                    combo_counts[combo] *= random_factor
            
            # 根据概率选择组合
            sorted_combos = sorted(combo_counts.items(), key=lambda x: x[1], reverse=True)
            logger.info(f"组合概率排序: {sorted_combos}")
            
            # 选择组合策略
            selected_combos = []
            
            # 基础策略：选择概率最高的两个组合
            if algo_num == 1 or random.random() < 0.4:
                selected_combos = [sorted_combos[0][0], sorted_combos[1][0]]
                logger.info("使用基础策略：选择概率最高的两个组合")
            
            # 平衡策略：选择一个高概率和一个低概率组合
            elif algo_num == 2 or random.random() < 0.3:
                selected_combos = [sorted_combos[0][0], sorted_combos[-1][0]]
                logger.info("使用平衡策略：选择一个高概率和一个低概率组合")
            
            # 反向策略：选择概率较低的两个组合
            elif algo_num == 3 or random.random() < 0.2:
                selected_combos = [sorted_combos[-1][0], sorted_combos[-2][0]]
                logger.info("使用反向策略：选择概率较低的两个组合")
            
            # 随机策略：完全随机选择两个不同的组合
            else:
                all_combos = list(combo_counts.keys())
                random.shuffle(all_combos)
                selected_combos = all_combos[:2]
                logger.info("使用随机策略：随机选择两个组合")
            
            # 确保选择的两个组合不同
            if selected_combos[0] == selected_combos[1] and len(combo_counts) > 1:
                other_combos = [c for c in combo_counts.keys() if c != selected_combos[0]]
                selected_combos[1] = random.choice(other_combos)
            
            # 记录本次推荐的组合
            DoubleGroupAlgorithm.last_recommended_combos = selected_combos.copy()
            
            # 构建预测结果
            combos_str = "/".join(selected_combos)
            
            # 定义每种组合的数字范围
            combo_ranges = {
                '大单': {'min': 15, 'max': 27, 'odd': True},   # 大单：>=15且为奇数
                '大双': {'min': 14, 'max': 26, 'odd': False},  # 大双：>=14且为偶数
                '小单': {'min': 1, 'max': 13, 'odd': True},    # 小单：<14且为奇数
                '小双': {'min': 0, 'max': 12, 'odd': False}    # 小双：<14且为偶数
            }
            
            # 获取历史数据中的热门和冷门数字
            number_frequency = {}
            recent_numbers = set()  # 记录最近几期出现的数字
            
            # 初始化所有数字的出现次数为0
            for num in range(28):  # 确保初始化0-27的所有数字
                number_frequency[num] = 0
                
            # 分析历史数据中的数字出现频率
            for idx, record in enumerate(recent_records[:30]):  # 最近30期
                try:
                    number = int(record[4])  # 获取和值
                    number_frequency[number] += 1
                    
                    # 标记最近5期出现的数字
                    if idx < 5:
                        recent_numbers.add(number)
                except Exception as e:
                    logger.error(f"获取历史数字频率失败: {e}")
                    continue
            
            # 查找冷门数字 (近期未出现且历史频率较低的数字)
            cold_numbers = []
            for num in range(28):
                if num not in recent_numbers and number_frequency[num] <= 2:
                    cold_numbers.append(num)
            
            # 为每个选定的组合生成一个特码
            special_numbers = []
            used_ranges = []  # 记录已使用的数字范围
            
            # 优化：确保两个组合的特码来自不同的数字区间，增加覆盖范围
            for combo in selected_combos:
                combo_range = combo_ranges.get(combo, {'min': 0, 'max': 27, 'odd': None})
                
                # 筛选符合范围的数字
                valid_numbers = []
                for num in range(combo_range['min'], combo_range['max'] + 1):
                    # 检查奇偶性
                    if combo_range['odd'] is not None:
                        if (num % 2 == 1) != combo_range['odd']:
                            continue
                    valid_numbers.append(num)
                
                if not valid_numbers:
                    # 如果没有有效数字，使用默认范围
                    valid_numbers = list(range(0, 28))
                
                # 根据历史频率给数字加权
                weighted_numbers = []
                for num in valid_numbers:
                    # 基础权重为1
                    weight = 1
                    
                    # 降低最近5期出现过的数字权重
                    if num in recent_numbers:
                        weight *= 0.5
                    
                    # 增加冷门数字权重
                    if num in cold_numbers:
                        weight *= 2
                        
                    # 如果在历史数据中出现过，调整权重
                    if num in number_frequency:
                        # 为频率较高的数字略微增加权重，但避免过度偏好
                        if number_frequency[num] > 3:
                            weight += 1
                        # 为冷门数字增加更多权重
                        elif number_frequency[num] <= 1:
                            weight += 2
                    
                    # 避免与之前选择的数字范围重叠，提高覆盖度
                    in_used_range = False
                    for used_range in used_ranges:
                        if used_range[0] <= num <= used_range[1]:
                            in_used_range = True
                            break
                    
                    if in_used_range:
                        weight *= 0.3  # 大幅降低已使用范围内数字的权重
                    
                    weighted_numbers.extend([num] * int(weight))
                
                # 随机选择一个数字，但有10%概率选择完全随机数字以增加覆盖范围
                if weighted_numbers and random.random() > 0.1:
                    selected_number = random.choice(weighted_numbers)
                else:
                    # 完全随机选择一个符合组合条件的数字
                    min_range = combo_range['min']
                    max_range = combo_range['max']
                    
                    if combo_range['odd'] is not None:
                        # 生成符合奇偶条件的随机数
                        valid_ranges = []
                        for num in range(min_range, max_range + 1):
                            if (num % 2 == 1) == combo_range['odd']:
                                valid_ranges.append(num)
                        
                        if valid_ranges:
                            selected_number = random.choice(valid_ranges)
                        else:
                            # 如果没有合适的范围，使用完全随机数
                            selected_number = random.randint(0, 27)
                    else:
                        # 直接生成范围内的随机数
                        selected_number = random.randint(min_range, max_range)
                
                # 额外的平衡机制：有20%的概率选择极端数字(0-3或24-27)以增加覆盖
                if random.random() < 0.2:
                    # 选择极值区域
                    extreme_ranges = [(0, 3), (24, 27)]
                    selected_range = random.choice(extreme_ranges)
                    
                    # 生成符合奇偶条件的随机数
                    valid_extremes = []
                    for num in range(selected_range[0], selected_range[1] + 1):
                        if combo_range['odd'] is None or (num % 2 == 1) == combo_range['odd']:
                            valid_extremes.append(num)
                    
                    if valid_extremes:
                        selected_number = random.choice(valid_extremes)
                
                # 确保数字在0-27范围内
                selected_number = min(27, max(0, selected_number))
                special_numbers.append(selected_number)
                
                # 记录已使用的数字范围(前后5个数字)
                range_min = max(0, selected_number - 5)
                range_max = min(27, selected_number + 5)
                used_ranges.append((range_min, range_max))
            
            # 如果生成的特码数量少于2，添加随机特码
            while len(special_numbers) < 2:
                # 优先选择冷门数字
                if cold_numbers:
                    new_num = random.choice(cold_numbers)
                    cold_numbers.remove(new_num)  # 避免重复选择同一个冷门数字
                else:
                    # 如果没有合适的冷门数字，随机生成
                    new_num = random.randint(0, 27)
                
                # 避免重复
                if new_num not in special_numbers:
                    special_numbers.append(new_num)
            
            # 如果有超过两个特码，只保留两个
            if len(special_numbers) > 2:
                special_numbers = special_numbers[:2]
            
            # 排序特码
            special_numbers.sort()
            
            # 格式化特码字符串
            numbers_str = ",".join([f"{num:02d}" for num in special_numbers])
            
            # 构建最终预测结果
            prediction = f"{combos_str}:[{numbers_str}]"
            
            logger.info(f"双组预测成功: {prediction}")
            return prediction
            
        except Exception as e:
            logger.error(f"双组预测失败: {e}")
            return "小单/小双:[01,15]"  # 默认值也改为小单/小双，避免总是大单/大双