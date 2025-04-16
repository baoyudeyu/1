"""
自适应预测器模型，结合强化学习实现算法自适应优化
"""
import json
from datetime import datetime
from loguru import logger

from features.prediction.utils.prediction_utils import prepare_test_values
from features.prediction.algorithms.base_algorithms import BaseAlgorithms
from features.prediction.algorithms.double_group_algorithm import DoubleGroupAlgorithm
from features.prediction.ml_models.reinforcement_learner import ReinforcementLearner
from features.data.db_manager import db_manager

class AdaptivePredictor:
    """自适应预测器模型，结合强化学习优化预测算法"""
    
    def __init__(self):
        """初始化自适应预测器"""
        # 当前使用的算法
        self.current_algorithms = {
            'single_double': 1,
            'big_small': 1,  # 大小预测固定使用算法1，不进行切换
            'kill_group': 1,
            'double_group': 1
        }
        
        # 初始化强化学习模型
        self.rl_models = {
            'single_double': ReinforcementLearner('single_double'),
            'big_small': ReinforcementLearner('big_small'),
            'kill_group': ReinforcementLearner('kill_group'),
            'double_group': ReinforcementLearner('double_group')
        }
        
        # 记录最近预测使用的状态和算法
        self.last_predictions = {
            'single_double': {'state': None, 'algo': None, 'qihao': None},
            'big_small': {'state': None, 'algo': None, 'qihao': None},
            'kill_group': {'state': None, 'algo': None, 'qihao': None},
            'double_group': {'state': None, 'algo': None, 'qihao': None}
        }
        
        # 记录每种预测类型的性能
        self.performance_metrics = {
            'single_double': {'success_count': 0, 'total_count': 0},
            'big_small': {'success_count': 0, 'total_count': 0},
            'kill_group': {'success_count': 0, 'total_count': 0},
            'double_group': {'success_count': 0, 'total_count': 0}
        }
        
        logger.info("自适应预测器初始化完成")
    
    def predict(self, pred_type, records, big_boundary=14):
        """进行预测
        
        Args:
            pred_type: 预测类型
            records: 历史记录
            big_boundary: 大小界限
            
        Returns:
            预测结果字典
        """
        try:
            # 获取最新期号和下一期号
            latest_qihao = records[0][1]
            next_qihao = str(int(latest_qihao) + 1)
            
            # 检查缓存
            cached_prediction = db_manager.get_cached_prediction(next_qihao, pred_type)
            if cached_prediction:
                logger.info(f"使用缓存的预测结果: {pred_type} {next_qihao}")
                
                # 构建返回数据
                if isinstance(cached_prediction, dict):
                    return {
                        'qihao': next_qihao,
                        'prediction': cached_prediction['prediction'],
                        'prediction_type': pred_type,
                        'algorithm_used': cached_prediction['algorithm_used'],
                        'switch_info': None  # 使用缓存时没有切换信息
                    }
                else:  # 如果是元组
                    return {
                        'qihao': next_qihao,
                        'prediction': cached_prediction[2],  # 假设prediction在索引2
                        'prediction_type': pred_type,
                        'algorithm_used': cached_prediction[4],  # 假设algorithm_used在索引4
                        'switch_info': None  # 使用缓存时没有切换信息
                    }
            
            # 提取当前状态特征
            current_state = self.rl_models[pred_type].get_state_features(records)
            
            # 使用强化学习选择算法，但对于大小预测固定使用算法1
            if pred_type == 'big_small':
                selected_algo = 1
                # 确保当前算法也是1
                self.current_algorithms[pred_type] = 1
            else:
                # 对其他预测类型使用强化学习
                selected_algo = self.rl_models[pred_type].select_algorithm(current_state)
            
            # 记录算法切换信息
            switch_info = None
            if pred_type != 'big_small' and selected_algo != self.current_algorithms.get(pred_type, 1):
                switch_info = {
                    'from': self.current_algorithms.get(pred_type, 1),
                    'to': selected_algo,
                    'reason': '强化学习算法自适应切换'
                }
                logger.info(f"算法切换: {pred_type} 从算法{switch_info['from']}切换到算法{switch_info['to']}")
                
                # 更新当前算法
                self.current_algorithms[pred_type] = selected_algo
            
            # 准备预测数据
            values = prepare_test_values(records)
            if not values and pred_type != 'double_group':
                logger.error(f"无法准备测试数据: {pred_type}")
                return None
            
            # 根据预测类型和选择的算法进行预测
            if pred_type == 'single_double':
                prediction_content = BaseAlgorithms.predict_single_double(values, selected_algo, big_boundary)
            elif pred_type == 'big_small':
                prediction_content = BaseAlgorithms.predict_big_small(values, selected_algo, big_boundary)
            elif pred_type == 'kill_group':
                # 为杀组预测添加原始记录
                values['_raw_records_'] = records
                prediction_content = BaseAlgorithms.predict_kill_group(values, selected_algo, big_boundary)
            elif pred_type == 'double_group':
                prediction_content = DoubleGroupAlgorithm.predict_double_group(records, selected_algo)
            else:
                logger.error(f"不支持的预测类型: {pred_type}")
                return None
            
            # 记录本次预测使用的状态和算法
            self.last_predictions[pred_type] = {
                'state': current_state,
                'algo': selected_algo,
                'qihao': next_qihao
            }
            
            # 构建预测结果
            prediction_result = {
                'qihao': next_qihao,
                'prediction': prediction_content,
                'prediction_type': pred_type,
                'algorithm_used': json.dumps({pred_type: selected_algo}),
                'switch_info': switch_info
            }
            
            # 缓存预测结果
            db_manager.save_prediction_cache({
                'qihao': next_qihao,
                'prediction_type': pred_type,
                'prediction': prediction_content,
                'algorithm_used': json.dumps({pred_type: selected_algo})
            })
            
            logger.info(f"预测完成: {pred_type} {next_qihao} 使用算法{selected_algo}")
            return prediction_result
            
        except Exception as e:
            logger.error(f"自适应预测失败: {e}")
            return None
    
    def update_model(self, pred_type, qihao, is_correct, actual_data):
        """更新模型
        
        Args:
            pred_type: 预测类型
            qihao: 期号
            is_correct: 是否正确
            actual_data: 实际结果数据
        """
        try:
            # 更新性能指标
            if pred_type in self.performance_metrics:
                self.performance_metrics[pred_type]['total_count'] += 1
                if is_correct:
                    self.performance_metrics[pred_type]['success_count'] += 1
            
            # 获取上次预测信息
            last_pred = self.last_predictions.get(pred_type)
            if not last_pred or last_pred['qihao'] != qihao:
                logger.warning(f"找不到匹配的预测记录: {pred_type} {qihao}")
                return
                
            # 获取当前状态特征
            current_state = self.rl_models[pred_type].get_state_features([actual_data])
            
            # 计算奖励
            confidence_score = 0.5  # 默认置信度
            reward = self.rl_models[pred_type].calculate_reward(is_correct, confidence_score)
            
            # 更新Q值
            self.rl_models[pred_type].update_q_values(
                last_pred['state'],
                last_pred['algo'],
                reward,
                current_state
            )
            
            # 计算成功率
            metrics = self.performance_metrics[pred_type]
            success_rate = metrics['success_count'] / metrics['total_count'] if metrics['total_count'] > 0 else 0.5
            
            # 自适应调整学习参数
            self.rl_models[pred_type].adapt_parameters(success_rate, metrics['total_count'])
            
            logger.info(f"模型更新完成: {pred_type} {qihao} 正确:{is_correct} 奖励:{reward:.2f}")
            
        except Exception as e:
            logger.error(f"更新模型失败: {e}")
    
    def get_model_status(self):
        """获取模型状态
        
        Returns:
            模型状态信息
        """
        status = {}
        
        for pred_type in ['single_double', 'big_small', 'kill_group', 'double_group']:
            metrics = self.performance_metrics[pred_type]
            success_rate = metrics['success_count'] / metrics['total_count'] if metrics['total_count'] > 0 else 0
            
            status[pred_type] = {
                'current_algorithm': self.current_algorithms.get(pred_type, 1),
                'success_rate': success_rate,
                'prediction_count': metrics['total_count'],
                'learning_rate': self.rl_models[pred_type].learning_rate,
                'exploration_rate': self.rl_models[pred_type].exploration_rate
            }
        
        return status 