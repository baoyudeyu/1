"""
强化学习模型模块，提供算法自学习和适应能力
"""
import numpy as np
import pickle
import os
from datetime import datetime
from loguru import logger
import random

class ReinforcementLearner:
    """强化学习模型类，实现预测算法的自我学习和优化"""
    
    def __init__(self, pred_type, model_dir='data/models'):
        """初始化
        
        Args:
            pred_type: 预测类型
            model_dir: 模型存储目录
        """
        self.pred_type = pred_type
        self.model_dir = model_dir
        
        # 创建模型目录
        os.makedirs(model_dir, exist_ok=True)
        
        # 模型保存路径
        self.model_path = os.path.join(model_dir, f"{pred_type}_model.pkl")
        
        # 学习参数
        self.learning_rate = 0.05  # 学习率
        self.discount_factor = 0.95  # 折扣因子
        self.exploration_rate = 0.2  # 探索率
        
        # Q值表，用于存储状态-动作对的价值
        self.q_table = {}
        
        # 特征提取器
        self.feature_extractor = FeatureExtractor()
        
        # 加载已有模型或初始化
        self._load_or_init_model()
        
    def _load_or_init_model(self):
        """加载已有模型或初始化新模型"""
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, 'rb') as f:
                    model_data = pickle.load(f)
                    self.q_table = model_data.get('q_table', {})
                    self.learning_rate = model_data.get('learning_rate', 0.05)
                    self.discount_factor = model_data.get('discount_factor', 0.95)
                    self.exploration_rate = model_data.get('exploration_rate', 0.2)
                    
                logger.info(f"已加载{self.pred_type}的强化学习模型")
            else:
                logger.info(f"初始化{self.pred_type}的新强化学习模型")
                # 初始化空的Q值表
                self.q_table = {}
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            # 初始化空的Q值表
            self.q_table = {}
    
    def save_model(self):
        """保存模型"""
        try:
            model_data = {
                'q_table': self.q_table,
                'learning_rate': self.learning_rate,
                'discount_factor': self.discount_factor,
                'exploration_rate': self.exploration_rate,
                'update_time': datetime.now()
            }
            
            with open(self.model_path, 'wb') as f:
                pickle.dump(model_data, f)
                
            logger.info(f"已保存{self.pred_type}的强化学习模型")
        except Exception as e:
            logger.error(f"保存模型失败: {e}")
    
    def get_state_features(self, records):
        """从历史记录中提取状态特征
        
        Args:
            records: 历史开奖记录
        
        Returns:
            状态特征字符串
        """
        try:
            # 使用特征提取器提取特征
            features = self.feature_extractor.extract_features(records, self.pred_type)
            
            # 将特征转换为状态字符串
            state = self._features_to_state(features)
            
            return state
        except Exception as e:
            logger.error(f"提取状态特征失败: {e}")
            return "default_state"
    
    def _features_to_state(self, features):
        """将特征转换为状态字符串
        
        Args:
            features: 特征字典
        
        Returns:
            状态字符串
        """
        # 按特征名称排序并连接为字符串
        state_parts = []
        for key in sorted(features.keys()):
            value = features[key]
            
            # 处理不同类型的特征值
            if isinstance(value, bool):
                state_parts.append(f"{key}:{'1' if value else '0'}")
            elif isinstance(value, (int, float)):
                # 离散化连续值
                if abs(value) < 0.001:  # 近似为零
                    state_parts.append(f"{key}:0")
                elif value > 0:
                    state_parts.append(f"{key}:p{int(value*10)}")
                else:
                    state_parts.append(f"{key}:n{int(abs(value)*10)}")
            else:
                state_parts.append(f"{key}:{value}")
        
        return "|".join(state_parts)
    
    def select_algorithm(self, state, available_algorithms=[1, 2, 3]):
        """根据当前状态选择最优算法
        
        Args:
            state: 当前状态
            available_algorithms: 可用算法列表
            
        Returns:
            选择的算法编号
        """
        # 探索: 随机选择算法
        if random.random() < self.exploration_rate:
            return random.choice(available_algorithms)
        
        # 利用: 选择Q值最高的算法
        if state not in self.q_table:
            self.q_table[state] = {algo: 0.5 for algo in available_algorithms}
        
        state_q_values = self.q_table[state]
        
        # 获取Q值最高的算法
        best_algorithm = max(state_q_values.items(), key=lambda x: x[1])[0]
        
        return int(best_algorithm)
    
    def update_q_values(self, state, action, reward, next_state):
        """更新Q值表
        
        Args:
            state: 当前状态
            action: 选择的动作（算法编号）
            reward: 获得的奖励
            next_state: 下一个状态
        """
        try:
            # 确保状态存在于Q表中
            if state not in self.q_table:
                self.q_table[state] = {1: 0.5, 2: 0.5, 3: 0.5}
            
            if next_state not in self.q_table:
                self.q_table[next_state] = {1: 0.5, 2: 0.5, 3: 0.5}
            
            # 获取当前Q值
            current_q = self.q_table[state].get(action, 0.5)
            
            # 计算下一状态的最大Q值
            max_next_q = max(self.q_table[next_state].values())
            
            # 计算新的Q值
            new_q = current_q + self.learning_rate * (reward + self.discount_factor * max_next_q - current_q)
            
            # 更新Q值表
            self.q_table[state][action] = new_q
            
            # 定期保存模型
            if random.random() < 0.1:  # 10%概率保存
                self.save_model()
                
        except Exception as e:
            logger.error(f"更新Q值失败: {e}")
    
    def calculate_reward(self, is_correct, confidence_score=0.5):
        """计算奖励值
        
        Args:
            is_correct: 预测是否正确
            confidence_score: 置信度分数
            
        Returns:
            奖励值
        """
        if is_correct:
            # 正确的预测，奖励根据置信度增加
            return 1.0 + confidence_score
        else:
            # 错误的预测，惩罚根据置信度增加
            return -1.0 - confidence_score
    
    def adapt_parameters(self, success_rate, iteration_count):
        """根据性能自适应调整学习参数
        
        Args:
            success_rate: 成功率
            iteration_count: 迭代次数
        """
        try:
            # 调整探索率 - 随着迭代次数增加或成功率稳定，降低探索率
            self.exploration_rate = max(0.05, min(0.3, 0.5 / (1 + 0.1 * iteration_count)))
            
            # 调整学习率 - 随着成功率提高，降低学习率
            if success_rate > 0.7:
                self.learning_rate = max(0.01, self.learning_rate * 0.95)
            elif success_rate < 0.4:
                self.learning_rate = min(0.2, self.learning_rate * 1.05)
                
            logger.info(f"自适应参数: 探索率={self.exploration_rate:.3f}, 学习率={self.learning_rate:.3f}")
        except Exception as e:
            logger.error(f"调整学习参数失败: {e}")

