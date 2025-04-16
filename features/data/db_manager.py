import sqlite3
from datetime import datetime
from loguru import logger
import os
import time
import json

from ..config.config_manager import DB_CONFIG, GAME_CONFIG

class DBManager:
    """数据库管理类，提供数据库操作的封装"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super(DBManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path=None):
        """初始化数据库管理器"""
        try:
            # 设置数据库路径
            self.db_path = db_path or DB_CONFIG.get("db_path", "lottery.db")
            self.conn = None
            
            # 尝试连接数据库
            self.connect()
        except Exception as e:
            logger.error(f"初始化数据库管理器失败: {e}")
            self.conn = None
    
    def create_tables(self):
        """创建数据库表（兼容旧代码）"""
        return self._init_tables()
    
    def connect(self):
        """连接到数据库"""
        try:
            # 确保数据库路径有效
            if not self.db_path:
                self.db_path = "lottery.db"
                logger.warning(f"数据库路径无效，使用默认路径: {self.db_path}")
            
            # 记录数据库路径
            logger.info(f"使用数据库路径: {self.db_path}")
            
            # 确保数据库目录存在
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                try:
                    os.makedirs(db_dir, exist_ok=True)
                    logger.info(f"创建数据库目录: {db_dir}")
                except Exception as e:
                    logger.error(f"创建数据库目录失败: {e}")
                    # 如果无法创建目录，使用当前目录
                    self.db_path = "lottery.db"
                    logger.warning(f"使用当前目录作为数据库路径: {self.db_path}")
            
            # 尝试检查数据库文件是否可写
            try:
                db_file_exists = os.path.exists(self.db_path)
                if db_file_exists:
                    # 检查是否可读
                    if not os.access(self.db_path, os.R_OK):
                        logger.warning(f"数据库文件不可读: {self.db_path}")
                    # 检查是否可写
                    if not os.access(self.db_path, os.W_OK):
                        logger.warning(f"数据库文件不可写: {self.db_path}")
                else:
                    # 尝试创建空文件测试权限
                    try:
                        with open(self.db_path, 'a'):
                            pass
                        logger.info(f"数据库文件权限正常: {self.db_path}")
                    except Exception as e:
                        logger.error(f"无法创建数据库文件: {e}")
                        # 如果无法在指定路径创建文件，使用当前目录
                        self.db_path = "lottery.db"
                        logger.warning(f"改用当前目录数据库: {self.db_path}")
            except Exception as e:
                logger.error(f"检查数据库文件权限失败: {e}")
            
            # 尝试连接数据库
            logger.debug(f"尝试连接数据库: {self.db_path}")
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            
            # 初始化数据库表
            self._init_tables()
            
            logger.info(f"成功连接到数据库: {self.db_path}")
            return True
        except Exception as e:
            logger.error(f"连接数据库失败: {e}")
            self.conn = None
            return False
    
    def _init_tables(self):
        """初始化数据库表"""
        try:
            if not self.conn:
                logger.error("数据库未连接，无法初始化表")
                return False
            
            # 创建开奖记录表
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS lottery_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    qihao TEXT UNIQUE,
                    opentime TEXT,
                    opennum TEXT,
                    sum INTEGER,
                    is_big INTEGER,
                    is_odd INTEGER,
                    combination_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建预测记录表
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    qihao TEXT,
                    prediction TEXT,
                    prediction_type TEXT,
                    algorithm_used TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    result_qihao TEXT,
                    is_correct INTEGER,
                    UNIQUE(qihao, prediction_type)
                )
            """)
            
            # 创建预测缓存表
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS prediction_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    qihao TEXT NOT NULL,
                    prediction TEXT,
                    prediction_type TEXT,
                    algorithm_used TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(qihao, prediction_type)
                )
            """)
            
            # 创建活跃聊天表
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS active_chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建用户验证表
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS user_verification (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    is_verified INTEGER DEFAULT 0,
                    verification_time TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建群组成员表
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS group_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    group_id INTEGER NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    status TEXT,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    left_at TIMESTAMP,
                    UNIQUE(user_id, group_id)
                )
            """)
            
            # 创建算法性能表
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS algorithm_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prediction_type TEXT NOT NULL,
                    algorithm_number INTEGER NOT NULL,
                    success_count INTEGER DEFAULT 0,
                    total_count INTEGER DEFAULT 0,
                    success_rate REAL DEFAULT 0.0,
                    updated_at TIMESTAMP,
                    UNIQUE(prediction_type, algorithm_number)
                )
            """)
            
            # 创建算法性能详情表
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS algorithm_performance_details (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prediction_type TEXT NOT NULL,
                    performance_data TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(prediction_type)
                )
            """)
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"初始化数据库表失败: {e}")
            return False
    
    def execute_query(self, query, params=(), max_retries=3, fetch=True):
        """执行查询并返回结果
        
        Args:
            query: SQL查询语句
            params: 查询参数
            max_retries: 最大重试次数
            fetch: 是否返回查询结果，对于INSERT/UPDATE/DELETE操作可设为False
        """
        retries = 0
        while retries < max_retries:
            try:
                if not self.conn:
                    self.connect()
                    if not self.conn:
                        logger.error("数据库未连接，无法执行查询")
                        return []
                
                cursor = self.conn.cursor()
                cursor.execute(query, params)
                
                # 如果是SELECT查询，返回结果
                if query.strip().upper().startswith("SELECT") and fetch:
                    results = cursor.fetchall()
                    cursor.close()
                    return results
                # 否则提交事务并返回影响的行数
                else:
                    self.conn.commit()
                    affected_rows = cursor.rowcount
                    cursor.close()
                    return affected_rows
            except sqlite3.OperationalError as e:
                # 处理数据库锁定或繁忙错误
                if "database is locked" in str(e) or "database is busy" in str(e):
                    retries += 1
                    wait_time = 0.1 * (2 ** retries)  # 指数退避
                    logger.warning(f"数据库繁忙，等待 {wait_time:.2f} 秒后重试 ({retries}/{max_retries})")
                    time.sleep(wait_time)
                    # 如果连接可能已损坏，尝试重新连接
                    try:
                        self.conn.close()
                    except:
                        pass
                    self.conn = None
                else:
                    logger.error(f"执行查询失败: {e}")
                    return [] if query.strip().upper().startswith("SELECT") else 0
            except Exception as e:
                logger.error(f"执行查询失败: {e}")
                return [] if query.strip().upper().startswith("SELECT") else 0
        
        # 如果所有重试都失败
        logger.error(f"执行查询失败，已达到最大重试次数: {max_retries}")
        return [] if query.strip().upper().startswith("SELECT") else 0
    
    def save_lottery_record(self, data):
        """保存开奖记录"""
        try:
            if not data or not isinstance(data, dict) or 'qihao' not in data or 'opennum' not in data:
                logger.warning(f"保存开奖记录失败: 数据不完整或格式错误 {data}")
                return False
            
            # 解析开奖号码
            try:
                opennum = data['opennum']
                nums = opennum.split('+')
                total_sum = sum(int(n) for n in nums)
                is_big = total_sum >= GAME_CONFIG.get("BIG_BOUNDARY", 14)  # 使用配置中的大小分界点
                is_odd = total_sum % 2 == 1
                
                # 获取组合类型
                combination_type = self.check_combination_type([int(n) for n in nums])
            except Exception as e:
                logger.error(f"解析开奖号码失败: {e}, 数据: {data}")
                # 使用默认值
                total_sum = 0
                is_big = False
                is_odd = False
                combination_type = "未知"
            
            # 插入或更新记录
            affected_rows = self.execute_query(
                """
                INSERT OR REPLACE INTO lottery_records 
                (qihao, opennum, sum, is_big, is_odd, combination_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (data['qihao'], data['opennum'], total_sum, 1 if is_big else 0, 1 if is_odd else 0, combination_type)
            )
            
            # 更新相关预测的正确性
            try:
                self.update_prediction_correctness(data['qihao'], opennum, total_sum, is_big, is_odd)
            except Exception as e:
                logger.error(f"更新预测正确性失败: {e}")
            
            return affected_rows > 0
        except Exception as e:
            logger.error(f"保存开奖记录失败: {e}")
            return False
    
    def check_combination_type(self, nums):
        """检查号码组合类型"""
        try:
            # 确保输入是数字列表
            if not all(isinstance(n, int) for n in nums):
                nums = [int(n) for n in nums]
            
            # 检查是否为豹子
            if len(set(nums)) == 1:
                return "豹子"
            
            # 检查是否为顺子
            sorted_nums = sorted(nums)
            is_straight = all(sorted_nums[i] + 1 == sorted_nums[i+1] for i in range(len(sorted_nums)-1))
            if is_straight:
                return "顺子"
            
            # 检查是否为对子
            if len(set(nums)) == 2:
                counts = [nums.count(n) for n in set(nums)]
                if 2 in counts:
                    return "对子"
            
            # 默认为杂六
            return "杂六"
        except Exception as e:
            logger.error(f"检查组合类型失败: {e}")
            return "未知"
    
    def save_prediction(self, data):
        """保存预测记录"""
        try:
            if not data or 'qihao' not in data or 'prediction' not in data or 'prediction_type' not in data:
                logger.warning(f"保存预测记录失败: 数据不完整 {data}")
                return False
            
            # 准备算法使用信息
            algorithm_used = data.get('algorithm_used', {})
            if isinstance(algorithm_used, dict):
                algorithm_used = json.dumps(algorithm_used)
            
            # 检查是否已存在相同期号和预测类型的记录
            existing = self.execute_query(
                "SELECT id FROM predictions WHERE qihao = ? AND prediction_type = ?",
                (data['qihao'], data['prediction_type'])
            )
            
            if existing:
                # 更新现有记录
                affected_rows = self.execute_query(
                    """
                    UPDATE predictions 
                    SET prediction = ?, algorithm_used = ?, updated_at = datetime('now')
                    WHERE qihao = ? AND prediction_type = ?
                    """,
                    (data['prediction'], algorithm_used, data['qihao'], data['prediction_type'])
                )
                logger.debug(f"更新预测记录: {data['qihao']} - {data['prediction_type']}")
            else:
                # 插入新记录
                affected_rows = self.execute_query(
                    """
                    INSERT INTO predictions 
                    (qihao, prediction, prediction_type, algorithm_used, created_at)
                    VALUES (?, ?, ?, ?, datetime('now'))
                    """,
                    (data['qihao'], data['prediction'], data['prediction_type'], algorithm_used)
                )
                logger.info(f"保存新预测记录: {data['qihao']} - {data['prediction_type']}")
            
            # 检查是否有对应的开奖记录，如果有，立即更新预测正确性
            lottery_record = self.execute_query(
                "SELECT opennum, sum, is_big, is_odd FROM lottery_records WHERE qihao = ?",
                (data['qihao'],)
            )
            
            if lottery_record:
                opennum = lottery_record[0][0]
                total_sum = lottery_record[0][1]
                is_big = lottery_record[0][2]
                is_odd = lottery_record[0][3]
                self.update_prediction_correctness(data['qihao'], opennum, total_sum, is_big, is_odd)
            
            return affected_rows > 0
        except Exception as e:
            logger.error(f"保存预测记录失败: {e}")
            return False
    
    def get_recent_records(self, limit=10):
        """获取最近的开奖记录"""
        try:
            records = self.execute_query(
                "SELECT * FROM lottery_records ORDER BY qihao DESC LIMIT ?",
                (limit,)
            )
            return records
        except Exception as e:
            logger.error(f"获取最近开奖记录失败: {e}")
            return []
    
    def get_latest_record(self):
        """获取最新的开奖记录"""
        try:
            records = self.execute_query(
                "SELECT * FROM lottery_records ORDER BY qihao DESC LIMIT 1"
            )
            return records[0] if records else None
        except Exception as e:
            logger.error(f"获取最新开奖记录失败: {e}")
            return None
    
    def get_prediction_history(self, prediction_type, limit=100):
        """获取预测历史记录"""
        try:
            query = """
                SELECT p.id, p.qihao, p.prediction, p.created_at, p.algorithm_used, 
                       r.opennum as result, r.sum as sum, r.is_big, r.is_odd, r.combination_type, 
                       CASE 
                           WHEN r.opennum IS NOT NULL THEN 
                               CASE 
                                   WHEN p.prediction_type = 'single_double' THEN 
                                       (CASE WHEN r.is_odd = 1 AND p.prediction LIKE '单%' THEN 1
                                             WHEN r.is_odd = 0 AND p.prediction LIKE '双%' THEN 1
                                             ELSE 0 END)
                                   WHEN p.prediction_type = 'big_small' THEN 
                                       (CASE WHEN r.is_big = 1 AND p.prediction LIKE '大%' THEN 1
                                             WHEN r.is_big = 0 AND p.prediction LIKE '小%' THEN 1
                                             ELSE 0 END)
                                   WHEN p.prediction_type = 'kill_group' THEN 
                                       (CASE WHEN (r.is_big = 1 AND r.is_odd = 1 AND p.prediction NOT LIKE '%大单%') OR
                                                  (r.is_big = 1 AND r.is_odd = 0 AND p.prediction NOT LIKE '%大双%') OR
                                                  (r.is_big = 0 AND r.is_odd = 1 AND p.prediction NOT LIKE '%小单%') OR
                                                  (r.is_big = 0 AND r.is_odd = 0 AND p.prediction NOT LIKE '%小双%')
                                             THEN 1
                                             ELSE 0 END)
                                   WHEN p.prediction_type = 'double_group' THEN 
                                       (CASE WHEN (r.is_big = 1 AND r.is_odd = 1 AND p.prediction LIKE '%大单%') OR
                                                  (r.is_big = 1 AND r.is_odd = 0 AND p.prediction LIKE '%大双%') OR
                                                  (r.is_big = 0 AND r.is_odd = 1 AND p.prediction LIKE '%小单%') OR
                                                  (r.is_big = 0 AND r.is_odd = 0 AND p.prediction LIKE '%小双%')
                                             THEN 1
                                             ELSE 0 END)
                                   ELSE 0
                               END
                           ELSE NULL
                       END as is_correct
                FROM predictions p
                LEFT JOIN lottery_records r ON p.qihao = r.qihao
                WHERE p.prediction_type = ?
                ORDER BY p.qihao DESC
                LIMIT ?
            """
            
            history = []
            cursor = self.conn.cursor()
            cursor.execute(query, (prediction_type, limit))
            
            for row in cursor.fetchall():
                # 构建预测历史记录
                opennum = row[5]  # result
                total_sum = row[6]  # sum
                is_big = row[7]  # is_big
                is_odd = row[8]  # is_odd
                combination_type = row[9]  # combination_type
                is_correct = row[10]  # is_correct
                
                # 处理NULL值
                result = opennum if opennum else "未知"
                
                history.append({
                    'id': row[0],
                    'qihao': row[1],
                    'prediction': row[2],
                    'created_at': row[3],
                    'algorithm_used': row[4],
                    'result': result,
                    'sum': total_sum,
                    'is_big': bool(is_big) if is_big is not None else None,
                    'is_odd': bool(is_odd) if is_odd is not None else None,
                    'combination_type': combination_type,
                    'is_correct': bool(is_correct) if is_correct is not None else None
                })
            
            return history
            
        except Exception as e:
            logger.error(f"获取预测历史失败: {e}")
            return []
    
    def get_prediction_by_qihao(self, qihao, pred_type):
        """根据期号获取预测记录"""
        try:
            records = self.execute_query(
                "SELECT * FROM predictions WHERE qihao = ? AND prediction_type = ?",
                (qihao, pred_type)
            )
            return records[0] if records else None
        except Exception as e:
            logger.error(f"获取预测记录失败: {e}")
            return None
    
    def update_prediction_result(self, qihao, prediction_type, opennum, total_sum, is_correct):
        """更新预测结果"""
        try:
            # 更新预测结果，不使用opennum列
            self.execute_query(
                """
                UPDATE predictions 
                SET is_correct = ?, updated_at = datetime('now')
                WHERE qihao = ? AND prediction_type = ?
                """,
                (1 if is_correct else 0, qihao, prediction_type),
                fetch=False
            )
            logger.info(f"更新预测结果: {qihao} {prediction_type} 正确:{is_correct}")
            return True
        except Exception as e:
            logger.error(f"更新预测结果失败: {e}")
            return False
    
    def get_cached_prediction(self, qihao, prediction_type):
        """获取缓存的预测"""
        try:
            records = self.execute_query(
                "SELECT * FROM prediction_cache WHERE qihao = ? AND prediction_type = ?",
                (qihao, prediction_type)
            )
            return records[0] if records else None
        except Exception as e:
            logger.error(f"获取缓存预测失败: {e}")
            return None
    
    def save_prediction_cache(self, data):
        """保存预测缓存"""
        try:
            # 检查缓存是否已存在
            existing = self.execute_query(
                "SELECT id FROM prediction_cache WHERE qihao = ? AND prediction_type = ?",
                (data['qihao'], data['prediction_type'])
            )
            
            if existing:
                # 更新现有缓存
                self.execute_query(
                    """
                    UPDATE prediction_cache 
                    SET prediction = ?, algorithm_used = ?, created_at = ?
                    WHERE qihao = ? AND prediction_type = ?
                    """,
                    (
                        data['prediction'], data['algorithm_used'], 
                        datetime.now(), data['qihao'], data['prediction_type']
                    ),
                    fetch=False
                )
            else:
                # 插入新缓存
                self.execute_query(
                    """
                    INSERT INTO prediction_cache 
                    (qihao, prediction, prediction_type, algorithm_used)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        data['qihao'], data['prediction'], 
                        data['prediction_type'], data['algorithm_used']
                    ),
                    fetch=False
                )
            
            return True
        except Exception as e:
            logger.error(f"保存预测缓存失败: {e}")
            return False
    
    def cache_prediction(self, qihao, prediction_type, data):
        """缓存预测结果（作为save_prediction_cache的别名）
        
        Args:
            qihao: 期号
            prediction_type: 预测类型
            data: 预测数据
        
        Returns:
            bool: 是否成功
        """
        # 构建完整数据
        cache_data = {
            'qihao': qihao,
            'prediction_type': prediction_type,
            'prediction': data.get('prediction'),
            'algorithm_used': data.get('algorithm_used')
        }
        
        # 调用原有方法
        return self.save_prediction_cache(cache_data)
    
    def get_active_chats(self):
        """获取所有活跃聊天"""
        try:
            records = self.execute_query("SELECT chat_id FROM active_chats")
            return [record[0] for record in records]
        except Exception as e:
            logger.error(f"获取活跃聊天失败: {e}")
            return []
    
    def add_active_chat(self, chat_id):
        """添加活跃聊天"""
        try:
            # 检查是否已存在
            existing = self.execute_query(
                "SELECT id FROM active_chats WHERE chat_id = ?",
                (chat_id,)
            )
            
            if not existing:
                self.execute_query(
                    "INSERT INTO active_chats (chat_id) VALUES (?)",
                    (chat_id,),
                    fetch=False
                )
                logger.info(f"添加活跃聊天: {chat_id}")
            
            return True
        except Exception as e:
            logger.error(f"添加活跃聊天失败: {e}")
            return False
    
    def remove_active_chat(self, chat_id):
        """移除活跃聊天"""
        try:
            self.execute_query(
                "DELETE FROM active_chats WHERE chat_id = ?",
                (chat_id,),
                fetch=False
            )
            logger.info(f"移除活跃聊天: {chat_id}")
            return True
        except Exception as e:
            logger.error(f"移除活跃聊天失败: {e}")
            return False
    
    def update_algorithm_performance(self, pred_type, algo_num, is_correct):
        """更新算法性能"""
        try:
            if not pred_type or not algo_num:
                logger.warning(f"更新算法性能失败: 参数不完整 {pred_type}, {algo_num}")
                return False
                
            # 确保is_correct是布尔值
            if isinstance(is_correct, int):
                is_correct = bool(is_correct)
                
            # 检查记录是否存在
            existing = self.execute_query(
                """
                SELECT id, success_count, total_count 
                FROM algorithm_performance 
                WHERE prediction_type = ? AND algorithm_number = ?
                """,
                (pred_type, algo_num)
            )
            
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if existing and len(existing) > 0:
                # 更新现有记录
                try:
                    record = existing[0]
                    success_count = record[1] + (1 if is_correct else 0)
                    total_count = record[2] + 1
                    success_rate = success_count / total_count if total_count > 0 else 0
                    
                    self.execute_query(
                        """
                        UPDATE algorithm_performance 
                        SET success_count = ?, total_count = ?, success_rate = ?, updated_at = ?
                        WHERE prediction_type = ? AND algorithm_number = ?
                        """,
                        (success_count, total_count, success_rate, current_time, pred_type, algo_num)
                    )
                except Exception as e:
                    logger.error(f"更新算法性能记录失败: {e}")
                    return False
            else:
                # 插入新记录
                success_count = 1 if is_correct else 0
                total_count = 1
                success_rate = success_count / total_count
                
                self.execute_query(
                    """
                    INSERT INTO algorithm_performance 
                    (prediction_type, algorithm_number, success_count, total_count, success_rate, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (pred_type, algo_num, success_count, total_count, success_rate, current_time)
                )
            
            return True
        except Exception as e:
            logger.error(f"更新算法性能失败: {e}")
            return False
    
    def get_algorithm_performance(self, pred_type=None):
        """获取算法性能数据"""
        try:
            if not self.conn:
                self.connect()
                if not self.conn:
                    logger.error("数据库未连接，无法获取算法性能数据")
                    return None
            
            if pred_type:
                # 先尝试从算法性能详情表获取数据
                query = """
                    SELECT * FROM algorithm_performance_details
                    WHERE prediction_type = ?
                    ORDER BY updated_at DESC
                    LIMIT 1
                """
                result = self.execute_query(query, (pred_type,))
                
                if result and len(result) > 0:
                    try:
                        # 返回完整的性能数据
                        perf_data = json.loads(result[0]['performance_data'])
                        return perf_data
                    except:
                        logger.warning(f"解析算法详细性能数据失败，尝试使用基本性能数据: {pred_type}")
                
                # 如果没有详细数据或解析失败，使用基本性能数据
                query = """
                    SELECT algorithm_number, success_count, total_count, success_rate
                    FROM algorithm_performance
                    WHERE prediction_type = ?
                """
                results = self.execute_query(query, (pred_type,))
                
                if not results:
                    logger.warning(f"数据库中未找到{pred_type}的算法性能数据")
                    return None
                
                # 构建基本的性能数据结构
                perf_data = {
                    'current_algorithm': 1,  # 默认使用1号算法
                    'algorithms': {},
                    'updated_at': datetime.now().isoformat()
                }
                
                for row in results:
                    algo_num = row['algorithm_number']
                    
                    # 兼容处理：确保算法编号是整数
                    try:
                        algo_num = int(algo_num)
                    except:
                        continue
                        
                    perf_data['algorithms'][algo_num] = {
                        'total_predictions': row['total_count'],
                        'correct_predictions': row['success_count'],
                        'success_rate': row['success_rate'],
                        'confidence_score': row['success_rate'] if row['total_count'] > 0 else 0.5,
                        'consecutive_wrong': 0,
                        'consecutive_correct': 0,
                        'recent_results': [],
                        'recent_success_rate': row['success_rate'],
                        'last_switch_time': 0
                    }
                    
                    # 如果算法1的成功率高于其他，设为当前算法
                    if algo_num == 1:
                        perf_data['current_algorithm'] = 1
                    elif (algo_num in [2, 3] and 
                          algo_num in perf_data['algorithms'] and 
                          1 in perf_data['algorithms'] and
                          perf_data['algorithms'][algo_num]['success_rate'] > 
                          perf_data['algorithms'][1]['success_rate'] + 0.1):
                        perf_data['current_algorithm'] = algo_num
                
                return perf_data
            else:
                # 获取所有预测类型的算法性能
                results = {}
                for pt in ['single_double', 'big_small', 'kill_group', 'double_group']:
                    results[pt] = self.get_algorithm_performance(pt)
                return results
                
        except Exception as e:
            logger.error(f"获取算法性能数据失败: {e}")
            return None
    
    def save_algorithm_performance(self, pred_type, performance_data):
        """保存算法完整性能数据
        
        Args:
            pred_type: 预测类型
            performance_data: 性能数据字典
            
        Returns:
            bool: 保存是否成功
        """
        try:
            if not self.conn:
                self.connect()
                if not self.conn:
                    logger.error("数据库未连接，无法保存算法性能数据")
                    return False
            
            # 确保数据库中存在算法性能详情表
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS algorithm_performance_details (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prediction_type TEXT NOT NULL,
                    performance_data TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(prediction_type) ON CONFLICT REPLACE
                )
            """)
            self.conn.commit()
            
            # 保存完整性能数据
            query = """
                INSERT OR REPLACE INTO algorithm_performance_details
                (prediction_type, performance_data, updated_at)
                VALUES (?, ?, ?)
            """
            params = (
                pred_type,
                json.dumps(performance_data),
                datetime.now().isoformat()
            )
            
            self.execute_query(query, params, fetch=False)
            
            # 同时更新基本的算法性能表，保持向后兼容性
            if 'algorithms' in performance_data:
                for algo_num, perf in performance_data['algorithms'].items():
                    if not isinstance(algo_num, int):
                        try:
                            algo_num = int(algo_num)
                        except:
                            continue
                    
                    # 提取基本性能数据
                    total_count = perf.get('total_predictions', 0)
                    success_count = perf.get('correct_predictions', 0)
                    success_rate = perf.get('success_rate', 0.0)
                    
                    if total_count > 0:
                        # 更新基本性能表
                        query = """
                            INSERT OR REPLACE INTO algorithm_performance
                            (prediction_type, algorithm_number, success_count, total_count, success_rate, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """
                        params = (
                            pred_type,
                            algo_num,
                            success_count,
                            total_count,
                            success_rate,
                            datetime.now().isoformat()
                        )
                        self.execute_query(query, params, fetch=False)
            
            logger.info(f"算法性能数据保存成功: {pred_type}")
            return True
            
        except Exception as e:
            logger.error(f"保存算法性能数据失败: {e}")
            return False
    
    def update_prediction_correctness(self, qihao, opennum, total_sum, is_big, is_odd):
        """更新预测的正确性"""
        try:
            # 获取该期号的所有预测
            predictions = self.execute_query(
                "SELECT id, prediction, prediction_type FROM predictions WHERE qihao = ?",
                (qihao,)
            )
            
            if not predictions:
                return
            
            # 计算组合类型
            try:
                nums = [int(n) for n in opennum.split('+')]
                combination_type = self.check_combination_type(nums)
            except:
                combination_type = "未知"
            
            # 更新每个预测的正确性
            for pred in predictions:
                pred_id = pred[0]
                prediction = pred[1]
                pred_type = pred[2]
                
                # 判断预测是否正确
                is_correct = False
                
                try:
                    if pred_type == 'single_double':
                        # 修复单双预测判断，处理"单08"或"双17"这样的格式
                        if "单" in prediction:
                            is_correct = is_odd  # 如果预测包含"单"，则结果为单数时正确
                        else:  # "双"
                            is_correct = not is_odd  # 如果预测包含"双"，则结果为双数时正确
                    elif pred_type == 'big_small':
                        is_correct = (prediction.startswith('大') and is_big) or (prediction.startswith('小') and not is_big)
                    elif pred_type == 'kill_group':
                        kill_target = prediction[1:] if len(prediction) > 1 else ""
                        actual_result = f"{'大' if is_big else '小'}{'单' if is_odd else '双'}"
                        is_correct = kill_target != actual_result
                    elif pred_type == 'double_group':
                        # 双组预测验证逻辑
                        try:
                            # 处理双组预测格式
                            if ':' in prediction:
                                pred_parts = prediction.split(':')[0].split('/')
                                # 提取特码数字
                                numbers_text = prediction.split(':')[1].strip() if len(prediction.split(':')) > 1 else ""
                                if numbers_text.startswith('[') and numbers_text.endswith(']'):
                                    numbers = numbers_text.strip('[]').split(',')
                                    # 清理数字格式
                                    numbers = [n.strip().strip('`').strip() for n in numbers]
                                    # 检查当前和值是否在特码中
                                    is_number_correct = str(total_sum).zfill(2) in numbers or str(total_sum) in numbers
                                else:
                                    is_number_correct = False
                            else:
                                pred_parts = prediction.split('/')
                                is_number_correct = False
                                
                            actual_result = f"{'大' if is_big else '小'}{'单' if is_odd else '双'}"
                            is_combo_correct = any(combo == actual_result for combo in pred_parts)
                            
                            # 组合或特码正确，则预测正确
                            is_correct = is_combo_correct or is_number_correct
                        except Exception as e:
                            logger.error(f"双组预测正确性验证失败: {e}")
                            is_correct = False
                except Exception as e:
                    logger.error(f"判断预测正确性失败: {e}")
                    continue
                
                # 更新预测结果
                self.execute_query(
                    """
                    UPDATE predictions 
                    SET is_correct = ?, updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (1 if is_correct else 0, pred_id),
                    fetch=False
                )
        except Exception as e:
            logger.error(f"更新预测正确性失败: {e}")
    
    def initialize_database(self):
        """初始化数据库，包括创建表和初始化算法性能数据"""
        try:
            # 确保数据库连接
            if not self.conn:
                self.connect()
                if not self.conn:
                    logger.error("数据库未连接，无法初始化数据库")
                    return False
            
            # 初始化表
            self._init_tables()
            
            # 初始化算法性能数据
            self._initialize_algorithm_performance()
            
            logger.info("数据库初始化完成")
            return True
        except Exception as e:
            logger.error(f"初始化数据库失败: {e}")
            return False
    
    def _initialize_algorithm_performance(self):
        """初始化算法性能数据"""
        try:
            # 检查算法性能表是否有数据
            for pred_type in ['single_double', 'big_small', 'kill_group', 'double_group']:
                # 检查是否已存在该预测类型的算法性能数据
                query = """
                    SELECT COUNT(*) as count FROM algorithm_performance
                    WHERE prediction_type = ?
                """
                result = self.execute_query(query, (pred_type,))
                
                if not result or result[0]['count'] == 0:
                    logger.info(f"初始化 {pred_type} 的算法性能数据")
                    
                    # 为每个算法创建默认性能数据
                    for algo_num in [1, 2, 3]:
                        query = """
                            INSERT INTO algorithm_performance
                            (prediction_type, algorithm_number, success_count, total_count, success_rate, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """
                        params = (
                            pred_type,
                            algo_num,
                            0,  # success_count
                            0,  # total_count
                            0.5,  # success_rate (默认0.5)
                            datetime.now().isoformat()
                        )
                        self.execute_query(query, params, fetch=False)
                    
                    # 创建详细性能数据
                    performance_data = {
                        'current_algorithm': 1,
                        'algorithms': {
                            1: {
                                'total_predictions': 0,
                                'correct_predictions': 0,
                                'success_rate': 0.5,
                                'confidence_score': 0.5,
                                'consecutive_wrong': 0,
                                'consecutive_correct': 0,
                                'recent_results': [],
                                'recent_success_rate': 0.5,
                                'last_switch_time': 0
                            },
                            2: {
                                'total_predictions': 0,
                                'correct_predictions': 0,
                                'success_rate': 0.5,
                                'confidence_score': 0.5,
                                'consecutive_wrong': 0,
                                'consecutive_correct': 0,
                                'recent_results': [],
                                'recent_success_rate': 0.5,
                                'last_switch_time': 0
                            },
                            3: {
                                'total_predictions': 0,
                                'correct_predictions': 0,
                                'success_rate': 0.5,
                                'confidence_score': 0.5,
                                'consecutive_wrong': 0,
                                'consecutive_correct': 0,
                                'recent_results': [],
                                'recent_success_rate': 0.5,
                                'last_switch_time': 0
                            }
                        },
                        'updated_at': datetime.now().isoformat()
                    }
                    
                    # 保存详细性能数据
                    self.save_algorithm_performance(pred_type, performance_data)
                    
                    logger.info(f"{pred_type} 算法性能数据初始化完成")
                else:
                    logger.info(f"{pred_type} 算法性能数据已存在，跳过初始化")
            
            return True
        except Exception as e:
            logger.error(f"初始化算法性能数据失败: {e}")
            return False
    
    def __del__(self):
        """析构函数，关闭数据库连接"""
        try:
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
                logger.info("数据库连接已关闭")
        except Exception as e:
            logger.error(f"关闭数据库连接失败: {e}")
    
    def get_prediction_count(self, prediction_type):
        """获取指定类型的预测总数"""
        query = "SELECT COUNT(*) as count FROM predictions WHERE prediction_type = ?"
        result = self.execute_query(query, (prediction_type,))
        return result[0]['count'] if result else 0
        
    # 用户验证相关方法
    def add_user(self, user_id, username=None, first_name=None, last_name=None):
        """添加新用户或更新现有用户信息"""
        try:
            query = """
                INSERT INTO user_verification (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name
            """
            params = (user_id, username, first_name, last_name)
            self.execute_query(query, params, fetch=False)
            logger.info(f"添加或更新用户: user_id={user_id}, username={username}")
            return True
        except Exception as e:
            logger.error(f"添加或更新用户失败: {e}")
            return False
    
    def set_user_verified(self, user_id, is_verified=True):
        """设置用户验证状态"""
        try:
            verification_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if is_verified else None
            query = """
                UPDATE user_verification
                SET is_verified = ?, verification_time = ?
                WHERE user_id = ?
            """
            params = (1 if is_verified else 0, verification_time, user_id)
            result = self.execute_query(query, params, fetch=False)
            
            if result > 0:
                logger.info(f"用户验证状态已更新: user_id={user_id}, is_verified={is_verified}")
                return True
            else:
                logger.warning(f"未找到用户: user_id={user_id}")
                return False
        except Exception as e:
            logger.error(f"更新用户验证状态失败: {e}")
            return False
    
    def is_user_verified(self, user_id):
        """检查用户是否已验证"""
        try:
            query = "SELECT is_verified FROM user_verification WHERE user_id = ?"
            result = self.execute_query(query, (user_id,))
            if result:
                is_verified = bool(result[0]['is_verified'])
                logger.debug(f"检查用户验证状态: user_id={user_id}, is_verified={is_verified}")
                return is_verified
            else:
                logger.debug(f"未找到用户: user_id={user_id}")
                return False
        except Exception as e:
            logger.error(f"检查用户验证状态失败: {e}")
            return False
    
    def get_user_verification_info(self, user_id):
        """获取用户的验证信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            dict: 用户验证信息，如果未找到则返回None
        """
        try:
            query = "SELECT * FROM user_verification WHERE user_id = ?"
            result = self.execute_query(query, (user_id,))
            
            if result:
                # 将sqlite3.Row转换为普通字典
                user_info = dict(result[0])
                logger.debug(f"获取用户验证信息成功: user_id={user_id}")
                return user_info
            else:
                logger.debug(f"未找到用户验证信息: user_id={user_id}")
                return None
        except Exception as e:
            logger.error(f"获取用户验证信息失败: {e}")
            return None
    
    def get_verification_stats(self):
        """获取验证统计信息"""
        try:
            query = """
                SELECT 
                    COUNT(*) as total_users,
                    SUM(CASE WHEN is_verified = 1 THEN 1 ELSE 0 END) as verified_users
                FROM user_verification
            """
            result = self.execute_query(query)
            if result:
                stats = {
                    "total_users": result[0]['total_users'],
                    "verified_users": result[0]['verified_users']
                }
                return stats
            else:
                return {"total_users": 0, "verified_users": 0}
        except Exception as e:
            logger.error(f"获取验证统计信息失败: {e}")
            return {"total_users": 0, "verified_users": 0}
            
    def get_all_verified_users(self):
        """获取所有已验证用户
        
        Returns:
            list: 已验证用户列表，每个元素为包含用户信息的字典
        """
        try:
            query = """
                SELECT user_id, username, first_name, last_name, verification_time
                FROM user_verification
                WHERE is_verified = 1
                ORDER BY verification_time DESC
            """
            result = self.execute_query(query)
            
            users = []
            if result:
                for row in result:
                    users.append(dict(row))
                
                logger.debug(f"获取到 {len(users)} 个已验证用户")
            else:
                logger.debug("没有找到已验证用户")
                
            return users
        except Exception as e:
            logger.error(f"获取已验证用户列表失败: {e}")
            return []
            
    # 群组成员管理相关方法
    def add_group_member(self, user_id, group_id, username=None, first_name=None, last_name=None, status=None):
        """添加或更新群组成员信息"""
        try:
            # 检查是否已存在记录
            query = "SELECT id, is_active FROM group_members WHERE user_id = ? AND group_id = ?"
            result = self.execute_query(query, (user_id, group_id))
            
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if result:
                # 更新现有记录
                member_id = result[0]['id']
                is_active = result[0]['is_active']
                
                if is_active == 0:
                    # 如果之前标记为非活跃，现在重新加入
                    update_query = """
                        UPDATE group_members
                        SET username = ?, first_name = ?, last_name = ?, status = ?,
                            last_seen_at = ?, is_active = 1, left_at = NULL
                        WHERE id = ?
                    """
                    params = (username, first_name, last_name, status, current_time, member_id)
                    self.execute_query(update_query, params, fetch=False)
                    logger.info(f"用户 {user_id} 重新加入群组 {group_id}")
                else:
                    # 正常更新
                    update_query = """
                        UPDATE group_members
                        SET username = ?, first_name = ?, last_name = ?, status = ?,
                            last_seen_at = ?
                        WHERE id = ?
                    """
                    params = (username, first_name, last_name, status, current_time, member_id)
                    self.execute_query(update_query, params, fetch=False)
                    logger.debug(f"更新群组成员信息: user_id={user_id}, group_id={group_id}")
            else:
                # 插入新记录
                insert_query = """
                    INSERT INTO group_members
                    (user_id, group_id, username, first_name, last_name, status, joined_at, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
                params = (user_id, group_id, username, first_name, last_name, status, current_time, current_time)
                self.execute_query(insert_query, params, fetch=False)
                logger.info(f"添加新群组成员: user_id={user_id}, group_id={group_id}, status={status}")
            
            return True
        except Exception as e:
            logger.error(f"添加或更新群组成员失败: {e}")
            return False
    
    def mark_member_left_group(self, user_id, group_id):
        """标记用户已离开群组"""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            query = """
                UPDATE group_members
                SET is_active = 0, left_at = ?
                WHERE user_id = ? AND group_id = ? AND is_active = 1
            """
            result = self.execute_query(query, (current_time, user_id, group_id), fetch=False)
            
            if result > 0:
                logger.info(f"标记用户 {user_id} 已离开群组 {group_id}")
                return True
            else:
                logger.warning(f"找不到活跃的群组成员记录: user_id={user_id}, group_id={group_id}")
                return False
        except Exception as e:
            logger.error(f"标记用户离开群组失败: {e}")
            return False
    
    def is_user_in_group(self, user_id, group_id):
        """检查用户是否在群组中（根据数据库记录）"""
        try:
            query = "SELECT is_active FROM group_members WHERE user_id = ? AND group_id = ?"
            result = self.execute_query(query, (user_id, group_id))
            
            if result:
                is_active = bool(result[0]['is_active'])
                return is_active
            else:
                return False
        except Exception as e:
            logger.error(f"检查用户是否在群组中失败: {e}")
            return False
    
    def update_member_status(self, user_id, group_id, status):
        """更新成员在群组中的状态"""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            query = """
                UPDATE group_members
                SET status = ?, last_seen_at = ?
                WHERE user_id = ? AND group_id = ?
            """
            result = self.execute_query(query, (status, current_time, user_id, group_id), fetch=False)
            
            if result > 0:
                logger.debug(f"更新用户 {user_id} 在群组 {group_id} 的状态为 {status}")
                return True
            else:
                logger.warning(f"找不到群组成员记录来更新状态: user_id={user_id}, group_id={group_id}")
                return False
        except Exception as e:
            logger.error(f"更新成员状态失败: {e}")
            return False
    
    def get_group_member_info(self, user_id, group_id):
        """获取用户在指定群组的成员信息
        
        Args:
            user_id: 用户ID
            group_id: 群组ID
            
        Returns:
            dict: 成员信息字典，如果未找到则返回None
        """
        try:
            query = "SELECT * FROM group_members WHERE user_id = ? AND group_id = ?"
            result = self.execute_query(query, (user_id, group_id))
            
            if result:
                # 将sqlite3.Row转换为普通字典
                member_info = dict(result[0])
                logger.debug(f"获取群组成员信息成功: user_id={user_id}, group_id={group_id}")
                return member_info
            else:
                logger.debug(f"未找到群组成员信息: user_id={user_id}, group_id={group_id}")
                return None
        except Exception as e:
            logger.error(f"获取群组成员信息失败: {e}")
            return None
    
    def get_all_group_members(self, group_id, status=None, limit=100, offset=0):
        """获取指定群组的所有成员
        
        Args:
            group_id: 群组ID
            status: 成员状态（可选，如果提供则只返回指定状态的成员）
            limit: 返回的最大记录数
            offset: 分页偏移量
            
        Returns:
            list: 成员信息列表
        """
        try:
            if status:
                query = """
                    SELECT * FROM group_members 
                    WHERE group_id = ? AND status = ? 
                    ORDER BY last_seen_at DESC
                    LIMIT ? OFFSET ?
                """
                params = (group_id, status, limit, offset)
            else:
                query = """
                    SELECT * FROM group_members 
                    WHERE group_id = ? 
                    ORDER BY last_seen_at DESC
                    LIMIT ? OFFSET ?
                """
                params = (group_id, limit, offset)
                
            results = self.execute_query(query, params)
            
            # 将sqlite3.Row转换为普通字典
            members = [dict(row) for row in results]
            logger.debug(f"获取群组所有成员成功: group_id={group_id}, count={len(members)}")
            return members
        except Exception as e:
            logger.error(f"获取群组所有成员失败: {e}")
            return []
    
    def get_active_group_members_count(self, group_id):
        """获取指定群组的活跃成员数量
        
        Args:
            group_id: 群组ID
            
        Returns:
            int: 活跃成员数量
        """
        try:
            query = """
                SELECT COUNT(*) as count FROM group_members 
                WHERE group_id = ? AND is_active = 1 AND left_at IS NULL
            """
            result = self.execute_query(query, (group_id,))
            
            count = result[0]['count'] if result else 0
            logger.debug(f"获取群组活跃成员数量: group_id={group_id}, count={count}")
            return count
        except Exception as e:
            logger.error(f"获取群组活跃成员数量失败: {e}")

# 创建全局数据库管理器实例
db_manager = DBManager() 