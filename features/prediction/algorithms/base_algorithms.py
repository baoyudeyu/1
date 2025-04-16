"""
基础算法模块，包含各种预测类型的基础算法实现
"""
from features.prediction.utils.prediction_utils import get_last_digit
import numpy as np
from loguru import logger
import random

class AlgorithmComponents:
    """算法组件类，提供可复用的算法基础组件"""
    
    @staticmethod
    def sum_pattern(values, pattern):
        """按照指定模式对值进行求和"""
        try:
            total = 0
            for key in pattern:
                if key in values:
                    total += values[key]
            return total
        except Exception as e:
            logger.error(f"模式求和失败: {e}")
            return 0
    
    @staticmethod
    def weighted_sum(values, weights):
        """计算加权和"""
        try:
            total = 0
            for key, weight in weights.items():
                if key in values:
                    total += values[key] * weight
            return total
        except Exception as e:
            logger.error(f"加权求和失败: {e}")
            return 0
    
    @staticmethod
    def moving_average(values, window=3):
        """计算移动平均"""
        try:
            if not values:
                return 0
            if len(values) < window:
                return sum(values) / len(values)
            return sum(values[-window:]) / window
        except Exception as e:
            logger.error(f"移动平均计算失败: {e}")
            return 0
    
    @staticmethod
    def trend_analysis(values):
        """简单趋势分析"""
        try:
            if len(values) < 2:
                return 0
            
            # 计算简单线性回归斜率
            x = np.array(range(len(values)))
            y = np.array(values)
            
            # 防止除零错误
            if len(x) <= 1 or np.std(x) == 0:
                return 0
                
            slope = np.cov(x, y)[0, 1] / np.var(x)
            return slope
        except Exception as e:
            logger.error(f"趋势分析失败: {e}")
            return 0
            
    @staticmethod
    def apply_formula(values, formula_type, **params):
        """应用公式计算
        
        Args:
            values: 输入值
            formula_type: 公式类型
            params: 其他参数
            
        Returns:
            计算结果
        """
        try:
            if formula_type == 'abc_standard':
                # 标准的A、B、C值组合公式
                return (values.get('A1', 0) + values.get('B2', 0) + values.get('C3', 0)) / 3
            
            elif formula_type == 'abc_weighted':
                # 带权重的A、B、C值组合
                weights = params.get('weights', {'A': 0.5, 'B': 0.3, 'C': 0.2})
                return (values.get('A1', 0) * weights['A'] + 
                        values.get('B2', 0) * weights['B'] + 
                        values.get('C3', 0) * weights['C'])
            
            elif formula_type == 'square_sum':
                # 平方和
                return (values.get('A1', 0) ** 2 + 
                        values.get('B1', 0) ** 2 + 
                        values.get('C1', 0) ** 2)
            
            elif formula_type == 'pattern_cycle':
                # 周期模式
                keys = params.get('keys', ['A1', 'B2', 'C3', 'A3', 'B2', 'C1'])
                return sum(values.get(k, 0) for k in keys) / len(keys)
            
            else:
                logger.warning(f"未知公式类型: {formula_type}")
                return 0
                
        except Exception as e:
            logger.error(f"应用公式失败: {e}")
            return 0