class FeatureExtractor:
    """特征提取器类，从历史数据中提取有用特征"""
    
    def extract_features(self, records, pred_type):
        """提取特征
        
        Args:
            records: 历史开奖记录
            pred_type: 预测类型
            
        Returns:
            特征字典
        """
        features = {}
        
        try:
            # 基础统计特征
            self._extract_basic_stats(records, features)
            
            # 根据预测类型提取特定特征
            if pred_type == 'single_double':
                self._extract_single_double_features(records, features)
            elif pred_type == 'big_small':
                self._extract_big_small_features(records, features)
            elif pred_type == 'kill_group':
                self._extract_kill_group_features(records, features)
            elif pred_type == 'double_group':
                self._extract_double_group_features(records, features)
            
            # 提取趋势特征
            self._extract_trend_features(records, features)
            
            # 提取周期特征
            self._extract_cycle_features(records, features)
            
        except Exception as e:
            logger.error(f"提取特征失败: {e}")
            
        return features
    
    def _extract_basic_stats(self, records, features):
        """提取基础统计特征"""
        try:
            if not records or len(records) < 5:
                return
                
            # 分析最近的记录
            big_count = 0
            odd_count = 0
            combo_types = {"豹子": 0, "对子": 0, "顺子": 0, "杂六": 0}
            
            for record in records[:10]:  # 最近10期
                try:
                    is_big = bool(record[5])
                    is_odd = bool(record[6])
                    combo_type = record[7]
                    
                    if is_big:
                        big_count += 1
                    if is_odd:
                        odd_count += 1
                    
                    if combo_type in combo_types:
                        combo_types[combo_type] += 1
                except IndexError:
                    continue
            
            # 记录特征
            total = min(10, len(records))
            features['big_ratio'] = big_count / total if total > 0 else 0.5
            features['odd_ratio'] = odd_count / total if total > 0 else 0.5
            
            # 组合类型比例
            for combo, count in combo_types.items():
                features[f'{combo}_ratio'] = count / total if total > 0 else 0
                
        except Exception as e:
            logger.error(f"提取基础统计特征失败: {e}")
    
    def _extract_single_double_features(self, records, features):
        """提取单双特征"""
        try:
            # 统计连续出现的单双次数
            odd_streak = 0
            even_streak = 0
            last_is_odd = None
            
            for record in records[:10]:
                try:
                    is_odd = bool(record[6])
                    
                    if last_is_odd is None:
                        last_is_odd = is_odd
                        continue
                    
                    if is_odd:
                        if last_is_odd:
                            odd_streak += 1
                            even_streak = 0
                        else:
                            odd_streak = 1
                            even_streak = 0
                    else:
                        if not last_is_odd:
                            even_streak += 1
                            odd_streak = 0
                        else:
                            even_streak = 1
                            odd_streak = 0
                            
                    last_is_odd = is_odd
                except IndexError:
                    continue
            
            # 记录特征
            features['odd_streak'] = odd_streak
            features['even_streak'] = even_streak
            
        except Exception as e:
            logger.error(f"提取单双特征失败: {e}")
    
    def _extract_big_small_features(self, records, features):
        """提取大小特征"""
        try:
            # 统计连续出现的大小次数
            big_streak = 0
            small_streak = 0
            last_is_big = None
            
            for record in records[:10]:
                try:
                    is_big = bool(record[5])
                    
                    if last_is_big is None:
                        last_is_big = is_big
                        continue
                    
                    if is_big:
                        if last_is_big:
                            big_streak += 1
                            small_streak = 0
                        else:
                            big_streak = 1
                            small_streak = 0
                    else:
                        if not last_is_big:
                            small_streak += 1
                            big_streak = 0
                        else:
                            small_streak = 1
                            big_streak = 0
                            
                    last_is_big = is_big
                except IndexError:
                    continue
            
            # 记录特征
            features['big_streak'] = big_streak
            features['small_streak'] = small_streak
            
        except Exception as e:
            logger.error(f"提取大小特征失败: {e}")
    
    def _extract_kill_group_features(self, records, features):
        """提取杀组特征"""
        try:
            # 分析最近5期的组合类型
            combos = []
            for record in records[:5]:
                try:
                    is_big = bool(record[5])
                    is_odd = bool(record[6])
                    combo = f"{'大' if is_big else '小'}{'单' if is_odd else '双'}"
                    combos.append(combo)
                except IndexError:
                    continue
            
            # 统计各组合出现次数
            combo_counts = {
                "大单": 0,
                "大双": 0,
                "小单": 0,
                "小双": 0
            }
            
            for combo in combos:
                if combo in combo_counts:
                    combo_counts[combo] += 1
            
            # 记录特征
            for combo, count in combo_counts.items():
                features[f'{combo}_count'] = count
            
            # 找出出现次数最多的组合
            most_common = max(combo_counts.items(), key=lambda x: x[1])[0] if combo_counts else None
            features['most_common_combo'] = most_common
            
        except Exception as e:
            logger.error(f"提取杀组特征失败: {e}")
    
    def _extract_double_group_features(self, records, features):
        """提取双组特征"""
        try:
            # 与杀组特征提取类似，但增加分析
            self._extract_kill_group_features(records, features)
            
            # 额外分析最近10期的组合转换模式
            transitions = {
                "大单→大双": 0,
                "大单→小单": 0,
                "大单→小双": 0,
                "大双→大单": 0,
                "大双→小单": 0,
                "大双→小双": 0,
                "小单→大单": 0,
                "小单→大双": 0,
                "小单→小双": 0,
                "小双→大单": 0,
                "小双→大双": 0,
                "小双→小单": 0
            }
            
            last_combo = None
            for record in records[:10]:
                try:
                    is_big = bool(record[5])
                    is_odd = bool(record[6])
                    combo = f"{'大' if is_big else '小'}{'单' if is_odd else '双'}"
                    
                    if last_combo:
                        transition = f"{last_combo}→{combo}"
                        if transition in transitions:
                            transitions[transition] += 1
                    
                    last_combo = combo
                except IndexError:
                    continue
            
            # 找出最常见的转换模式
            common_transitions = sorted(
                transitions.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:2]
            
            if common_transitions:
                features['common_transition1'] = common_transitions[0][0]
                if len(common_transitions) > 1:
                    features['common_transition2'] = common_transitions[1][0]
            
        except Exception as e:
            logger.error(f"提取双组特征失败: {e}")
    
    def _extract_trend_features(self, records, features):
        """提取趋势特征"""
        try:
            # 分析和值的趋势
            sums = []
            for record in records[:15]:  # 分析最近15期
                try:
                    sum_value = int(record[4])
                    sums.append(sum_value)
                except (IndexError, ValueError):
                    continue
            
            if len(sums) >= 5:
                # 计算平均值
                avg_sum = sum(sums) / len(sums)
                features['avg_sum'] = avg_sum
                
                # 计算趋势（使用简单线性回归）
                if len(sums) >= 3:
                    x = np.array(range(len(sums)))
                    y = np.array(sums)
                    slope = np.cov(x, y)[0, 1] / np.var(x)
                    features['sum_trend'] = slope
                
                # 最近值相对于平均值的位置
                if sums:
                    recent_sum = sums[0]
                    features['recent_vs_avg'] = (recent_sum - avg_sum) / avg_sum if avg_sum else 0
            
        except Exception as e:
            logger.error(f"提取趋势特征失败: {e}")
    
    def _extract_cycle_features(self, records, features):
        """提取周期特征"""
        try:
            # 尝试检测大小、单双的周期
            big_small_seq = []
            odd_even_seq = []
            
            for record in records[:20]:
                try:
                    is_big = bool(record[5])
                    is_odd = bool(record[6])
                    
                    big_small_seq.append(1 if is_big else 0)
                    odd_even_seq.append(1 if is_odd else 0)
                except IndexError:
                    continue
            
            # 检测简单周期
            for seq_len in [2, 3, 4]:
                if len(big_small_seq) >= seq_len * 2:
                    # 检查大小序列是否有周期
                    has_big_small_cycle = self._check_cycle(big_small_seq, seq_len)
                    features[f'has_big_small_cycle_{seq_len}'] = has_big_small_cycle
                
                if len(odd_even_seq) >= seq_len * 2:
                    # 检查单双序列是否有周期
                    has_odd_even_cycle = self._check_cycle(odd_even_seq, seq_len)
                    features[f'has_odd_even_cycle_{seq_len}'] = has_odd_even_cycle
            
        except Exception as e:
            logger.error(f"提取周期特征失败: {e}")
    
    def _check_cycle(self, sequence, cycle_length):
        """检查序列是否存在周期"""
        if len(sequence) < cycle_length * 2:
            return False
            
        # 提取可能的周期模式
        pattern = sequence[:cycle_length]
        
        # 检查该模式是否在序列中重复出现
        matches = 0
        total_checks = 0
        
        for i in range(0, len(sequence) - cycle_length, cycle_length):
            total_checks += 1
            current = sequence[i:i+cycle_length]
            if current == pattern:
                matches += 1
        
        # 如果匹配率超过50%，认为存在周期
        return (matches / total_checks >= 0.5) if total_checks > 0 else False 