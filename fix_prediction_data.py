#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
预测数据修复工具
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
        logging.FileHandler('fix_prediction.log')
    ]
)
logger = logging.getLogger('fix_prediction')

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

def check_prediction_tables(conn):
    """检查预测相关的表"""
    try:
        cursor = conn.cursor()
        
        # 检查algorithm_performance表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='algorithm_performance'")
        if cursor.fetchone():
            logger.info("algorithm_performance表存在")
            
            # 检查该表中的数据
            cursor.execute("SELECT COUNT(*) FROM algorithm_performance")
            count = cursor.fetchone()[0]
            logger.info(f"algorithm_performance表中有{count}条记录")
            
            if count > 0:
                cursor.execute("SELECT * FROM algorithm_performance")
                rows = cursor.fetchall()
                for row in rows:
                    prediction_type = row['prediction_type']
                    algorithm_number = row['algorithm_number']
                    success_rate = row['success_rate']
                    logger.info(f"算法性能: {prediction_type} - 算法{algorithm_number} - 成功率{success_rate}")
        else:
            logger.warning("algorithm_performance表不存在")
            
        # 检查algorithm_switch表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='algorithm_switch'")
        if cursor.fetchone():
            logger.info("algorithm_switch表存在")
        else:
            logger.warning("algorithm_switch表不存在")
            
        # 检查algorithm_performance_full表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='algorithm_performance_full'")
        if cursor.fetchone():
            logger.info("algorithm_performance_full表存在")
            
            # 检查该表中的数据
            cursor.execute("SELECT COUNT(*) FROM algorithm_performance_full")
            count = cursor.fetchone()[0]
            logger.info(f"algorithm_performance_full表中有{count}条记录")
        else:
            logger.warning("algorithm_performance_full表不存在")
            
        return True
    except Exception as e:
        logger.error(f"检查预测表失败: {e}")
        return False

def init_prediction_tables(conn):
    """初始化预测数据表"""
    try:
        cursor = conn.cursor()
        
        # 创建算法性能表
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
        
        # 创建算法切换表
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
        
        # 创建完整算法性能表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS algorithm_performance_full (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_type TEXT,
                performance_data TEXT,
                updated_at TIMESTAMP,
                UNIQUE(prediction_type)
            )
        """)
        
        # 提交事务
        conn.commit()
        logger.info("预测数据表初始化成功")
        return True
    except Exception as e:
        logger.error(f"初始化预测数据表失败: {e}")
        return False

def init_default_algorithm_data(conn):
    """初始化默认算法数据"""
    try:
        cursor = conn.cursor()
        
        # 预测类型
        prediction_types = ['single_double', 'big_small', 'kill_group', 'double_group']
        
        # 初始化每种预测类型的三种算法
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
                    logger.info(f"初始化默认算法数据: {pred_type} - 算法{algo_num}")
        
        # 初始化完整性能数据
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
                logger.info(f"初始化默认完整算法数据: {pred_type}")
        
        # 提交事务
        conn.commit()
        logger.info("默认算法数据初始化成功")
        return True
    except Exception as e:
        logger.error(f"初始化默认算法数据失败: {e}")
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
        
        # 检查预测表
        if not check_prediction_tables(conn):
            logger.warning("预测表检查失败，尝试初始化...")
            
            # 初始化预测表
            if not init_prediction_tables(conn):
                logger.error("初始化预测表失败，退出")
                return False
        
        # 初始化默认算法数据
        if not init_default_algorithm_data(conn):
            logger.error("初始化默认算法数据失败")
        
        # 关闭数据库连接
        conn.close()
        
        logger.info("预测数据检查和修复完成")
        return True
    except Exception as e:
        logger.error(f"检查和修复预测数据失败: {e}")
        return False

if __name__ == "__main__":
    sys.exit(0 if main() else 1) 