class BaseAlgorithms:
    """基础算法类，提供各种预测类型的基础算法实现"""
    
    @staticmethod
    def get_single_double_algorithms():
        """获取单双预测算法"""
        return {
            1: lambda v: (v.get('A1', 0) + v.get('B2', 0) + v.get('C3', 0) + v.get('C1', 0) + v.get('B2', 0) + v.get('A3', 0) + v.get('B1', 0) + v.get('B2', 0) + v.get('B3', 0)) / 3,
            2: lambda v: (v.get('A1', 0) + v.get('B2', 0) + v.get('C3', 0) + v.get('C1', 0) + v.get('B2', 0) + v.get('A3', 0) + v.get('A2', 0) + v.get('B2', 0) + v.get('C2', 0)) / 3
        }
    
    @staticmethod
    def get_big_small_algorithms():
        """获取大小预测算法"""
        return {
            1: lambda v: (v.get('A1', 0) + v.get('A2', 0) + v.get('A3', 0) + v.get('C1', 0) + v.get('C2', 0) + v.get('C3', 0) + v.get('B1', 0) + v.get('B2', 0) + v.get('B3', 0)) / 3,
            2: lambda v: AlgorithmComponents.apply_formula(v, 'abc_weighted', weights={'A': 0.4, 'B': 0.35, 'C': 0.25})
        }
    
    @staticmethod
    def get_kill_group_algorithms():
        """获取杀组预测算法"""
        return {
            1: lambda v: AlgorithmComponents.apply_formula(v, 'abc_standard'),
            2: lambda v: (v.get('A1', 0) + v.get('B2', 0) + v.get('C3', 0) + v.get('C1', 0) + v.get('B2', 0) + v.get('A3', 0) + v.get('B1', 0) + v.get('B2', 0) + v.get('B3', 0)) / 3,
            3: lambda v: (v.get('A1', 0) + v.get('B2', 0) + v.get('C3', 0) + v.get('C1', 0) + v.get('B2', 0) + v.get('A3', 0) + v.get('A2', 0) + v.get('B2', 0) + v.get('C2', 0)) / 3
        }
    
    @staticmethod
    def predict_single_double(values, algo_num, big_boundary=14):
        """单双预测实现"""
        algorithms = BaseAlgorithms.get_single_double_algorithms()
        if algo_num not in algorithms:
            algo_num = 1
            
        # 使用指定算法计算结果
        result = algorithms[algo_num](values)
        result = abs(int(round(result)))  # 取绝对值并四舍五入
        return f"{'单' if result % 2 == 1 else '双'}{result:02d}"
    
    @staticmethod
    def predict_big_small(values, algo_num, big_boundary=14):
        """大小预测实现"""
        algorithms = BaseAlgorithms.get_big_small_algorithms()
        if algo_num not in algorithms:
            algo_num = 1
            
        # 使用指定算法计算结果
        result = algorithms[algo_num](values)
        result = abs(int(round(result)))  # 取绝对值并四舍五入
        return f"{'大' if result >= big_boundary else '小'}{result:02d}"
    
    @staticmethod
    def predict_kill_group(values, algo_num, big_boundary=14):
        """杀组预测实现 - 高级数据分析版
        
        Args:
            values: 包含原始记录的值字典
            algo_num: 算法变异系数，决定预测多样性
            big_boundary: 大小界限值
            
        Returns:
            str: 杀组预测结果，格式为"杀大单"等
        """
        # 获取原始记录 (从传入的values中尝试获取raw_records)
        raw_records = values.get('_raw_records_', [])
        
        # 如果没有原始记录，则无法进行智能分析
        if not raw_records or len(raw_records) < 5:
            logger.warning("无法获取原始记录，回退到基本算法")
            # 使用一个基本算法作为备用
            result = (values.get('A1', 0) + values.get('B1', 0) + values.get('C1', 0)) / 3
            result = abs(int(round(result)))
            return f"杀{'大' if result >= big_boundary else '小'}{'单' if result % 2 == 1 else '双'}"
        
        try:
            # 分析更多历史数据，提取组合模式
            # 增加分析的期数，从30期增加到50期
            patterns = []  # 存储历史开奖组合模式
            for record in raw_records[:50]:  # 分析最近50期
                try:
                    total_sum = int(record[4])
                    is_big = bool(record[5])
                    is_odd = bool(record[6])
                    
                    # 获取当前组合
                    current_combo = f"{'大' if is_big else '小'}{'单' if is_odd else '双'}"
                    patterns.append(current_combo)
                except (IndexError, ValueError, TypeError) as e:
                    logger.error(f"处理开奖记录失败: {e}, record: {record}")
                    continue
            
            if not patterns:
                logger.error("没有有效的开奖记录模式")
                return f"杀{'大' if random.random() < 0.5 else '小'}{'单' if random.random() < 0.5 else '双'}"
            
            # 定义所有可能的组合
            all_combos = ['大单', '大双', '小单', '小双']
            
            # 分析最近一期的组合
            latest_combo = patterns[0]
            
            # 统计每个组合的出现次数
            combo_counts = {combo: patterns.count(combo) for combo in all_combos}
            
            # 分析不同时间段的组合趋势
            recent_patterns = patterns[:10]  # 最近10期
            mid_patterns = patterns[10:30]   # 中期20期
            long_patterns = patterns[30:]    # 长期数据
            
            recent_combo_counts = {combo: recent_patterns.count(combo) for combo in all_combos}
            mid_combo_counts = {combo: mid_patterns.count(combo) if mid_patterns else 0 for combo in all_combos}
            long_combo_counts = {combo: long_patterns.count(combo) if long_patterns else 0 for combo in all_combos}
            
            # 分析组合的连续性和周期性
            combo_streaks = {}  # 记录每个组合的最长连续出现次数
            combo_gaps = {}     # 记录每个组合的最长间隔次数
            combo_last_pos = {} # 记录每个组合最后一次出现的位置
            combo_cycles = {}   # 记录每个组合的周期性
            
            # 初始化
            for combo in all_combos:
                combo_streaks[combo] = 0
                combo_gaps[combo] = 0
                combo_last_pos[combo] = -1
                combo_cycles[combo] = []
            
            # 分析连续性、间隔和周期性
            current_streaks = {combo: 0 for combo in all_combos}
            current_gaps = {combo: 0 for combo in all_combos}
            last_seen_pos = {combo: -1 for combo in all_combos}
            
            for i, combo in enumerate(patterns):
                # 更新当前组合的连续次数
                current_streaks[combo] += 1
                
                # 计算周期性
                if last_seen_pos[combo] >= 0:
                    cycle = i - last_seen_pos[combo]
                    combo_cycles[combo].append(cycle)
                last_seen_pos[combo] = i
                
                # 重置其他组合的连续次数
                for other_combo in all_combos:
                    if other_combo != combo:
                        current_streaks[other_combo] = 0
                        current_gaps[other_combo] += 1
                    else:
                        current_gaps[other_combo] = 0
                
                # 更新最长连续次数和间隔
                for c in all_combos:
                    combo_streaks[c] = max(combo_streaks[c], current_streaks[c])
                    combo_gaps[c] = max(combo_gaps[c], current_gaps[c])
                    if c == combo:
                        combo_last_pos[c] = i
            
            # 计算平均周期
            avg_cycles = {}
            for combo in all_combos:
                if combo_cycles[combo]:
                    avg_cycles[combo] = sum(combo_cycles[combo]) / len(combo_cycles[combo])
                else:
                    avg_cycles[combo] = 0
            
            # 分析组合之间的转换模式
            transition_matrix = {c1: {c2: 0 for c2 in all_combos} for c1 in all_combos}
            for i in range(len(patterns) - 1):
                current = patterns[i]
                next_combo = patterns[i + 1]
                transition_matrix[current][next_combo] += 1
            
            # 计算每个组合的权重 (考虑多种因素)
            combo_weights = {}
            for combo in all_combos:
                # 基础权重 - 出现频率 (出现次数越多权重越高)
                frequency_weight = combo_counts[combo] / len(patterns) if patterns else 0.25
                
                # 不同时间段的趋势权重
                recent_weight = recent_combo_counts[combo] / len(recent_patterns) if recent_patterns else 0.25
                mid_weight = mid_combo_counts[combo] / len(mid_patterns) if mid_patterns else 0.25
                long_weight = long_combo_counts[combo] / len(long_patterns) if long_patterns else 0.25
                
                # 趋势变化权重 (最近趋势与中期趋势的差异)
                trend_change = recent_weight - mid_weight
                
                # 连续性权重 (连续出现次数越多，越可能被杀)
                streak_weight = min(combo_streaks[combo] / 5, 1.0) if combo_streaks[combo] > 0 else 0
                
                # 间隔权重 (间隔越长，越不可能被杀)
                gap_weight = min(combo_gaps[combo] / 10, 1.0) if combo_gaps[combo] > 0 else 0
                
                # 最近出现位置权重 (越近期出现，权重越高)
                recency_weight = 0
                if combo_last_pos[combo] >= 0:
                    recency_weight = 1.0 - (combo_last_pos[combo] / len(patterns)) if len(patterns) > 0 else 0
                
                # 周期性权重 (如果当前处于周期性高点，权重增加)
                cycle_weight = 0
                if avg_cycles[combo] > 0:
                    current_pos = combo_last_pos[combo]
                    if current_pos >= 0:
                        periods_since_last = len(patterns) - 1 - current_pos
                        cycle_match = (periods_since_last % avg_cycles[combo]) / avg_cycles[combo]
                        cycle_weight = 1.0 - min(cycle_match, 1.0)  # 接近周期点时权重高
                
                # 转换概率权重 (基于上一期结果的转换概率)
                transition_weight = 0
                if latest_combo in transition_matrix:
                    total_transitions = sum(transition_matrix[latest_combo].values())
                    if total_transitions > 0:
                        transition_weight = transition_matrix[latest_combo][combo] / total_transitions
                
                # 最近一期权重 (降低对最近一期的依赖)
                latest_bonus = 0.05 if combo == latest_combo else 0
                
                # 综合权重计算 - 更加平衡的多因素分析
                combo_weights[combo] = (
                    frequency_weight * 0.15 +    # 历史频率 (降低权重)
                    recent_weight * 0.20 +       # 最近趋势
                    mid_weight * 0.10 +          # 中期趋势
                    long_weight * 0.05 +         # 长期趋势
                    trend_change * 0.10 +        # 趋势变化
                    streak_weight * 0.10 +       # 连续性
                    recency_weight * 0.10 +      # 最近出现
                    cycle_weight * 0.10 +        # 周期性
                    transition_weight * 0.05 +   # 转换概率
                    latest_bonus                 # 最近一期小加成 (降低权重)
                ) - (gap_weight * 0.05)          # 减去间隔权重 (降低权重)
                
                logger.debug(f"组合 {combo} 权重计算: 频率={frequency_weight:.2f}, 最近={recent_weight:.2f}, "
                           f"中期={mid_weight:.2f}, 长期={long_weight:.2f}, 趋势变化={trend_change:.2f}, "
                           f"连续={streak_weight:.2f}, 间隔={gap_weight:.2f}, 位置={recency_weight:.2f}, "
                           f"周期={cycle_weight:.2f}, 转换={transition_weight:.2f}, "
                           f"最新={latest_bonus}, 总权重={combo_weights[combo]:.2f}")
            
            # 根据权重排序组合
            sorted_combos = sorted(combo_weights.items(), key=lambda x: (-x[1], random.random()))
            logger.info(f"杀组权重排序: {sorted_combos}")
            
            # 选择权重最高的组合进行杀组
            if not sorted_combos:
                return f"杀{'大' if random.random() < 0.5 else '小'}{'单' if random.random() < 0.5 else '双'}"
                
            kill_combo = sorted_combos[0][0]  # 选择权重最高的组合
            
            # 添加一些变异，避免总是杀同一个组合
            if algo_num > 1 and random.random() < 0.3 and len(sorted_combos) > 1:
                # 有30%的概率选择第二高权重的组合
                kill_combo = sorted_combos[1][0]
                logger.info(f"变异算法选择了第二高权重的组合: {kill_combo}")
            
            # 如果算法3，有10%的概率完全随机选择
            if algo_num == 3 and random.random() < 0.1:
                kill_combo = random.choice(all_combos)
                logger.info(f"算法3随机选择了组合: {kill_combo}")
            
            # 增加额外的随机性
            # 如果过去10期同一个组合被杀过超过3次，有25%的概率选择完全不同的组合
            kill_history = patterns[:10]  # 最近10期
            kill_combo_count = 0
            for i, recent_kill in enumerate(kill_history):
                if i < 10 and recent_kill == kill_combo:
                    kill_combo_count += 1
            
            if kill_combo_count >= 3 and random.random() < 0.25:
                # 从其他组合中随机选择
                other_combos = [c for c in all_combos if c != kill_combo]
                if other_combos:
                    kill_combo = random.choice(other_combos)
                    logger.info(f"为避免重复，随机选择了不同组合: {kill_combo}")
            
            # 平衡机制：每隔一段时间（例如，每3-5次预测）随机选择最不常被选择的组合
            # 使用全局计数器（如果不存在则初始化）
            if not hasattr(BaseAlgorithms, 'kill_group_counter'):
                BaseAlgorithms.kill_group_counter = 0
            
            BaseAlgorithms.kill_group_counter += 1
            if BaseAlgorithms.kill_group_counter >= random.randint(3, 5):
                # 重置计数器
                BaseAlgorithms.kill_group_counter = 0
                # 选择最不常被选择的组合
                sorted_by_frequency = sorted(combo_counts.items(), key=lambda x: (x[1], random.random()))
                if sorted_by_frequency:
                    least_frequent = sorted_by_frequency[0][0]
                    # 有50%的概率选择最不常见的组合
                    if random.random() < 0.5:
                        kill_combo = least_frequent
                        logger.info(f"平衡机制选择了最不常见组合: {kill_combo}")
            
            return f"杀{kill_combo}"
            
        except Exception as e:
            logger.error(f"杀组预测失败: {e}")
            return f"杀{'大' if random.random() < 0.5 else '小'}{'单' if random.random() < 0.5 else '双'}" 