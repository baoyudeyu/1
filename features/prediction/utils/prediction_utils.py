"""
预测工具函数模块，提供预测所需的辅助函数
"""
import random
from loguru import logger

def get_last_digit(number):
    """获取数字的最后一位（个位数）"""
    return abs(int(number)) % 10

def calculate_confidence_score(perf):
    """计算置信度分数
    
    Args:
        perf: 算法性能数据字典
        
    Returns:
        置信度分数 (0-1之间)
    """
    # 基础置信度 = 总体成功率和最近成功率的加权平均
    base_confidence = perf['success_rate'] * 0.4 + perf['recent_success_rate'] * 0.6
    
    # 连续正确奖励
    correct_bonus = min(perf['consecutive_correct'] * 0.05, 0.2)
    
    # 连续错误惩罚
    wrong_penalty = min(perf['consecutive_wrong'] * 0.1, 0.3)
    
    # 经验因子 (预测次数越多，置信度越高)
    experience_factor = min(perf['total_predictions'] / 50, 1) * 0.1
    
    # 计算最终置信度
    confidence = base_confidence + correct_bonus - wrong_penalty + experience_factor
    
    # 确保置信度在0-1之间
    return max(0.1, min(0.95, confidence))

def extract_values_from_records(records):
    """从历史记录中提取预测所需的值
    
    Args:
        records: 历史开奖记录
        
    Returns:
        包含预测所需值的字典
    """
    values = {}
    
    try:
        # 确保有足够的记录
        if len(records) < 10:
            logger.warning("历史记录不足，无法提取完整的预测值")
            return values
            
        # 提取最近10期的A、B、C值
        for i in range(min(10, len(records))):
            record = records[i]
            
            # 提取A、B、C值
            try:
                a_val = int(record[3])
                b_val = int(record[4])
                c_val = int(record[5])
                
                # 存储值
                values[f'A{i+1}'] = a_val
                values[f'B{i+1}'] = b_val
                values[f'C{i+1}'] = c_val
            except (IndexError, ValueError, TypeError) as e:
                logger.error(f"提取A、B、C值失败: {e}, record: {record}")
                # 使用随机值代替
                values[f'A{i+1}'] = random.randint(0, 9)
                values[f'B{i+1}'] = random.randint(0, 9)
                values[f'C{i+1}'] = random.randint(0, 9)
    
    except Exception as e:
        logger.error(f"提取预测值失败: {e}")
        
    return values

def prepare_test_values(records):
    """准备测试数据，从历史记录中提取预测所需的值
    
    Args:
        records: 历史开奖记录
        
    Returns:
        包含预测所需值的字典
    """
    values = {}
    
    try:
        # 确保有足够的记录
        if len(records) < 10:
            logger.warning("历史记录不足，无法提取完整的预测值")
            return values
            
        # 提取最近10期的A、B、C值
        for i in range(min(10, len(records))):
            record = records[i]
            
            # 提取A、B、C值
            try:
                # 获取开奖号码字段 (格式如 "0+6+9")
                opennum = record[3]  # 假设开奖号码在索引3
                
                # 分割开奖号码
                if '+' in opennum:
                    abc_values = opennum.split('+')
                    if len(abc_values) == 3:
                        a_val = int(abc_values[0])
                        b_val = int(abc_values[1])
                        c_val = int(abc_values[2])
                    else:
                        raise ValueError(f"开奖号码格式错误: {opennum}")
                else:
                    # 如果没有+分隔符，尝试按位置解析
                    if len(opennum) == 3:
                        a_val = int(opennum[0])
                        b_val = int(opennum[1])
                        c_val = int(opennum[2])
                    else:
                        raise ValueError(f"开奖号码格式错误: {opennum}")
                
                # 存储值
                values[f'A{i+1}'] = a_val
                values[f'B{i+1}'] = b_val
                values[f'C{i+1}'] = c_val
            except (IndexError, ValueError, TypeError) as e:
                logger.error(f"提取A、B、C值失败: {e}, record: {record}")
                # 使用随机值代替
                values[f'A{i+1}'] = random.randint(0, 9)
                values[f'B{i+1}'] = random.randint(0, 9)
                values[f'C{i+1}'] = random.randint(0, 9)
    
    except Exception as e:
        logger.error(f"提取预测值失败: {e}")
        
    return values

