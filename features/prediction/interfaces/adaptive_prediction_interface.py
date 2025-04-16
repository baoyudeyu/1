"""
自适应预测接口实现，连接强化学习模型和预测接口
"""
import json
from typing import Dict, Any, Tuple, List, Optional
from loguru import logger

from features.prediction.interfaces.prediction_interface import (
    PredictionInterface, 
    PredictionData, 
    PredictionResult
)
from features.prediction.algorithms.base_algorithms import BaseAlgorithms
from features.prediction.algorithms.double_group_algorithm import DoubleGroupAlgorithm
from features.prediction.ml_models.reinforcement_learner import ReinforcementLearner
from features.prediction.utils.prediction_utils import PredictionJudge
from features.data.db_manager import db_manager

class AdaptivePredictionInterface(PredictionInterface):
    """自适应预测接口实现，使用强化学习模型优化预测"""
    
    def __init__(self):
        """初始化"""
        # 当前使用的算法
        self.current_algorithms = {
            'single_double': 1,
            'big_small': 1,
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
        
        # 预测判断器
        self.prediction_judge = PredictionJudge()
        
        logger.info("自适应预测接口初始化完成")
    
    def predict(self, 
               data: PredictionData, 
               prediction_type: str, 
               **kwargs) -> Optional[PredictionResult]:
        """进行预测
        
        Args:
            data: 预测数据
            prediction_type: 预测类型
            **kwargs: 其他参数
            
        Returns:
            预测结果
        """
        try:
            # 获取参数
            big_boundary = kwargs.get('big_boundary', 14)
            
            # 获取元数据
            metadata = data.get_metadata()
            next_qihao = metadata.get('next_qihao')
            
            if not next_qihao:
                logger.error("无法获取下一期号")
                return None
                
            # 检查缓存
            cached_prediction = db_manager.get_cached_prediction(next_qihao, prediction_type)
            if cached_prediction:
                logger.info(f"使用缓存的预测结果: {prediction_type} {next_qihao}")
                
                # 构建返回数据
                if isinstance(cached_prediction, dict):
                    return PredictionResult(
                        qihao=next_qihao,
                        prediction=cached_prediction['prediction'],
                        prediction_type=prediction_type,
                        algorithm_used=cached_prediction['algorithm_used'],
                        confidence_score=0.5,
                        switch_info=None  # 使用缓存时没有切换信息
                    )
                else:  # 如果是元组
                    return PredictionResult(
                        qihao=next_qihao,
                        prediction=cached_prediction[2],  # 假设prediction在索引2
                        prediction_type=prediction_type,
                        algorithm_used=cached_prediction[4],  # 假设algorithm_used在索引4
                        confidence_score=0.5,
                        switch_info=None  # 使用缓存时没有切换信息
                    )
            
            # 提取当前状态特征
            raw_records = data.get_raw_records()
            current_state = self.rl_models[prediction_type].get_state_features(raw_records)
            
            # 使用强化学习选择算法
            selected_algo = self.rl_models[prediction_type].select_algorithm(current_state)
            
            # 记录算法切换信息
            switch_info = None
            if selected_algo != self.current_algorithms.get(prediction_type, 1):
                switch_info = {
                    'from': self.current_algorithms.get(prediction_type, 1),
                    'to': selected_algo,
                    'reason': '强化学习算法自适应切换'
                }
                logger.info(f"算法切换: {prediction_type} 从算法{switch_info['from']}切换到算法{switch_info['to']}")
                
                # 更新当前算法
                self.current_algorithms[prediction_type] = selected_algo
            
            # 获取值
            values = data.get_values()
            
            # 根据预测类型和选择的算法进行预测
            prediction_content = None
            if prediction_type == 'single_double':
                prediction_content = BaseAlgorithms.predict_single_double(values, selected_algo, big_boundary)
            elif prediction_type == 'big_small':
                prediction_content = BaseAlgorithms.predict_big_small(values, selected_algo, big_boundary)
            elif prediction_type == 'kill_group':
                # 为杀组预测添加原始记录
                values['_raw_records_'] = raw_records
                prediction_content = BaseAlgorithms.predict_kill_group(values, selected_algo, big_boundary)
            elif prediction_type == 'double_group':
                prediction_content = DoubleGroupAlgorithm.predict_double_group(raw_records, selected_algo)
            
            if not prediction_content:
                logger.error(f"预测失败: {prediction_type}")
                return None
            
            # 记录本次预测使用的状态和算法
            self.last_predictions[prediction_type] = {
                'state': current_state,
                'algo': selected_algo,
                'qihao': next_qihao
            }
            
            # 计算置信度
            confidence_score = 0.5  # 默认值
            try:
                # 从强化学习模型中获取当前状态的Q值
                if current_state in self.rl_models[prediction_type].q_table:
                    q_values = self.rl_models[prediction_type].q_table[current_state]
                    if selected_algo in q_values:
                        confidence_score = min(0.95, max(0.05, q_values[selected_algo]))
            except Exception as e:
                logger.warning(f"计算置信度失败: {e}")
            
            # 构建预测结果
            prediction_result = PredictionResult(
                qihao=next_qihao,
                prediction=prediction_content,
                prediction_type=prediction_type,
                algorithm_used=json.dumps({prediction_type: selected_algo}),
                confidence_score=confidence_score,
                switch_info=switch_info
            )
            
            # 缓存预测结果
            db_manager.save_prediction_cache({
                'qihao': next_qihao,
                'prediction_type': prediction_type,
                'prediction': prediction_content,
                'algorithm_used': json.dumps({prediction_type: selected_algo})
            })
            
            logger.info(f"预测完成: {prediction_type} {next_qihao} 使用算法{selected_algo}")
            return prediction_result
            
        except Exception as e:
            logger.error(f"自适应预测失败: {e}")
            return None
    
    def verify_prediction(self, 
                         prediction: PredictionResult, 
                         actual_data: Dict[str, Any]) -> Tuple[bool, float]:
        """验证预测
        
        Args:
            prediction: 预测结果
            actual_data: 实际结果数据
            
        Returns:
            (是否正确, 置信度)
        """
        try:
            # 判断预测是否正确
            is_correct = self.prediction_judge.check_prediction_correctness(
                prediction.prediction_type,
                prediction.prediction,
                actual_data
            )
            
            return is_correct, prediction.confidence_score
            
        except Exception as e:
            logger.error(f"验证预测失败: {e}")
            return False, 0.0
    
    def update_model(self, 
                    prediction: PredictionResult, 
                    is_correct: bool, 
                    actual_data: Dict[str, Any]) -> None:
        """更新模型
        
        Args:
            prediction: 预测结果
            is_correct: 是否正确
            actual_data: 实际结果数据
        """
        try:
            pred_type = prediction.prediction_type
            qihao = prediction.qihao
            
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
            reward = self.rl_models[pred_type].calculate_reward(is_correct, prediction.confidence_score)
            
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
    
    def get_model_status(self) -> Dict[str, Any]:
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