"""
预测器模型，包含预测器的核心逻辑
"""
import json
from datetime import datetime
# IDE可能会错误标记此导入，但不影响程序运行
from loguru import logger  # type: ignore
from features.data.db_manager import db_manager
from features.config.config_manager import GAME_CONFIG
from features.prediction.utils.prediction_utils import prepare_test_values, calculate_confidence_score
from features.prediction.algorithms.base_algorithms import BaseAlgorithms
from features.prediction.algorithms.double_group_algorithm import DoubleGroupAlgorithm
from features.prediction.algorithms.algorithm_switcher import AlgorithmSwitcher

# 初始化数据库连接
# db = Database()  # 不再需要，使用 db_manager 替代

class PredictorModel:
    """预测器模型类，处理预测的核心逻辑"""
    
    def __init__(self):
        self.current_algorithms = {
            'single_double': 1,
            'big_small': 1,  # 大小预测固定使用算法1，不切换
            'kill_group': 1,
            'double_group': 1
        }
        
        # 算法性能追踪
        self.algorithm_performance = {
            'single_double': {},
            'big_small': {},
            'kill_group': {},
            'double_group': {}
        }
        
        # 为每个预测类型初始化算法性能数据
        for pred_type in ['single_double', 'big_small', 'kill_group', 'double_group']:
            for algo_num in [1, 2, 3]:
                self.algorithm_performance[pred_type][algo_num] = {
                    'total_predictions': 0,
                    'correct_predictions': 0,
                    'recent_results': [],  # 最近20次预测结果
                    'consecutive_correct': 0,  # 连续正确次数
                    'consecutive_wrong': 0,    # 连续错误次数
                    'last_switch_time': 0,     # 上次切换时间（预测次数）
                    'success_rate': 0.5,       # 成功率
                    'recent_success_rate': 0.5, # 最近20次成功率
                    'confidence_score': 0.5,    # 置信度分数
                }
        
        self.algorithm_names = {
            'single_double': '单双',
            'big_small': '大小',
            'kill_group': '杀组',
            'double_group': '双组'
        }
        
        # 记录每个预测类型的上次使用的算法
        self.last_used_algorithms = {
            'single_double': {},  # 格式: {qihao: algo_num}
            'big_small': {},
            'kill_group': {},
            'double_group': {}
        }
        
        # 记录每个预测类型的连续错误次数
        self.consecutive_errors = {
            'single_double': 0,
            'big_small': 0,
            'kill_group': 0,
            'double_group': 0
        }
        
        # 初始化算法切换器
        self.algorithm_switcher = AlgorithmSwitcher()
        
        # 从数据库加载算法性能数据
        self._load_algorithm_performance()
        
        # 最后一次保存性能数据的时间
        self.last_save_time = datetime.now()
        
        # 性能数据保存间隔 (秒)
        self.save_interval = 300  # 5分钟
    
    def _load_algorithm_performance(self):
        """从数据库加载算法性能数据"""
        try:
            logger.info("正在从数据库加载算法性能数据...")
            
            # 记录加载前的算法配置
            logger.info(f"加载前的算法配置: {self.current_algorithms}")
            
            for pred_type in ['single_double', 'big_small', 'kill_group', 'double_group']:
                # 尝试从数据库加载
                db_perf = db_manager.get_algorithm_performance(pred_type)
                
                logger.info(f"从数据库加载 {pred_type} 的算法性能数据: {db_perf is not None}")
                
                if db_perf and isinstance(db_perf, dict):
                    # 恢复当前算法
                    if 'current_algorithm' in db_perf:
                        self.current_algorithms[pred_type] = db_perf['current_algorithm']
                        logger.info(f"已加载 {pred_type} 当前算法: {db_perf['current_algorithm']}号")
                    
                    # 恢复各算法性能数据
                    if 'algorithms' in db_perf and isinstance(db_perf['algorithms'], dict):
                        for algo_num_str, perf_data in db_perf['algorithms'].items():
                            # 确保算法编号是整数
                            try:
                                algo_num = int(algo_num_str)
                            except (ValueError, TypeError):
                                logger.warning(f"算法编号无效: {algo_num_str}")
                                continue
                                
                            if algo_num not in [1, 2, 3]:
                                logger.warning(f"算法编号超出范围: {algo_num}")
                                continue
                                
                            # 更新内存中的算法性能数据
                            if not isinstance(perf_data, dict):
                                logger.warning(f"算法性能数据格式错误: {perf_data}")
                                continue
                                
                            for key, value in perf_data.items():
                                if key in self.algorithm_performance[pred_type][algo_num]:
                                    self.algorithm_performance[pred_type][algo_num][key] = value
                            
                            # 记录成功率，便于日志
                            success_rate = perf_data.get('success_rate', 0) * 100
                            logger.info(f"已加载 {pred_type} {algo_num}号算法性能数据, 成功率: {success_rate:.2f}%")
                else:
                    logger.warning(f"数据库中未找到 {pred_type} 的算法性能数据，使用默认值")
                    
            # 记录加载后的算法配置
            logger.info(f"加载后的算法配置: {self.current_algorithms}")
            logger.info("算法性能数据加载完成")
            
            # 立即保存当前算法性能数据，确保数据库更新
            self.save_algorithm_performance(force=True)
        except Exception as e:
            logger.error(f"加载算法性能数据失败: {e}")
            # 打印更详细的错误信息
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            logger.info("使用默认算法性能数据")
    
    def save_algorithm_performance(self, force=False):
        """保存算法性能数据到数据库"""
        # 检查是否需要保存
        now = datetime.now()
        elapsed = (now - self.last_save_time).total_seconds()
        
        if not force and elapsed < self.save_interval:
            return
            
        try:
            logger.info("正在保存算法性能数据到数据库...")
            
            for pred_type in ['single_double', 'big_small', 'kill_group', 'double_group']:
                # 准备保存数据
                save_data = {
                    'current_algorithm': self.current_algorithms[pred_type],
                    'algorithms': {},
                    'updated_at': now.isoformat()  # 将datetime转换为ISO格式字符串
                }
                
                # 添加各算法性能数据
                for algo_num in [1, 2, 3]:
                    # 创建算法性能数据的深拷贝，避免修改原始数据
                    algo_perf = self.algorithm_performance[pred_type][algo_num].copy()
                    
                    # 确保所有datetime对象都转换为字符串
                    if 'last_switch_time' in algo_perf and isinstance(algo_perf['last_switch_time'], datetime):
                        algo_perf['last_switch_time'] = algo_perf['last_switch_time'].isoformat()
                    
                    save_data['algorithms'][algo_num] = algo_perf
                
                # 保存到数据库
                success = db_manager.save_algorithm_performance(pred_type, save_data)
                
                if success:
                    logger.info(f"{pred_type} 算法性能数据保存成功")
                else:
                    logger.error(f"{pred_type} 算法性能数据保存失败")
            
            self.last_save_time = now
            
        except Exception as e:
            logger.error(f"保存算法性能数据失败: {e}")
    
    def update_algorithm_performance(self, pred_type, algo_num, is_correct):
        """更新算法性能统计"""
        perf = self.algorithm_performance[pred_type][algo_num]
        
        # 更新基础统计
        perf['total_predictions'] += 1
        if is_correct:
            perf['correct_predictions'] += 1
            perf['consecutive_correct'] += 1
            perf['consecutive_wrong'] = 0
        else:
            perf['consecutive_wrong'] += 1
            perf['consecutive_correct'] = 0
        
        # 更新最近结果
        perf['recent_results'].append(1 if is_correct else 0)
        if len(perf['recent_results']) > self.algorithm_switcher.switch_config['max_recent_results']:
            perf['recent_results'].pop(0)
        
        # 更新成功率
        perf['success_rate'] = perf['correct_predictions'] / perf['total_predictions']
        
        # 更新最近成功率
        recent_correct = sum(perf['recent_results'])
        recent_total = len(perf['recent_results'])
        perf['recent_success_rate'] = recent_correct / recent_total if recent_total > 0 else 0.5
        
        # 更新置信度分数
        perf['confidence_score'] = calculate_confidence_score(perf)
        
        logger.info(f"算法性能更新 - 类型: {pred_type}, 算法: {algo_num}, "
                   f"成功率: {perf['success_rate']:.2%}, "
                   f"最近成功率: {perf['recent_success_rate']:.2%}, "
                   f"置信度: {perf['confidence_score']:.2f}")
                   
        # 更新算法性能趋势
        self.algorithm_switcher.update_algorithm_trends(
            pred_type, algo_num, perf['recent_success_rate']
        )
        
        # 检查是否需要保存性能数据
        self.save_algorithm_performance()
    
    def calculate_prediction(self, records, prediction_type):
        """计算预测结果"""
        try:
            # 获取最新期号和下一期号
            latest_qihao = records[0][1]
            next_qihao = str(int(latest_qihao) + 1)
            
            # 检查缓存
            cached_prediction = db_manager.get_cached_prediction(next_qihao, prediction_type)
            if cached_prediction:
                logger.info(f"使用缓存的预测结果: {prediction_type} {next_qihao}")
                
                # 构建返回数据，根据cached_prediction的类型进行适配
                if isinstance(cached_prediction, dict):
                    return {
                        'qihao': next_qihao,
                        'prediction': cached_prediction['prediction'],
                        'prediction_type': prediction_type,
                        'algorithm_used': cached_prediction['algorithm_used'],
                        'switch_info': None  # 使用缓存时没有切换信息
                    }
                else:  # 如果是元组
                    return {
                        'qihao': next_qihao,
                        'prediction': cached_prediction[2],  # 假设prediction在索引2
                        'prediction_type': prediction_type,
                        'algorithm_used': cached_prediction[4],  # 假设algorithm_used在索引4
                        'switch_info': None  # 使用缓存时没有切换信息
                    }
            
            # 重置算法切换计数器 (如果不存在)
            if not hasattr(self, 'switch_counters'):
                self.switch_counters = {
                    'single_double': 0,
                    'big_small': 0,
                    'kill_group': 0,
                    'double_group': 0
                }
                
            # 增加算法检查计数
            self.switch_counters[prediction_type] = self.switch_counters.get(prediction_type, 0) + 1
            
            # 检查是否需要切换算法
            algorithm_switched = False
            switch_info = None
            current_algo = self.current_algorithms.get(prediction_type, 1)
            
            # 对于大小预测，始终使用算法1
            if prediction_type == 'big_small':
                # 强制设置当前算法为1号算法
                current_algo = 1
                self.current_algorithms[prediction_type] = 1
            else:
                # 周期性强制算法探索 (每100次检查重置一次强制探索状态)
                if self.switch_counters[prediction_type] >= 100:
                    self.algorithm_switcher.reset_forced_exploration()
                    self.switch_counters[prediction_type] = 0
                    logger.info(f"重置{prediction_type}算法强制探索状态")
                    
                # 检查是否需要切换算法
                new_algo, switch_reason = self.algorithm_switcher.should_switch_algorithm(
                    prediction_type,
                    current_algo,
                    self.algorithm_performance[prediction_type]
                )
                
                # 如果需要切换算法
                if new_algo != current_algo:
                    old_algo = current_algo
                    self.current_algorithms[prediction_type] = new_algo
                    algorithm_switched = True
                    
                    # 记录算法切换信息
                    switch_info = {
                        'from_algo': old_algo,
                        'to_algo': new_algo,
                        'reason': switch_reason
                    }
                    
                    logger.info(f"算法切换: {prediction_type} 从 {old_algo}号 切换到 {new_algo}号, 原因: {switch_reason}")
                    
                    # 更新当前使用的算法
                    current_algo = new_algo
            
            # 记录当前期号使用的算法
            self.last_used_algorithms[prediction_type][next_qihao] = current_algo
            
            # 使用当前算法进行预测
            prediction_content = self.predict(prediction_type, records)
            if not prediction_content:
                logger.error(f"预测失败: {prediction_type}")
                return None
                
            # 构建预测结果
            prediction_result = {
                'qihao': next_qihao,
                'prediction_type': prediction_type,
                'prediction': prediction_content,
                'algorithm_used': json.dumps({prediction_type: current_algo})
            }
            
            # 如果发生了算法切换，添加切换信息
            if algorithm_switched:
                prediction_result['switch_info'] = switch_info
            
            # 记录预测结果到缓存
            db_manager.cache_prediction(next_qihao, prediction_type, {
                'prediction': prediction_content,
                'algorithm_used': json.dumps({prediction_type: current_algo})
            })

            return prediction_result

        except Exception as e:
            logger.error(f"预测计算失败: {e}")
            return None
    
    def get_algorithm_status(self):
        """获取算法状态报告"""
        status = {}
        for pred_type in ['single_double', 'big_small', 'kill_group', 'double_group']:
            current_algo = self.current_algorithms.get(pred_type, 1)
            perf = self.algorithm_performance[pred_type][current_algo]
            
            status[pred_type] = {
                'current_algorithm': current_algo,
                'success_rate': perf['success_rate'],
                'confidence_score': perf['confidence_score'],
                'consecutive_correct': perf['consecutive_correct'],
                'consecutive_wrong': perf['consecutive_wrong'],
                'total_predictions': perf['total_predictions']
            }
        return status

    def get_algorithm_for_qihao(self, pred_type, qihao):
        """获取指定期号使用的算法号"""
        # 如果有记录，返回记录的算法号
        if qihao in self.last_used_algorithms.get(pred_type, {}):
            return self.last_used_algorithms[pred_type][qihao]
        
        # 如果没有记录，返回当前算法号
        return self.current_algorithms.get(pred_type, 1)
        
    def get_best_algorithm(self, pred_type):
        """获取最佳算法"""
        try:
            # 从数据库获取算法性能数据
            performance = db_manager.get_algorithm_performance(pred_type)
            if not performance:
                # 如果没有数据库数据，使用内存中的数据
                best_algo = None
                best_score = -1
                
                for algo_num in [1, 2, 3]:
                    if pred_type in self.algorithm_performance and algo_num in self.algorithm_performance[pred_type]:
                        algo_perf = self.algorithm_performance[pred_type][algo_num]
                        # 使用置信度分数作为评价指标
                        score = algo_perf['confidence_score']
                        
                        if score > best_score:
                            best_score = score
                            best_algo = {
                                'algorithm_number': algo_num,
                                'success_rate': algo_perf['success_rate'],
                                'confidence_score': algo_perf['confidence_score'],
                                'total_count': algo_perf['total_predictions']
                            }
                
                return best_algo
            
            # 如果有数据库数据，找出最佳算法
            best_algo = None
            best_score = -1
            
            # 检查performance是否包含algorithms字段
            if 'algorithms' in performance:
                # 正确处理字典结构
                for algo_num, algo_info in performance['algorithms'].items():
                    # 使用成功率作为评价指标
                    score = algo_info['success_rate']
                    
                    if score > best_score:
                        best_score = score
                        best_algo = {
                            'algorithm_number': int(algo_num),
                            'success_rate': algo_info['success_rate'],
                            'confidence_score': algo_info.get('confidence_score', algo_info['success_rate']),
                            'total_count': algo_info['total_predictions']
                        }
            else:
                # 兼容旧格式数据
                logger.warning(f"算法性能数据格式不正确: {performance}")
                # 使用默认算法
                best_algo = {
                    'algorithm_number': 1,
                    'success_rate': 0.5,
                    'confidence_score': 0.5,
                    'total_count': 0
                }
            
            return best_algo
        except Exception as e:
            logger.error(f"获取最佳算法失败: {e}")
            return None
    
    def predict(self, pred_type, records):
        """预测主方法，根据预测类型调用对应的预测方法
        
        Args:
            pred_type: 预测类型
            records: 历史记录
            
        Returns:
            str: 预测结果
        """
        try:
            if pred_type == 'single_double':
                # 单双预测逻辑 - 当前使用算法1
                current_algo = self.current_algorithms.get(pred_type, 1)
                return self.single_double_prediction(records, current_algo)
            elif pred_type == 'big_small':
                # 大小预测逻辑 - 当前使用算法1
                current_algo = self.current_algorithms.get(pred_type, 1)
                return self.big_small_prediction(records, current_algo)
            elif pred_type == 'kill_group':
                # 杀组预测逻辑
                current_algo = self.current_algorithms.get(pred_type, 1)
                return self.kill_group_prediction(records, current_algo)
            elif pred_type == 'double_group':
                # 双组预测逻辑
                current_algo = self.current_algorithms.get(pred_type, 1)
                return self.double_group_prediction(records, current_algo)
            else:
                logger.error(f"未知的预测类型: {pred_type}")
                return None
        except Exception as e:
            logger.error(f"预测失败: {e}")
            return None
    
    def get_current_algorithm(self, pred_type):
        """获取当前使用的算法号
        
        Args:
            pred_type: 预测类型
            
        Returns:
            int: 算法号
        """
        return self.current_algorithms.get(pred_type, 1)
    
    def single_double_prediction(self, records, algo_num=1):
        """单双预测方法
        
        Args:
            records: 历史记录
            algo_num: 算法号
            
        Returns:
            str: 预测结果
        """
        try:
            # 准备测试值
            test_values = prepare_test_values(records)
            
            # 使用基础算法中的单双预测方法
            return BaseAlgorithms.predict_single_double(test_values, algo_num)
        except Exception as e:
            logger.error(f"单双预测失败: {e}")
            return None
    
    def big_small_prediction(self, records, algo_num=1):
        """大小预测方法
        
        Args:
            records: 历史记录
            algo_num: 算法号
            
        Returns:
            str: 预测结果
        """
        try:
            # 准备测试值
            test_values = prepare_test_values(records)
            
            # 使用基础算法中的大小预测方法
            return BaseAlgorithms.predict_big_small(test_values, algo_num)
        except Exception as e:
            logger.error(f"大小预测失败: {e}")
            return None
    
    def kill_group_prediction(self, records, algo_num=1):
        """杀组预测方法
        
        Args:
            records: 历史记录
            algo_num: 算法号
            
        Returns:
            str: 预测结果
        """
        try:
            # 准备测试值
            test_values = prepare_test_values(records)
            # 添加原始记录，以便高级算法使用
            test_values['_raw_records_'] = records
            
            # 使用基础算法中的杀组预测方法
            return BaseAlgorithms.predict_kill_group(test_values, algo_num)
        except Exception as e:
            logger.error(f"杀组预测失败: {e}")
            return None
    
    def double_group_prediction(self, records, algo_num=1):
        """双组预测方法
        
        Args:
            records: 历史记录
            algo_num: 算法号
            
        Returns:
            str: 预测结果
        """
        try:
            # 使用双组预测算法
            return DoubleGroupAlgorithm.predict_double_group(records, algo_num)
        except Exception as e:
            logger.error(f"双组预测失败: {e}")
            return None 