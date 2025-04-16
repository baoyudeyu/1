import json
import random
from datetime import datetime
from loguru import logger

class AlgorithmLibrary:
    def __init__(self):
        self.MAX_ALGORITHMS = 10  # 每种预测类型最多存储10个算法
        self.libraries = {
            'single_double': [],
            'big_small': [],
            'kill_group': [],
            'double_group': []
        }
        self.performance_history = {
            'single_double': {},
            'big_small': {},
            'kill_group': {},
            'double_group': {}
        }
        # 算法模板，用于生成新算法，每个模板都会生成0-9的尾数
        self.algorithm_templates = {
            'basic': [
                # 基础模板 - 单数字运算
                'get_last_digit(A1*A1+A1)',
                'get_last_digit(B1*B1+B1)',
                'get_last_digit(C1*C1+C1)',
                'get_last_digit((A1+A2+A3)%10)',
                'get_last_digit((B1+B2+B3)%10)',
                'get_last_digit((C1+C2+C3)%10)',
                'get_last_digit(abs(A1-A5+A10))',
                'get_last_digit(abs(B1-B5+B10))',
                'get_last_digit(abs(C1-C5+C10))',
                'get_last_digit((A1+A3+A5+A7)%10)',
                'get_last_digit((B1+B3+B5+B7)%10)',
                'get_last_digit((C1+C3+C5+C7)%10)',
                # 新增基础模板
                'get_last_digit((A1+B1+C1)/3)',
                'get_last_digit((A1*2+B1+C1)/3)',
                'get_last_digit((A1+B1*2+C1)/3)',
                'get_last_digit((A1+B1+C1*2)/3)'
            ],
            'advanced': [
                # 高级模板 - 跨数字运算
                'get_last_digit(A1*B1+C1)',
                'get_last_digit(B1*C1+A1)',
                'get_last_digit(C1*A1+B1)',
                'get_last_digit((A1+B2+C3)%10)',
                'get_last_digit((B1+C2+A3)%10)',
                'get_last_digit((C1+A2+B3)%10)',
                'get_last_digit(abs(A1-B5+C10))',
                'get_last_digit(abs(B1-C5+A10))',
                'get_last_digit(abs(C1-A5+B10))',
                'get_last_digit((A1+B3+C5+A7)%10)',
                'get_last_digit((B1+C3+A5+B7)%10)',
                'get_last_digit((C1+A3+B5+C7)%10)',
                # 新增高级模板
                'get_last_digit((A1*B1+B1*C1+C1*A1)/3)',
                'get_last_digit(abs(A1-B1)*C1%10)',
                'get_last_digit((A1+B1+C1)*abs(A2-B2)%10)',
                'get_last_digit((A1*A2+B1*B2+C1*C2)/3)'
            ],
            'complex': [
                # 复杂模板 - 多期组合运算
                'get_last_digit((A1+A2)*A3+(A5+A7)%10)',
                'get_last_digit((B1+B2)*B3+(B5+B7)%10)',
                'get_last_digit((C1+C2)*C3+(C5+C7)%10)',
                'get_last_digit(abs((A1+B2)*(C3+A4))%10)',
                'get_last_digit(abs((B1+C2)*(A3+B4))%10)',
                'get_last_digit(abs((C1+A2)*(B3+C4))%10)',
                'get_last_digit((A1+A5+A10)*(B1+B5+B10)%10)',
                'get_last_digit((B1+B5+B10)*(C1+C5+C10)%10)',
                'get_last_digit((C1+C5+C10)*(A1+A5+A10)%10)',
                'get_last_digit(abs(A1-A3+A5-A7+A9))',
                'get_last_digit(abs(B1-B3+B5-B7+B9))',
                'get_last_digit(abs(C1-C3+C5-C7+C9))',
                # 新增复杂模板
                'get_last_digit(((A1+B1+C1)*(A2+B2+C2)*(A3+B3+C3))%10)',
                'get_last_digit(abs((A1-A5)*(B1-B5)*(C1-C5))%10)',
                'get_last_digit((A1*B2*C3 + A3*B2*C1)/5%10)',
                'get_last_digit(abs((A1+A2+A3)-(B1+B2+B3)+(C1+C2+C3))%10)'
            ]
        }

    def generate_algorithm(self, pred_type):
        """生成新算法，确保结果是三个0-9之间的尾数相加"""
        def create_formula():
            # 从每种复杂度中选择一个公式，并确保使用不同的数据组合
            formulas = []
            used_numbers = set()  # 用于追踪已使用的数字
            
            # 预先过滤可用公式
            available_templates = {
                complexity: [f for f in self.algorithm_templates[complexity]]
                for complexity in ['basic', 'advanced', 'complex']
            }
            
            for complexity in ['basic', 'advanced', 'complex']:
                # 过滤出未使用相同数字的公式
                valid_formulas = [f for f in available_templates[complexity]
                               if not any(num in f for num in used_numbers)]
                
                if not valid_formulas:  # 如果没有可用公式，使用所有公式
                    valid_formulas = available_templates[complexity]
                
                term = random.choice(valid_formulas)
                
                # 记录使用的数字
                for i in range(1, 11):
                    for letter in ['A', 'B', 'C']:
                        if f'{letter}{i}' in term:
                            used_numbers.add(f'{letter}{i}')
                
                formulas.append(term)
            
            # 将三个公式组合起来
            return " + ".join(formulas)
        
        # 生成新算法
        formula = create_formula()
        algorithm = {
            'id': len(self.libraries[pred_type]) + 1,
            'formula': formula,
            'created_at': datetime.now(),
            'success_rate': 0.5,
            'usage_count': 0,
            'last_success_rate': 0.5
        }
        
        return algorithm

    def add_algorithm(self, pred_type, algorithm):
        """添加新算法到库中"""
        if len(self.libraries[pred_type]) >= self.MAX_ALGORITHMS:
            # 移除表现最差的算法
            self.remove_worst_algorithm(pred_type)
        
        self.libraries[pred_type].append(algorithm)
        self.performance_history[pred_type][algorithm['id']] = []

    def remove_worst_algorithm(self, pred_type):
        """移除表现最差的算法"""
        worst_algo = min(self.libraries[pred_type], 
                        key=lambda x: x['success_rate'])
        self.libraries[pred_type].remove(worst_algo)
        del self.performance_history[pred_type][worst_algo['id']]

    def update_algorithm_performance(self, pred_type, algo_id, is_correct):
        """更新算法性能统计"""
        for algo in self.libraries[pred_type]:
            if algo['id'] == algo_id:
                algo['usage_count'] += 1
                history = self.performance_history[pred_type][algo_id]
                history.append(1 if is_correct else 0)
                
                # 只保留最近50次预测结果
                if len(history) > 50:
                    history.pop(0)
                
                # 更新成功率，使用加权平均，最近的结果权重更大
                weights = [1 + i/50 for i in range(len(history))]
                weighted_sum = sum(h * w for h, w in zip(history, weights))
                total_weight = sum(weights)
                
                algo['last_success_rate'] = algo['success_rate']
                algo['success_rate'] = weighted_sum / total_weight
                
                # 记录更新时间
                algo['last_updated'] = datetime.now()
                break

    def get_best_algorithms(self, pred_type, top_n=3):
        """获取最佳算法"""
        sorted_algos = sorted(self.libraries[pred_type],
                            key=lambda x: x['success_rate'],
                            reverse=True)
        return sorted_algos[:top_n]

    def get_algorithm_status(self):
        """获取算法库状态"""
        status = {}
        for pred_type in ['single_double', 'big_small', 'kill_group', 'double_group']:
            algorithms = self.libraries[pred_type]
            
            # 获取算法总数
            total_algorithms = len(algorithms)
            
            # 获取最佳算法（按成功率排序）
            sorted_algorithms = sorted(
                algorithms,
                key=lambda x: (x['success_rate'], -x['usage_count']),  # 首先按成功率，然后按使用次数（倒序）
                reverse=True
            )
            
            # 获取TOP3算法
            best_algorithms = []
            for algo in sorted_algorithms[:3]:
                best_algorithms.append({
                    'id': algo['id'],
                    'formula': algo['formula'],
                    'success_rate': algo['success_rate'],
                    'usage_count': algo['usage_count'],
                    'last_success_rate': algo['last_success_rate']
                })
            
            status[pred_type] = {
                'total_algorithms': total_algorithms,
                'best_algorithms': best_algorithms
            }
        
        return status 