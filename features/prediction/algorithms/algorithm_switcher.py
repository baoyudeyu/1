"""
算法切换管理模块，处理算法切换的相关逻辑
"""
import random
# IDE可能错误标记此导入，但不影响程序运行
import numpy as np  # type: ignore
from datetime import datetime, timedelta
# IDE可能错误标记此导入，但不影响程序运行
from loguru import logger  # type: ignore
from features.prediction.utils.prediction_utils import calculate_confidence_score

class AlgorithmSwitcher:
    """算法切换管理类，处理算法切换的相关逻辑"""
    
    def __init__(self):
        # 算法切换配置
        self.switch_config = {
            'min_predictions': 3,         # 最小预测次数
            'max_recent_results': 20,     # 最近结果记录数
            'min_switch_interval': 3,     # 最小切换间隔(次数)
            'confidence_threshold': 0.5,   # 置信度阈值
            'success_rate_threshold': 0.5, # 成功率阈值
            'exploration_rate': 0.2,       # 探索率
            'adaptive_learning_rate': 0.05, # 自适应学习率
            'trend_window': 5,            # 趋势分析窗口
            'dynamic_weight_adjust': True, # 是否启用动态权重调整
            'performance_memory': 10,      # 性能记忆周期
            'time_decay_factor': 0.9,      # 时间衰减因子
            'force_rotation_interval': 15, # 强制轮换间隔(次数)
            'rotation_counter': {},         # 记录每种预测类型使用同一算法的次数
            'min_predictions_before_switch': 5,  # 切换算法前所需的最小预测次数
            'max_consecutive_errors': 3,  # 允许的最大连续错误次数
            'min_confidence_score': 0.4,  # 最小置信度分数
            'min_recent_success_rate': 0.4,  # 最小近期成功率
            'exploration_probability': 0.2,  # 探索概率
            'exploration_threshold': 10  # 探索阈值
        }
        
        # 添加强制探索属性
        self.force_exploration = False
        
        # 记录强制探索状态
        self.forced_exploration_done = {
            'single_double': False,
            'big_small': False,
            'kill_group': False,
            'double_group': False
        }
        
        # 记录上次持久化时间
        self.last_persistence_time = datetime.now()
        
        # 初始化算法切换历史
        self.algorithm_switch_history = {
            'single_double': [],
            'big_small': [],
            'kill_group': [],
            'double_group': []
        }
        
        # 初始化算法性能趋势
        self.algorithm_trends = {
            'single_double': {1: [], 2: [], 3: []},
            'big_small': {1: [], 2: [], 3: []},
            'kill_group': {1: [], 2: [], 3: []},
            'double_group': {1: [], 2: [], 3: []}
        }
        
        # 初始化动态权重
        self.dynamic_weights = {
            'single_double': {'confidence': 0.4, 'recent_success': 0.4, 'overall_success': 0.2},
            'big_small': {'confidence': 0.4, 'recent_success': 0.4, 'overall_success': 0.2},
            'kill_group': {'confidence': 0.4, 'recent_success': 0.4, 'overall_success': 0.2},
            'double_group': {'confidence': 0.4, 'recent_success': 0.4, 'overall_success': 0.2}
        }
        
        # 初始化时间衰减记忆
        self.performance_memory = {
            'single_double': {1: [], 2: [], 3: []},
            'big_small': {1: [], 2: [], 3: []},
            'kill_group': {1: [], 2: [], 3: []},
            'double_group': {1: [], 2: [], 3: []}
        }
        
        # 初始化轮换计数器
        for pred_type in ['single_double', 'big_small', 'kill_group', 'double_group']:
            self.switch_config['rotation_counter'][pred_type] = 0
    
    def should_switch_algorithm(self, pred_type, current_algo, perf_data):
        """检查是否需要切换算法
        
        Args:
            pred_type: 预测类型
            current_algo: 当前使用的算法
            perf_data: 性能数据
            
        Returns:
            tuple: (新算法号, 切换原因) 如果不需要切换则返回当前算法
        """
        try:
            # 获取配置和性能数据
            config = self.switch_config
            
            # 获取当前算法的性能数据
            current_perf = perf_data.get(current_algo, {})
            
            # 检查是否有足够的数据进行决策
            if current_perf.get('total_predictions', 0) < config['min_predictions_before_switch']:
                return current_algo, "数据不足"
                
            # 检查连续错误次数
            consecutive_wrong = current_perf.get('consecutive_wrong', 0)
            if consecutive_wrong >= config['max_consecutive_errors']:
                return self._select_next_algorithm(pred_type, current_algo, perf_data), f"连续错误次数过多: {consecutive_wrong}次"
                
            # 检查置信度
            confidence_score = current_perf.get('confidence_score', 0.5)
            if confidence_score < config['min_confidence_score']:
                return self._select_next_algorithm(pred_type, current_algo, perf_data), f"置信度过低: {confidence_score:.2f}"
                
            # 检查最近成功率
            recent_success_rate = current_perf.get('recent_success_rate', 0.5)
            if recent_success_rate < config['min_recent_success_rate']:
                return self._select_next_algorithm(pred_type, current_algo, perf_data), f"最近成功率低: {recent_success_rate:.2%}"
                
            # 检查性能趋势是否持续下降
            trend = self.algorithm_trends.get(pred_type, {}).get(current_algo, [])
            if len(trend) >= 3:
                if all(trend[i] < trend[i-1] for i in range(1, len(trend))):
                    return self._select_next_algorithm(pred_type, current_algo, perf_data), "性能持续下降"
                    
            # 检查是否需要周期性探索其他算法
            explore_prob = config['exploration_probability']
            if self.force_exploration or (random.random() < explore_prob and 
                                         current_perf.get('total_predictions', 0) > config['exploration_threshold']):
                return self._select_next_algorithm(pred_type, current_algo, perf_data), "算法探索"
                
            # 如果不需要切换，返回当前算法
            return current_algo, "算法运行正常"
            
        except Exception as e:
            logger.error(f"检查是否需要切换算法时出错: {e}")
            return current_algo, "检查错误"
    
    def _calculate_dynamic_exploration_rate(self, pred_type, current_algo, algorithm_performance):
        """计算动态探索率 - 算法表现越稳定，探索率越低"""
        base_rate = self.switch_config['exploration_rate']
        current_perf = algorithm_performance[pred_type][current_algo]
        
        # 计算稳定性指标 (0-1之间，越高越稳定)
        stability = 0.5
        
        # 如果有足够的历史数据，计算方差作为稳定性指标
        if len(self.algorithm_trends[pred_type][current_algo]) >= 3:
            recent_trends = self.algorithm_trends[pred_type][current_algo][-3:]
            variance = np.var(recent_trends) if recent_trends else 0
            stability = max(0, 1 - min(variance * 10, 1))  # 方差越小，稳定性越高
        
        # 根据稳定性调整探索率
        adjusted_rate = base_rate * (1 - stability * 0.5)  # 稳定性高时，探索率降低50%
        
        # 根据当前算法的表现调整探索率
        if current_perf['success_rate'] > 0.7:  # 表现很好时，降低探索率
            adjusted_rate *= 0.8
        elif current_perf['success_rate'] < 0.4:  # 表现不佳时，提高探索率
            adjusted_rate *= 1.2
            
        return min(max(adjusted_rate, 0.02), 0.2)  # 确保探索率在2%-20%之间
    
    def _analyze_performance_trend(self, pred_type, algo_num):
        """分析算法性能趋势"""
        trends = self.algorithm_trends[pred_type][algo_num]
        
        # 如果没有足够的数据，返回无趋势
        if len(trends) < self.switch_config['trend_window']:
            return {'is_declining': False, 'trend_value': 0}
        
        # 获取最近的趋势窗口数据
        recent_trends = trends[-self.switch_config['trend_window']:]
        
        # 计算简单线性回归斜率
        x = np.array(range(len(recent_trends)))
        y = np.array(recent_trends)
        
        # 防止除零错误
        if len(x) <= 1 or np.std(x) == 0:
            return {'is_declining': False, 'trend_value': 0}
            
        slope = np.cov(x, y)[0, 1] / np.var(x)
        
        # 判断趋势
        is_declining = slope < -0.01  # 斜率小于-0.01认为是下降趋势
        
        return {'is_declining': is_declining, 'trend_value': slope}

    def _find_best_algorithm(self, pred_type, algorithm_performance):
        """查找最佳算法"""
        best_algo = None
        best_score = -1
        
        # 获取当前预测类型的动态权重
        weights = self.dynamic_weights[pred_type]
        
        for algo_num in [1, 2, 3]:
            perf = algorithm_performance[pred_type][algo_num]
            
            # 计算综合评分
            score = (perf['confidence_score'] * weights['confidence'] + 
                     perf['recent_success_rate'] * weights['recent_success'] + 
                     perf['success_rate'] * weights['overall_success'])
            
            # 应用时间衰减记忆
            memory_bonus = self._calculate_memory_bonus(pred_type, algo_num)
            score += memory_bonus
            
            if score > best_score:
                best_score = score
                best_algo = algo_num
        
        return best_algo
    
    def _calculate_memory_bonus(self, pred_type, algo_num):
        """计算时间衰减记忆奖励"""
        memory = self.performance_memory[pred_type][algo_num]
        if not memory:
            return 0
            
        # 计算时间衰减的加权平均
        total_weight = 0
        weighted_sum = 0
        decay = self.switch_config['time_decay_factor']
        
        for i, (timestamp, performance) in enumerate(memory):
            # 计算时间权重 (越近的数据权重越大)
            time_weight = decay ** (len(memory) - i - 1)
            weighted_sum += performance * time_weight
            total_weight += time_weight
            
        if total_weight == 0:
            return 0
            
        return weighted_sum / total_weight * 0.1  # 记忆奖励最多影响10%
    
    def update_algorithm_trends(self, pred_type, algo_num, performance_value):
        """更新算法性能趋势"""
        # 添加新的性能值到趋势列表
        self.algorithm_trends[pred_type][algo_num].append(performance_value)
        
        # 只保留最近20个趋势值
        if len(self.algorithm_trends[pred_type][algo_num]) > 20:
            self.algorithm_trends[pred_type][algo_num].pop(0)
            
        # 更新性能记忆
        self.performance_memory[pred_type][algo_num].append((datetime.now(), performance_value))
        
        # 只保留最近的性能记忆
        if len(self.performance_memory[pred_type][algo_num]) > self.switch_config['performance_memory']:
            self.performance_memory[pred_type][algo_num].pop(0)
            
        # 每隔一段时间检查数据持久化
        time_since_persistence = (datetime.now() - self.last_persistence_time).total_seconds()
        if time_since_persistence > 300:  # 5分钟
            self._check_persistence()
            self.last_persistence_time = datetime.now()
    
    def _check_persistence(self):
        """检查算法性能数据是否正确持久化到数据库"""
        try:
            # 导入数据库管理器
            from features.data.db_manager import db_manager
            
            # 记录数据持久化状态
            logger.info("执行算法性能数据持久化检查")
            
            # 检查各预测类型的算法性能数据
            for pred_type in ['single_double', 'big_small', 'kill_group', 'double_group']:
                # 获取数据库中的算法性能数据
                db_performance = db_manager.get_algorithm_performance(pred_type)
                
                # 校验数据有效性
                if not db_performance:
                    logger.warning(f"{pred_type}算法性能数据在数据库中不存在，可能影响算法切换")
                else:
                    logger.info(f"{pred_type}算法性能数据持久化正常，当前算法：{db_performance.get('current_algorithm', 1)}")
        except Exception as e:
            logger.error(f"数据持久化检查失败: {e}")
            
    def set_force_exploration(self, value=True):
        """设置强制探索状态
        
        Args:
            value: 布尔值，True表示启用强制探索，False表示禁用强制探索
        """
        self.force_exploration = value
        status = "启用" if value else "禁用"
        logger.info(f"已{status}强制探索模式")
            
    def reset_forced_exploration(self):
        """重置强制探索状态，允许再次触发强制探索"""
        for pred_type in self.forced_exploration_done:
            self.forced_exploration_done[pred_type] = False
        logger.info("已重置所有预测类型的强制探索状态")
    
    def force_algorithm_rotation(self, pred_type=None):
        """强制触发算法轮换"""
        if pred_type:
            self.switch_config['rotation_counter'][pred_type] = self.switch_config['force_rotation_interval']
            logger.info(f"已触发{pred_type}的强制算法轮换")
        else:
            # 对所有预测类型触发强制轮换
            for pt in self.switch_config['rotation_counter']:
                self.switch_config['rotation_counter'][pt] = self.switch_config['force_rotation_interval']
            logger.info("已触发所有预测类型的强制算法轮换")

    def select_next_algorithm(self, pred_type, current_algo, algorithm_performance):
        """选择下一个要使用的算法"""
        # 在选择新算法时重置轮换计数器
        self.switch_config['rotation_counter'][pred_type] = 0
        
        # 如果是由于连续错误触发的切换，选择置信度最高的算法
        if algorithm_performance[pred_type][current_algo]['consecutive_wrong'] >= 3:
            next_algo = self._find_best_algorithm(pred_type, algorithm_performance)
            switch_reason = f"连续{algorithm_performance[pred_type][current_algo]['consecutive_wrong']}次预测失败"
        else:
            # 分析性能趋势
            trend_result = self._analyze_performance_trend(pred_type, current_algo)
            if trend_result['is_declining']:
                # 如果当前算法性能下降，选择最佳算法
                next_algo = self._find_best_algorithm(pred_type, algorithm_performance)
                switch_reason = f"性能下降趋势({trend_result['trend_value']:.3f})"
            else:
                # 否则在其他算法中随机选择，但偏好置信度较高的算法
                other_algos = [i for i in [1, 2, 3] if i != current_algo]
                weights = []
                for algo in other_algos:
                    perf = algorithm_performance[pred_type][algo]
                    
                    # 基础权重
                    weight = perf['confidence_score'] + 0.1
                    
                    # 考虑趋势因素
                    algo_trend = self._analyze_performance_trend(pred_type, algo)
                    if not algo_trend['is_declining']:
                        weight *= 1.2  # 上升趋势的算法权重提高20%
                    
                    # 考虑记忆因素
                    memory_bonus = self._calculate_memory_bonus(pred_type, algo)
                    weight += memory_bonus
                    
                    weights.append(weight)
                
                # 归一化权重
                total_weight = sum(weights)
                if total_weight > 0:
                    weights = [w/total_weight for w in weights]
                    next_algo = random.choices(other_algos, weights=weights)[0]
                else:
                    next_algo = random.choice(other_algos)
                
                # 确定切换原因
                if algorithm_performance[pred_type][current_algo]['confidence_score'] < self.switch_config['confidence_threshold']:
                    switch_reason = f"置信度低于阈值({algorithm_performance[pred_type][current_algo]['confidence_score']:.2f})"
                elif random.random() < self._calculate_dynamic_exploration_rate(pred_type, current_algo, algorithm_performance):
                    switch_reason = "智能探索"
                else:
                    best_algo = self._find_best_algorithm(pred_type, algorithm_performance)
                    best_confidence = algorithm_performance[pred_type][best_algo]['confidence_score']
                    switch_reason = f"发现更优算法(置信度差: {best_confidence - algorithm_performance[pred_type][current_algo]['confidence_score']:.2f})"
        
        # 记录切换时间
        algorithm_performance[pred_type][next_algo]['last_switch_time'] = algorithm_performance[pred_type][current_algo]['total_predictions']
        
        # 记录切换历史
        switch_record = {
            'time': datetime.now(),
            'from_algo': current_algo,
            'to_algo': next_algo,
            'reason': switch_reason,
            'performance': {
                'old_algo': {
                    'success_rate': algorithm_performance[pred_type][current_algo]['success_rate'],
                    'confidence': algorithm_performance[pred_type][current_algo]['confidence_score']
                },
                'new_algo': {
                    'success_rate': algorithm_performance[pred_type][next_algo]['success_rate'],
                    'confidence': algorithm_performance[pred_type][next_algo]['confidence_score']
                }
            }
        }
        self.algorithm_switch_history[pred_type].append(switch_record)
        
        # 清理过期的切换历史（只保留最近50条记录）
        if len(self.algorithm_switch_history[pred_type]) > 50:
            self.algorithm_switch_history[pred_type].pop(0)
        
        # 在select_next_algorithm方法中添加强制性探索
        if current_algo == 1 and algorithm_performance[pred_type][current_algo]['total_predictions'] > 10 and not self.forced_exploration_done.get(pred_type, False):
            next_algo = random.choice([2, 3])
            self.forced_exploration_done[pred_type] = True
            switch_reason = "强制算法探索"
            logger.info(f"{pred_type}触发强制探索，从算法1切换到算法{next_algo}")
        
        # 记录切换详情日志
        logger.info(f"算法切换完成 - {pred_type}: 从{current_algo}号切换到{next_algo}号, 原因: {switch_reason}")
        
        return next_algo, switch_record 
    
    def _select_next_algorithm(self, pred_type, current_algo, perf_data):
        """选择下一个要使用的算法
        
        Args:
            pred_type: 预测类型
            current_algo: 当前使用的算法号
            perf_data: 性能数据
            
        Returns:
            int: 新算法号
        """
        try:
            # 获取所有可用算法
            all_algos = [1, 2, 3]  # 假设有3个可用算法
            other_algos = [algo for algo in all_algos if algo != current_algo]
            
            if not other_algos:
                logger.warning(f"没有其他可用算法，继续使用当前算法: {current_algo}")
                return current_algo
                
            # 按照置信度分数降序排序
            sorted_algos = sorted(
                other_algos,
                key=lambda a: perf_data.get(a, {}).get('confidence_score', 0),
                reverse=True
            )
            
            # 获取置信度最高的算法
            next_algo = sorted_algos[0]
            
            logger.info(f"选择新算法: 从{current_algo}号切换到{next_algo}号, 置信度: {perf_data.get(next_algo, {}).get('confidence_score', 0):.2f}")
            return next_algo
        except Exception as e:
            logger.error(f"选择下一个算法失败: {e}")
            # 简单地选择另一个算法
            return current_algo % 3 + 1