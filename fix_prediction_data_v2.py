#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
预测数据修复工具v2
用于检查和修复预测算法数据，特别是宝塔环境中的问题
"""

import os
import sys
import json
import sqlite3
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('fix_prediction_v2.log')
    ]
)
logger = logging.getLogger('fix_prediction_v2')

# 检查系统环境
is_bt = os.path.exists('/www/server/panel/class')
logger.info(f"宝塔环境: {'是' if is_bt else '否'}")
logger.info(f"当前工作目录: {os.getcwd()}")

# 数据库路径
DB_PATH = os.environ.get('DB_PATH', 'lottery.db')
if not os.path.exists(DB_PATH):
    if is_bt:
        # 宝塔环境默认路径
        DB_PATH = '/www/wwwroot/fenxi28/lottery.db'
    else:
        # 本地默认路径
        DB_PATH = 'lottery.db'

logger.info(f"使用数据库路径: {DB_PATH}")

def check_db_permissions():
    """检查数据库文件权限"""
    try:
        if os.path.exists(DB_PATH):
            can_read = os.access(DB_PATH, os.R_OK)
            can_write = os.access(DB_PATH, os.W_OK)
            logger.info(f"数据库文件权限: 可读={can_read}, 可写={can_write}")
            
            if not can_read or not can_write:
                logger.warning("数据库文件权限不足，尝试修复...")
                try:
                    if is_bt:
                        # 在宝塔环境中修复权限
                        os.system(f"chmod 666 {DB_PATH}")
                        logger.info("已尝试修复权限")
                    else:
                        logger.warning("非宝塔环境，无法自动修复权限")
                except Exception as e:
                    logger.error(f"修复权限失败: {e}")
        else:
            logger.warning(f"数据库文件不存在: {DB_PATH}")
    except Exception as e:
        logger.error(f"检查数据库权限失败: {e}")

def connect_db():
    """连接到数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        logger.info("数据库连接成功")
        return conn
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return None

def check_table_exists(conn, table_name):
    """检查表是否存在"""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None

def create_algorithm_performance_table(conn):
    """创建算法性能表"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS algorithm_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_type TEXT,
                algorithm_number INTEGER,
                success_count INTEGER DEFAULT 0,
                total_count INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0.5,
                updated_at TIMESTAMP,
                UNIQUE(prediction_type, algorithm_number)
            )
        """)
        conn.commit()
        logger.info("创建/确认 algorithm_performance 表成功")
        return True
    except Exception as e:
        logger.error(f"创建 algorithm_performance 表失败: {e}")
        return False

def create_algorithm_switch_table(conn):
    """创建算法切换表"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS algorithm_switch (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_type TEXT,
                from_algorithm INTEGER,
                to_algorithm INTEGER,
                switch_reason TEXT,
                switch_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        logger.info("创建/确认 algorithm_switch 表成功")
        return True
    except Exception as e:
        logger.error(f"创建 algorithm_switch 表失败: {e}")
        return False

def create_algorithm_performance_full_table(conn):
    """创建完整算法性能表"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS algorithm_performance_full (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_type TEXT,
                performance_data TEXT,
                updated_at TIMESTAMP,
                UNIQUE(prediction_type)
            )
        """)
        conn.commit()
        logger.info("创建/确认 algorithm_performance_full 表成功")
        return True
    except Exception as e:
        logger.error(f"创建 algorithm_performance_full 表失败: {e}")
        return False

def create_algorithm_performance_details_table(conn):
    """创建算法性能详情表"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS algorithm_performance_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_type TEXT NOT NULL,
                performance_data TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(prediction_type)
            )
        """)
        conn.commit()
        logger.info("创建/确认 algorithm_performance_details 表成功")
        return True
    except Exception as e:
        logger.error(f"创建 algorithm_performance_details 表失败: {e}")
        return False

def init_algorithm_performance_data(conn):
    """初始化algorithm_performance表数据"""
    try:
        cursor = conn.cursor()
        
        # 预测类型
        prediction_types = ['single_double', 'big_small', 'kill_group', 'double_group']
        
        for pred_type in prediction_types:
            for algo_num in [1, 2, 3]:
                # 检查是否已存在
                cursor.execute(
                    "SELECT id FROM algorithm_performance WHERE prediction_type = ? AND algorithm_number = ?",
                    (pred_type, algo_num)
                )
                
                if not cursor.fetchone():
                    # 插入默认数据
                    cursor.execute(
                        """
                        INSERT INTO algorithm_performance 
                        (prediction_type, algorithm_number, success_count, total_count, success_rate, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (pred_type, algo_num, 50, 100, 0.5, datetime.now().isoformat())
                    )
                    conn.commit()
                    logger.info(f"初始化 algorithm_performance 表默认数据: {pred_type} - 算法{algo_num}")
                else:
                    logger.info(f"algorithm_performance 表已存在数据: {pred_type} - 算法{algo_num}")
        
        return True
    except Exception as e:
        logger.error(f"初始化 algorithm_performance 表数据失败: {e}")
        return False

