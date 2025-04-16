"""
预测管理器模块，负责协调各种预测算法和切换逻辑
"""
import random
from datetime import datetime
from loguru import logger
from features.prediction.algorithms.algorithm_switcher import AlgorithmSwitcher
from features.prediction.algorithms.base_algorithms import BaseAlgorithms
from features.prediction.algorithms.double_group_algorithm import DoubleGroupAlgorithm
from features.prediction.utils.prediction_utils import calculate_confidence_score, prepare_test_values

class PredictionManager:
    """预测管理器类，负责协调各种预测算法和切换逻辑"""
    
    def __init__(self):
        # 初始化算法切换器
        self.algorithm_switcher = AlgorithmSwitcher()
        
        # 当前使用的算法编号
        self.current_algorithms = {
            'single_double': 1,  # 单双预测当前算法
            'big_small': 1,      # 大小预测固定使用算法1，不切换
            'kill_group': 1,     # 杀组预测当前算法
            'double_group': 1    # 双组预测当前算法
        }
        
        # 算法性能统计
        self.algorithm_performance = {
            'single_double': {
                1: self._init_performance_stats(),
                2: self._init_performance_stats(),
                3: self._init_performance_stats()
            },
            'big_small': {
                1: self._init_performance_stats(),
                2: self._init_performance_stats(),
                3: self._init_performance_stats()
            },
            'kill_group': {
                1: self._init_performance_stats(),
                2: self._init_performance_stats(),
                3: self._init_performance_stats()
            },
            'double_group': {
                1: self._init_performance_stats(),
                2: self._init_performance_stats(),
                3: self._init_performance_stats()
            }
        }
        
        # 预测历史记录
        self.prediction_history = {
            'single_double': [],
            'big_small': [],
            'kill_group': [],
            'double_group': []
        }
        
        # 算法切换历史
        self.switch_history = {
            'single_double': [],
            'big_small': [],
            'kill_group': [],
            'double_group': []
        }
    
    def _init_performance_stats(self):
        """初始化性能统计数据"""
        return {
            'total_predictions': 0,
            'correct_predictions': 0,
            'success_rate': 0.5,  # 初始成功率设为0.5
            'recent_results': [],  # 最近的预测结果 (1=正确, 0=错误)
            'recent_success_rate': 0.5,  # 最近的成功率
            'confidence_score': 0.5,  # 置信度分数
            'consecutive_correct': 0,  # 连续正确次数
            'consecutive_wrong': 0,  # 连续错误次数
            'last_switch_time': 0  # 上次切换时间
        }
    
    def make_prediction(self, pred_type, records, big_boundary=14):
        """进行预测
        
        Args:
            pred_type: 预测类型 ('single_double', 'big_small', 'kill_group', 'double_group')
            records: 历史开奖记录
            big_boundary: 大小界限
            
        Returns:
            预测结果
        """
        # 获取当前算法
        current_algo = self.current_algorithms.get(pred_type, 1)
        
        # 对于大小预测，强制使用算法1
        if pred_type == 'big_small':
            current_algo = 1
            self.current_algorithms[pred_type] = 1
        
        # 准备测试数据
        values = prepare_test_values(records)
        if not values and pred_type != 'double_group':
            logger.error(f"无法准备测试数据: {pred_type}")
            return None
        
        # 根据预测类型进行预测
        if pred_type == 'single_double':
            result = BaseAlgorithms.predict_single_double(values, current_algo, big_boundary)
        elif pred_type == 'big_small':
            result = BaseAlgorithms.predict_big_small(values, current_algo, big_boundary)
        elif pred_type == 'kill_group':
            # 为杀组预测添加原始记录
            # 确保提供足够的历史数据进行分析
            if len(records) < 50:
                # 如果传入的记录不足50条，尝试从数据库获取更多记录
                from ..data.db_manager import db_manager
                try:
                    more_records = db_manager.get_recent_records(100)  # 获取最近100条记录
                    if len(more_records) > len(records):
                        logger.info(f"为杀组预测获取更多历史数据: {len(more_records)} 条记录")
                        records = more_records
                except Exception as e:
                    logger.error(f"获取更多历史数据失败: {e}")
            
            values['_raw_records_'] = records
            result = BaseAlgorithms.predict_kill_group(values, current_algo, big_boundary)
        elif pred_type == 'double_group':
            result = DoubleGroupAlgorithm.predict_double_group(records, current_algo)
        
        # 记录预测历史
        prediction_record = {
            'time': datetime.now(),
            'algorithm': current_algo,
            'result': result,
            'verified': False,
            'correct': None
        }
        self.prediction_history[pred_type].append(prediction_record)
        
        # 只保留最近100条预测历史
        if len(self.prediction_history[pred_type]) > 100:
            self.prediction_history[pred_type].pop(0)
        
        return result
    
    def verify_prediction(self, pred_type, prediction_result, actual_result):
        """验证预测结果
        
        Args:
            pred_type: 预测类型
            prediction_result: 预测结果
            actual_result: 实际结果
            
        Returns:
            是否预测正确
        """
        # 查找最近的未验证预测
        for pred in reversed(self.prediction_history[pred_type]):
            if not pred['verified']:
                # 验证预测结果
                is_correct = self._check_prediction_correctness(
                    pred_type, pred['result'], actual_result
                )
                
                # 更新预测记录
                pred['verified'] = True
                pred['correct'] = is_correct
                pred['actual_result'] = actual_result
                
                # 更新算法性能统计
                self._update_algorithm_performance(
                    pred_type, pred['algorithm'], is_correct
                )
                
                return is_correct
        
        logger.warning(f"没有找到未验证的{pred_type}预测")
        return False
    
    def _check_prediction_correctness(self, pred_type, prediction, actual):
        """检查预测是否正确"""
        try:
            if pred_type == 'single_double':
                # 单双预测格式: "单12" 或 "双08"
                pred_type = prediction[0]  # '单' 或 '双'
                actual_num = int(actual)
                return (pred_type == '单' and actual_num % 2 == 1) or (pred_type == '双' and actual_num % 2 == 0)
                
            elif pred_type == 'big_small':
                # 大小预测格式: "大15" 或 "小09"
                pred_type = prediction[0]  # '大' 或 '小'
                actual_num = int(actual)
                return (pred_type == '大' and actual_num >= 14) or (pred_type == '小' and actual_num < 14)
                
            elif pred_type == 'kill_group':
                # 杀组预测格式: "杀大单" 或 "杀小双"
                kill_type = prediction[1:]  # '大单', '大双', '小单', '小双'
                actual_num = int(actual)
                actual_type = ('大' if actual_num >= 14 else '小') + ('单' if actual_num % 2 == 1 else '双')
                return kill_type != actual_type
                
            elif pred_type == 'double_group':
                # 双组预测格式: "大单/小双:[12,34]"
                try:
                    # 解析预测结果
                    if ":[" in prediction:
                        combo_part, numbers_part = prediction.split(':[')
                        combos = combo_part.split('/')
                        numbers = numbers_part.rstrip(']').split(',')
                        # 清理数字格式
                        numbers = [n.strip().strip('`').strip() for n in numbers]
                    else:
                        combos = prediction.split('/')
                        numbers = []
                    
                    # 解析实际结果
                    actual_num = int(actual)
                    actual_type = ('大' if actual_num >= 14 else '小') + ('单' if actual_num % 2 == 1 else '双')
                    
                    # 检查组合是否匹配
                    combo_correct = actual_type in combos
                    
                    # 检查特码是否匹配
                    number_correct = str(actual_num).zfill(2) in numbers or str(actual_num) in numbers
                    
                    # 只要有一个匹配就算正确
                    return combo_correct or number_correct
                except Exception as e:
                    logger.error(f"验证双组预测结果失败: {e}, 预测: {prediction}, 实际: {actual}")
                    return False
                
            else:
                logger.error(f"未知的预测类型: {pred_type}")
                return False
                
        except Exception as e:
            logger.error(f"验证预测结果失败: {e}, 预测: {prediction}, 实际: {actual}")
            return False
    
    def _update_algorithm_performance(self, pred_type, algo_num, is_correct):
        """更新算法性能统计"""
        perf = self.algorithm_performance[pred_type][algo_num]
        
        # 更新总体统计
        perf['total_predictions'] += 1
        if is_correct:
            perf['correct_predictions'] += 1
            perf['consecutive_correct'] += 1
            perf['consecutive_wrong'] = 0
        else:
            perf['consecutive_correct'] = 0
            perf['consecutive_wrong'] += 1
        
        # 更新成功率
        perf['success_rate'] = perf['correct_predictions'] / perf['total_predictions']
        
        # 更新最近结果
        perf['recent_results'].append(1 if is_correct else 0)
        if len(perf['recent_results']) > self.algorithm_switcher.switch_config['max_recent_results']:
            perf['recent_results'].pop(0)
        
        # 更新最近成功率
        if perf['recent_results']:
            perf['recent_success_rate'] = sum(perf['recent_results']) / len(perf['recent_results'])
        
        # 更新置信度分数
        perf['confidence_score'] = calculate_confidence_score(
            perf['success_rate'], 
            perf['recent_success_rate'],
            perf['consecutive_correct'],
            perf['consecutive_wrong'],
            perf['total_predictions']
        )
        
        # 更新算法趋势
        performance_value = perf['confidence_score']
        self.algorithm_switcher.update_algorithm_trends(pred_type, algo_num, performance_value)
        
        # 更新动态权重
        success_info = {
            'confidence_accurate': random.random() < perf['confidence_score'],
            'recent_accurate': random.random() < perf['recent_success_rate'],
            'overall_accurate': random.random() < perf['success_rate']
        }
        self.algorithm_switcher.update_dynamic_weights(pred_type, success_info)
        
        logger.debug(f"{pred_type}算法{algo_num}号性能更新: 成功率={perf['success_rate']:.2f}, 置信度={perf['confidence_score']:.2f}")
    
    def get_performance_summary(self):
        """获取性能统计摘要"""
        summary = {}
        
        for pred_type in ['single_double', 'big_small', 'kill_group', 'double_group']:
            current_algo = self.current_algorithms[pred_type]
            perf = self.algorithm_performance[pred_type][current_algo]
            
            summary[pred_type] = {
                'current_algorithm': current_algo,
                'total_predictions': perf['total_predictions'],
                'success_rate': perf['success_rate'],
                'recent_success_rate': perf['recent_success_rate'],
                'confidence_score': perf['confidence_score'],
                'consecutive_correct': perf['consecutive_correct'],
                'consecutive_wrong': perf['consecutive_wrong']
            }
            
            # 添加算法切换历史摘要
            if self.switch_history[pred_type]:
                last_switch = self.switch_history[pred_type][-1]
                summary[pred_type]['last_switch'] = {
                    'time': last_switch['time'],
                    'from_algo': last_switch['from_algo'],
                    'to_algo': last_switch['to_algo'],
                    'reason': last_switch['reason']
                }
        
        return summary 