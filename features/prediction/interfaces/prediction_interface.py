"""
预测接口模块，提供标准化的预测接口
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger

class PredictionData:
    """预测数据类，标准化预测所需的数据结构"""
    
    def __init__(self, raw_records: List[Any]):
        """初始化
        
        Args:
            raw_records: 原始记录数据
        """
        self.raw_records = raw_records
        self.processed_data = self._process_raw_data()
        
    def _process_raw_data(self) -> Dict[str, Any]:
        """处理原始数据，转换为标准格式
        
        Returns:
            处理后的数据
        """
        processed = {
            'values': {},  # A、B、C值等
            'features': {},  # 特征值
            'metadata': {}  # 元数据
        }
        
        try:
            if not self.raw_records or len(self.raw_records) < 5:
                logger.warning("原始记录不足，无法完全处理")
                return processed
                
            # 提取元数据
            try:
                latest_record = self.raw_records[0]
                processed['metadata']['latest_qihao'] = latest_record[1]
                processed['metadata']['next_qihao'] = str(int(latest_record[1]) + 1)
            except (IndexError, ValueError) as e:
                logger.error(f"提取元数据失败: {e}")
            
            # 提取A、B、C值
            for i, record in enumerate(self.raw_records[:10]):
                try:
                    opennum = record[3]  # 开奖号码字段
                    
                    # 分割开奖号码
                    if '+' in opennum:
                        abc_values = opennum.split('+')
                        if len(abc_values) == 3:
                            processed['values'][f'A{i+1}'] = int(abc_values[0])
                            processed['values'][f'B{i+1}'] = int(abc_values[1])
                            processed['values'][f'C{i+1}'] = int(abc_values[2])
                        else:
                            logger.warning(f"开奖号码格式错误: {opennum}")
                except (IndexError, ValueError) as e:
                    logger.warning(f"处理记录 {i} 失败: {e}")
                    continue
            
            # 提取特征数据 - 大小比例
            big_count = 0
            for record in self.raw_records[:20]:
                try:
                    is_big = bool(record[5])
                    if is_big:
                        big_count += 1
                except (IndexError, ValueError):
                    continue
                    
            processed['features']['big_ratio'] = big_count / min(20, len(self.raw_records))
            
            # 提取特征数据 - 单双比例
            odd_count = 0
            for record in self.raw_records[:20]:
                try:
                    is_odd = bool(record[6])
                    if is_odd:
                        odd_count += 1
                except (IndexError, ValueError):
                    continue
                    
            processed['features']['odd_ratio'] = odd_count / min(20, len(self.raw_records))
            
            # 提取特征数据 - 组合类型分布
            combo_counts = {"豹子": 0, "对子": 0, "顺子": 0, "杂六": 0}
            for record in self.raw_records[:20]:
                try:
                    combo_type = record[7]
                    if combo_type in combo_counts:
                        combo_counts[combo_type] += 1
                except (IndexError, ValueError):
                    continue
                    
            for combo, count in combo_counts.items():
                processed['features'][f'{combo}_ratio'] = count / min(20, len(self.raw_records))
                
        except Exception as e:
            logger.error(f"处理原始数据失败: {e}")
            
        return processed
    
    def get_values(self) -> Dict[str, int]:
        """获取A、B、C值
        
        Returns:
            A、B、C值字典
        """
        return self.processed_data['values']
    
    def get_features(self) -> Dict[str, float]:
        """获取特征值
        
        Returns:
            特征值字典
        """
        return self.processed_data['features']
    
    def get_metadata(self) -> Dict[str, Any]:
        """获取元数据
        
        Returns:
            元数据字典
        """
        return self.processed_data['metadata']
    
    def get_raw_records(self) -> List[Any]:
        """获取原始记录
        
        Returns:
            原始记录列表
        """
        return self.raw_records

class PredictionResult:
    """预测结果类，标准化预测结果的数据结构"""
    
    def __init__(self, 
                 qihao: str, 
                 prediction: str, 
                 prediction_type: str,
                 algorithm_used: Any,
                 confidence_score: float = 0.5,
                 switch_info: Optional[Dict[str, Any]] = None):
        """初始化
        
        Args:
            qihao: 期号
            prediction: 预测内容
            prediction_type: 预测类型
            algorithm_used: 使用的算法
            confidence_score: 置信度
            switch_info: 算法切换信息
        """
        self.qihao = qihao
        self.prediction = prediction
        self.prediction_type = prediction_type
        self.algorithm_used = algorithm_used
        self.confidence_score = confidence_score
        self.switch_info = switch_info
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典
        
        Returns:
            字典表示
        """
        return {
            'qihao': self.qihao,
            'prediction': self.prediction,
            'prediction_type': self.prediction_type,
            'algorithm_used': self.algorithm_used,
            'confidence_score': self.confidence_score,
            'switch_info': self.switch_info
        }

class PredictionInterface(ABC):
    """预测接口抽象类，定义预测的标准接口"""
    
    @abstractmethod
    def predict(self, 
               data: PredictionData, 
               prediction_type: str, 
               **kwargs) -> PredictionResult:
        """进行预测
        
        Args:
            data: 预测数据
            prediction_type: 预测类型
            **kwargs: 其他参数
            
        Returns:
            预测结果
        """
        pass
    
    @abstractmethod
    def verify_prediction(self, 
                         prediction: PredictionResult, 
                         actual_data: Dict[str, Any]) -> Tuple[bool, float]:
        """验证预测
        
        Args:
            prediction: 预测结果
            actual_data: 实际结果数据
            
        Returns:
            (是否正确, 偏差值)
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def get_model_status(self) -> Dict[str, Any]:
        """获取模型状态
        
        Returns:
            模型状态信息
        """
        pass 