def init_algorithm_performance_full_data(conn):
    """初始化algorithm_performance_full表数据"""
    try:
        cursor = conn.cursor()
        
        # 预测类型
        prediction_types = ['single_double', 'big_small', 'kill_group', 'double_group']
        
        for pred_type in prediction_types:
            # 检查是否已存在
            cursor.execute(
                "SELECT id FROM algorithm_performance_full WHERE prediction_type = ?",
                (pred_type,)
            )
            
            if not cursor.fetchone():
                # 创建默认算法性能数据
                performance_data = {
                    'current_algorithm': 1,
                    'algorithms': {
                        '1': {
                            'total_predictions': 100,
                            'correct_predictions': 50,
                            'success_rate': 0.5,
                            'recent_results': [],
                            'recent_success_rate': 0.5,
                            'confidence_score': 0.5,
                            'consecutive_correct': 0,
                            'consecutive_wrong': 0,
                            'last_switch_time': 0
                        },
                        '2': {
                            'total_predictions': 100,
                            'correct_predictions': 50,
                            'success_rate': 0.5,
                            'recent_results': [],
                            'recent_success_rate': 0.5,
                            'confidence_score': 0.5,
                            'consecutive_correct': 0,
                            'consecutive_wrong': 0,
                            'last_switch_time': 0
                        },
                        '3': {
                            'total_predictions': 100,
                            'correct_predictions': 50,
                            'success_rate': 0.5,
                            'recent_results': [],
                            'recent_success_rate': 0.5,
                            'confidence_score': 0.5,
                            'consecutive_correct': 0,
                            'consecutive_wrong': 0,
                            'last_switch_time': 0
                        }
                    },
                    'updated_at': datetime.now().isoformat()
                }
                
                # 插入默认数据
                cursor.execute(
                    """
                    INSERT INTO algorithm_performance_full 
                    (prediction_type, performance_data, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (pred_type, json.dumps(performance_data), datetime.now().isoformat())
                )
                conn.commit()
                logger.info(f"初始化 algorithm_performance_full 表默认数据: {pred_type}")
            else:
                logger.info(f"algorithm_performance_full 表已存在数据: {pred_type}")
        
        return True
    except Exception as e:
        logger.error(f"初始化 algorithm_performance_full 表数据失败: {e}")
        return False

def migrate_data_if_needed(conn):
    """如果需要，从algorithm_performance表迁移数据到algorithm_performance_full表"""
    try:
        cursor = conn.cursor()
        
        # 检查是否存在algorithm_performance表
        if not check_table_exists(conn, 'algorithm_performance'):
            logger.warning("algorithm_performance表不存在，无法迁移数据")
            return False
        
        # 检查algorithm_performance_full表
        if not check_table_exists(conn, 'algorithm_performance_full'):
            logger.warning("algorithm_performance_full表不存在，无法迁移数据")
            return False
        
        # 预测类型
        prediction_types = ['single_double', 'big_small', 'kill_group', 'double_group']
        
        for pred_type in prediction_types:
            # 检查algorithm_performance_full表是否已有该预测类型的数据
            cursor.execute(
                "SELECT id FROM algorithm_performance_full WHERE prediction_type = ?",
                (pred_type,)
            )
            
            if cursor.fetchone():
                # 已存在，跳过
                logger.info(f"algorithm_performance_full表已存在{pred_type}的数据，跳过迁移")
                continue
                
            # 从algorithm_performance表获取数据
            cursor.execute(
                "SELECT algorithm_number, success_count, total_count, success_rate FROM algorithm_performance WHERE prediction_type = ?",
                (pred_type,)
            )
            
            algo_data = cursor.fetchall()
            if not algo_data:
                logger.warning(f"algorithm_performance表中没有{pred_type}的数据，跳过迁移")
                continue
                
            # 创建算法性能数据
            performance_data = {
                'current_algorithm': 1,  # 默认使用算法1
                'algorithms': {},
                'updated_at': datetime.now().isoformat()
            }
            
            # 填充算法数据
            for row in algo_data:
                algo_num = row['algorithm_number']
                success_count = row['success_count']
                total_count = row['total_count']
                success_rate = row['success_rate']
                
                # 如果成功率比当前算法更高，更新当前算法
                if success_rate > 0.55 and success_rate > performance_data.get('algorithms', {}).get('1', {}).get('success_rate', 0):
                    performance_data['current_algorithm'] = algo_num
                
                # 添加算法数据
                performance_data['algorithms'][str(algo_num)] = {
                    'total_predictions': total_count,
                    'correct_predictions': int(total_count * success_rate),
                    'success_rate': success_rate,
                    'recent_results': [],
                    'recent_success_rate': success_rate,
                    'confidence_score': 0.5,
                    'consecutive_correct': 0,
                    'consecutive_wrong': 0,
                    'last_switch_time': 0
                }
            
            # 插入数据
            cursor.execute(
                """
                INSERT OR REPLACE INTO algorithm_performance_full 
                (prediction_type, performance_data, updated_at)
                VALUES (?, ?, ?)
                """,
                (pred_type, json.dumps(performance_data), datetime.now().isoformat())
            )
            conn.commit()
            logger.info(f"成功将{pred_type}的数据从algorithm_performance迁移到algorithm_performance_full")
        
        return True
    except Exception as e:
        logger.error(f"迁移数据失败: {e}")
        return False

def check_prediction_tables(conn):
    """检查预测相关表是否存在"""
    cursor = conn.cursor()
    tables = [
        "algorithm_performance", 
        "algorithm_switch", 
        "algorithm_performance_full", 
        "algorithm_performance_details"
    ]
    
    # 修改检查方式，记录所有不存在的表
    missing_tables = []
    for table in tables:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if not cursor.fetchone():
            missing_tables.append(table)
            logger.warning(f"表 {table} 不存在")
        else:
            # 获取表记录数
            try:
                cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                count = cursor.fetchone()['count']
                logger.info(f"表 {table} 存在，包含 {count} 条记录")
            except Exception as e:
                logger.error(f"检查表 {table} 记录数失败: {e}")
    
    if missing_tables:
        logger.warning(f"以下表不存在: {', '.join(missing_tables)}")
        return False, missing_tables
    else:
        logger.info("所有预测相关表均已存在")
        return True, []

def fix_algorithm_data_format(conn):
    """修复算法数据格式，特别是last_save_time相关问题"""
    try:
        cursor = conn.cursor()
        
        # 查询现有的algorithm_performance_full和algorithm_performance_details表数据
        for table in ["algorithm_performance_full", "algorithm_performance_details"]:
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            
            for row in rows:
                pred_type = row['prediction_type']
                try:
                    # 解析性能数据
                    perf_data = json.loads(row['performance_data'])
                    
                    # 确保有current_algorithm字段
                    if 'current_algorithm' not in perf_data:
                        perf_data['current_algorithm'] = 1
                        logger.info(f"修复 {pred_type} 的current_algorithm字段")
                    
                    # 确保有algorithms字段和正确的算法数据
                    if 'algorithms' not in perf_data or not isinstance(perf_data['algorithms'], dict):
                        perf_data['algorithms'] = {}
                        logger.info(f"修复 {pred_type} 的algorithms字段")
                    
                    # 确保每种算法都有正确的字段
                    for algo_num in [1, 2, 3]:
                        algo_key = str(algo_num)
                        if algo_key not in perf_data['algorithms']:
                            perf_data['algorithms'][algo_key] = {
                                'total_predictions': 100,
                                'correct_predictions': 50,
                                'success_rate': 0.5,
                                'recent_results': [],
                                'recent_success_rate': 0.5,
                                'confidence_score': 0.5,
                                'consecutive_correct': 0,
                                'consecutive_wrong': 0,
                                'last_switch_time': 0
                            }
                            logger.info(f"为 {pred_type} 添加缺失的算法{algo_num}数据")
                        else:
                            # 确保每个算法有所有必要的字段
                            algo_data = perf_data['algorithms'][algo_key]
                            required_fields = [
                                'total_predictions', 'correct_predictions', 'success_rate',
                                'recent_results', 'recent_success_rate', 'confidence_score',
                                'consecutive_correct', 'consecutive_wrong', 'last_switch_time'
                            ]
                            
                            for field in required_fields:
                                if field not in algo_data:
                                    if field == 'recent_results':
                                        algo_data[field] = []
                                    elif field in ['success_rate', 'recent_success_rate', 'confidence_score']:
                                        algo_data[field] = 0.5
                                    elif field == 'last_switch_time':
                                        algo_data[field] = 0
                                    else:
                                        algo_data[field] = 0
                                    logger.info(f"为 {pred_type} 算法{algo_num}添加缺失的{field}字段")
                    
                    # 更新数据
                    cursor.execute(
                        f"UPDATE {table} SET performance_data = ?, updated_at = ? WHERE prediction_type = ?",
                        (json.dumps(perf_data), datetime.now().isoformat(), pred_type)
                    )
                    conn.commit()
                    logger.info(f"已修复 {table} 表中 {pred_type} 的数据格式")
                    
                except Exception as e:
                    logger.error(f"修复 {table} 表中 {pred_type} 的数据格式失败: {e}")
        
        return True
    except Exception as e:
        logger.error(f"修复算法数据格式失败: {e}")
        return False

def fix_predictor_model_attributes():
    """检查并修复PredictorModel中的last_save_time属性问题"""
    try:
        # 导入模块 (在函数内部导入以避免全局依赖)
        import sys
        import importlib
        from pathlib import Path
        
        # 添加features目录到系统路径
        features_path = Path.cwd() / 'features'
        if features_path.exists() and features_path.is_dir():
            sys.path.append(str(features_path.parent))
            logger.info(f"已添加 {features_path.parent} 到系统路径")
        else:
            logger.warning(f"未找到features目录: {features_path}")
            return False
            
        try:
            # 导入PredictorModel类
            from features.prediction.models.predictor_model import PredictorModel
            
            # 检查类定义中是否包含last_save_time初始化
            import inspect
            source = inspect.getsource(PredictorModel.__init__)
            
            if "self.last_save_time = datetime.now()" in source:
                logger.info("PredictorModel.__init__已包含last_save_time初始化")
                return True
                
            # 如果没有找到初始化代码，尝试修改文件
            predictor_model_path = Path.cwd() / 'features' / 'prediction' / 'models' / 'predictor_model.py'
            if not predictor_model_path.exists():
                logger.warning(f"未找到predictor_model.py文件: {predictor_model_path}")
                return False
                
            # 读取文件内容
            content = predictor_model_path.read_text(encoding='utf-8')
            
            # 检查是否已经包含初始化代码
            if "self.last_save_time = datetime.now()" in content:
                logger.info("文件中已包含last_save_time初始化代码")
                
                # 检查save_algorithm_performance方法是否正确处理last_save_time
                if "if not hasattr(self, 'last_save_time'):" not in content:
                    # 修改save_algorithm_performance方法
                    import re
                    save_method_pattern = r"def save_algorithm_performance\(self, force=False\):(.*?)try:"
                    save_method_replacement = r"""def save_algorithm_performance(self, force=False):
        # 确保last_save_time属性存在
        if not hasattr(self, 'last_save_time'):
            self.last_save_time = datetime.now()
            
        # 检查是否需要保存
        now = datetime.now()
        elapsed = (now - self.last_save_time).total_seconds()
        
        if not force and elapsed < self.save_interval:
            return
            
        try:"""
                    
                    # 使用正则表达式替换
                    new_content = re.sub(save_method_pattern, save_method_replacement, content, flags=re.DOTALL)
                    
                    if new_content != content:
                        # 备份原文件
                        backup_path = predictor_model_path.with_suffix('.py.bak')
                        predictor_model_path.rename(backup_path)
                        logger.info(f"已备份原文件到: {backup_path}")
                        
                        # 写入新内容
                        predictor_model_path.write_text(new_content, encoding='utf-8')
                        logger.info("已修复save_algorithm_performance方法")
                        
                        # 重新加载模块
                        if 'features.prediction.models.predictor_model' in sys.modules:
                            importlib.reload(sys.modules['features.prediction.models.predictor_model'])
                            logger.info("已重新加载predictor_model模块")
                        
                        return True
                    else:
                        logger.warning("无法修改save_algorithm_performance方法")
                else:
                    logger.info("save_algorithm_performance方法已包含last_save_time检查")
                    return True
            else:
                # 在__init__方法中添加last_save_time初始化
                init_pattern = r"([ \t]+# 性能数据保存间隔 \(秒\)\n[ \t]+self\.save_interval = \d+.*?\n)"
                init_replacement = r"\1        # 最后一次保存性能数据的时间\n        self.last_save_time = datetime.now()\n"
                
                import re
                new_content = re.sub(init_pattern, init_replacement, content)
                
                if new_content != content:
                    # 备份原文件
                    backup_path = predictor_model_path.with_suffix('.py.bak')
                    predictor_model_path.rename(backup_path)
                    logger.info(f"已备份原文件到: {backup_path}")
                    
                    # 写入新内容
                    predictor_model_path.write_text(new_content, encoding='utf-8')
                    logger.info("已添加last_save_time初始化代码")
                    
                    # 重新加载模块
                    if 'features.prediction.models.predictor_model' in sys.modules:
                        importlib.reload(sys.modules['features.prediction.models.predictor_model'])
                        logger.info("已重新加载predictor_model模块")
                    
                    return True
                else:
                    logger.warning("无法添加last_save_time初始化代码")
                    return False
                
        except ImportError as e:
            logger.error(f"导入PredictorModel失败: {e}")
            return False
        except Exception as e:
            logger.error(f"检查PredictorModel类失败: {e}")
            return False
            
    except Exception as e:
        logger.error(f"修复PredictorModel属性失败: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return False

def main():
    """主函数"""
    try:
        logger.info("开始检查和修复预测数据...")
        
        # 检查数据库权限
        check_db_permissions()
        
        # 连接数据库
        conn = connect_db()
        if not conn:
            logger.error("无法连接数据库，退出")
            return False
        
        # 首先创建所有必要的表
        logger.info("确保必要的表存在...")
        create_algorithm_performance_table(conn)
        create_algorithm_switch_table(conn)
        create_algorithm_performance_full_table(conn)
        create_algorithm_performance_details_table(conn)
        
        # 然后初始化表数据
        logger.info("初始化表数据...")
        init_algorithm_performance_data(conn)
        init_algorithm_performance_full_data(conn)
        
        # 如果需要，迁移数据
        logger.info("检查是否需要迁移数据...")
        migrate_data_if_needed(conn)
        
        # 检查预测相关表
        logger.info("检查预测相关表...")
        check_prediction_tables(conn)
        
        # 修复算法数据格式
        logger.info("修复算法数据格式...")
        fix_algorithm_data_format(conn)
        
        # 修复PredictorModel属性
        logger.info("修复PredictorModel属性...")
        fix_predictor_model_attributes()
        
        # 关闭数据库连接
        conn.close()
        
        logger.info("预测数据检查和修复完成")
        return True
    except Exception as e:
        logger.error(f"检查和修复预测数据失败: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    sys.exit(0 if main() else 1) 