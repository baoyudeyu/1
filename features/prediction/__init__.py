"""
预测模块包，提供各种预测功能
"""
from features.prediction.models.predictor_model import PredictorModel
from features.prediction.algorithms.algorithm_library import AlgorithmLibrary

# 创建预测器实例
predictor = PredictorModel()
algorithm_library = AlgorithmLibrary()

__all__ = ['predictor', 'algorithm_library']