def generate_special_numbers(selected_combos):
    """根据选定的组合生成特码
    
    Args:
        selected_combos: 选定的组合列表 ['大单', '小双'] 等
        
    Returns:
        特码字符串
    """
    all_special_numbers = []
    
    for combo in selected_combos:
        # 解析组合
        is_big = '大' in combo
        is_odd = '单' in combo
        
        # 为每个组合生成2个符合条件的数字
        combo_numbers = []
        attempts = 0
        
        while len(combo_numbers) < 2 and attempts < 20:
            # 生成0-27之间的随机数
            if is_big:
                # 大: 14-27
                num = random.randint(14, 27)
            else:
                # 小: 0-13
                num = random.randint(0, 13)
                
            # 确保符合单双条件
            if (num % 2 == 1) != is_odd:
                # 如果不符合单双条件，尝试减1或加1来调整
                if is_odd:
                    # 需要是单数
                    if num > 0 and num % 2 == 0:
                        num -= 1  # 优先减1而不是加1，减少溢出风险
                    else:
                        num += 1
                else:
                    # 需要是双数
                    if num > 0 and num % 2 == 1:
                        num -= 1  # 优先减1而不是加1，减少溢出风险
                    else:
                        num += 1
                    
                # 确保调整后的数字仍在大小范围内
                if is_big and num < 14:
                    num = 15 if is_odd else 14
                elif not is_big and num > 13:
                    num = 13 if is_odd else 12
            
            # 额外检查确保数字在0-27范围内
            num = min(27, max(0, num))
            
            # 转换为两位数字符串
            num_str = f"{num:02d}"
            
            # 避免重复
            if num_str not in combo_numbers and num_str not in all_special_numbers:
                combo_numbers.append(num_str)
                all_special_numbers.append(num_str)
                
            attempts += 1
    
    # 随机打乱顺序
    random.shuffle(all_special_numbers)
    
    # 确保生成的数字足够
    while len(all_special_numbers) < 2:
        # 随机生成一个数字 (0-27)
        num = random.randint(0, 27)
        num_str = f"{num:02d}"
        if num_str not in all_special_numbers:
            all_special_numbers.append(num_str)
    
    # 始终返回两个数字，格式为 "xx,yy"
    result = ','.join(all_special_numbers[:2])
    
    # 最后检查一次是否确实有两个数字
    if result.count(',') != 1 or len(result.split(',')) != 2:
        # 如果格式不正确，强制使用两个不同的随机数字
        num1 = random.randint(0, 27)
        num2 = random.randint(0, 27)
        while num2 == num1:
            num2 = random.randint(0, 27)
        result = f"{num1:02d},{num2:02d}"
    
    return result 

class PredictionJudge:
    """预测判断类，集中处理各类预测的正确性判断"""
    
    @staticmethod
    def check_prediction_correctness(pred_type, prediction, actual_data):
        """统一判断预测是否正确
        
        Args:
            pred_type: 预测类型
            prediction: 预测内容
            actual_data: 实际结果数据 (包含is_big,is_odd等字段)
            
        Returns:
            bool: 是否正确
        """
        try:
            is_big = actual_data.get('is_big', False)
            is_odd = actual_data.get('is_odd', False)
            actual_result = f"{'大' if is_big else '小'}{'单' if is_odd else '双'}"
            
            # 根据预测类型使用不同判断逻辑
            if pred_type == 'single_double':
                # 单双预测
                target_result = '单' if is_odd else '双'
                return ('单' in prediction and target_result == '单') or ('双' in prediction and target_result == '双')
                
            elif pred_type == 'big_small':
                # 大小预测
                target_result = '大' if is_big else '小'
                return ('大' in prediction and target_result == '大') or ('小' in prediction and target_result == '小')
                
            elif pred_type == 'kill_group':
                # 杀组预测 - 预测要杀掉的组合与实际结果不同才正确
                kill_combo = ""
                if "杀" in prediction:
                    kill_combo = prediction.replace("杀", "")
                return kill_combo != actual_result
                
            elif pred_type == 'double_group':
                # 双组预测
                if ':' in prediction:
                    pred_parts = prediction.split(':')[0].split('/')
                else:
                    pred_parts = prediction.split('/')
                return any(combo == actual_result for combo in pred_parts)
                
            # 未知预测类型
            return False
            
        except Exception as e:
            logger.error(f"判断预测正确性失败: {e}")
            return False
            
    @staticmethod
    def judge_batch_predictions(pred_type, predictions, results):
        """批量判断一组预测的正确性
        
        Args:
            pred_type: 预测类型
            predictions: 预测内容列表
            results: 实际结果数据列表
            
        Returns:
            list: 每个预测的正确性布尔值列表
        """
        if len(predictions) != len(results):
            logger.error("预测和结果数量不匹配")
            return []
            
        correctness = []
        for i in range(len(predictions)):
            is_correct = PredictionJudge.check_prediction_correctness(
                pred_type, 
                predictions[i], 
                results[i]
            )
            correctness.append(is_correct)
            
        return correctness 