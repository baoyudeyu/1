from dotenv import load_dotenv
import os
from loguru import logger

# 加载环境变量
load_dotenv()

# Telegram 配置
TELEGRAM_CONFIG = {
    "BOT_TOKEN": os.getenv("BOT_TOKEN", "7265094096:AAFyH1RLt6cktnbzB3uSoW-5k9t-upkcIWM"),
    "ADMIN_ID": int(os.getenv("ADMIN_ID", "7556123117")),
    "API_ID": int(os.getenv("API_ID", "20608397")),
    "API_HASH": os.getenv("API_HASH", "18d5d21a6ef00351d0adbe9dc5f27952")
}

# 数据库配置
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "fenxi28bot"),
    "password": os.getenv("DB_PASSWORD", "yu"),
    "database": os.getenv("DB_NAME", "fenxi28bot"),
    "charset": os.getenv("DB_CHARSET", "utf8mb4"),
    "db_path": os.getenv("DB_PATH", "lottery.db")
}

# API 配置
API_CONFIG = {
    "LOTTERY_API": os.getenv("LOTTERY_API", "https://www.zuzu28.com/gengduo.php"),
    "TIMEOUT": int(os.getenv("API_TIMEOUT", "10")),
    "MAX_RETRIES": int(os.getenv("API_MAX_RETRIES", "3"))
}

# 游戏规则配置
GAME_CONFIG = {
    "BIG_BOUNDARY": int(os.getenv("BIG_BOUNDARY", "14")),  # 大小分界线
    "MAX_VALUE": int(os.getenv("MAX_VALUE", "27")),        # 最大值
    "MIN_VALUE": int(os.getenv("MIN_VALUE", "0"))          # 最小值
}

# 算法配置
ALGORITHM_CONFIG = {
    "SWITCH_PERIODS": {
        "SINGLE_DOUBLE": int(os.getenv("SINGLE_DOUBLE_SWITCH", "5")),  # 单双算法切换周期
        "BIG_SMALL": int(os.getenv("BIG_SMALL_SWITCH", "7")),          # 大小算法切换周期
        "KILL_GROUP": int(os.getenv("KILL_GROUP_SWITCH", "3")),        # 杀组算法切换周期
        "DOUBLE_GROUP": int(os.getenv("DOUBLE_GROUP_SWITCH", "4"))     # 双组算法切换周期
    },
    "PERFORMANCE_THRESHOLD": float(os.getenv("PERFORMANCE_THRESHOLD", "0.6")),  # 算法性能阈值
    "MIN_SAMPLES": int(os.getenv("MIN_SAMPLES", "10"))                 # 最小样本数
}

# 播报配置
BROADCAST_CONFIG = {
    "HISTORY_COUNT": int(os.getenv("BROADCAST_HISTORY_COUNT", "10")),  # 显示最近几期数据
    "INTERVAL": int(os.getenv("BROADCAST_INTERVAL", "1"))              # 检查间隔（秒）
}

# 预测配置
PREDICTION_CONFIG = {
    "CHECK_INTERVAL": int(os.getenv("PREDICTION_CHECK_INTERVAL", "300")),  # 验证间隔（秒）
    "DELAY_MIN": int(os.getenv("PREDICTION_DELAY_MIN", "10")),            # 最小延迟（秒）
    "DELAY_MAX": int(os.getenv("PREDICTION_DELAY_MAX", "30"))             # 最大延迟（秒）
}

# 缓存配置
CACHE_CONFIG = {
    "BROADCAST_TTL": int(os.getenv("CACHE_BROADCAST_TTL", "10")),      # 广播消息缓存时间（秒）
    "PREDICTION_TTL": int(os.getenv("CACHE_PREDICTION_TTL", "20")),    # 预测消息缓存时间（秒）
    "CLEANUP_INTERVAL": int(os.getenv("CACHE_CLEANUP_INTERVAL", "300")) # 缓存清理间隔（秒）
}

# 验证配置
VERIFICATION_CONFIG = {
    "REQUIRED": os.getenv("VERIFICATION_REQUIRED", "1") == "1",         # 是否需要验证
    "TARGET_GROUP_ID": int(os.getenv("TARGET_GROUP_ID", "-1002023834812")),  # 目标群组ID (@id520)
    "CHECK_INTERVAL": int(os.getenv("VERIFICATION_CHECK_INTERVAL", "60"))  # 验证检查间隔（秒）
}

# 特殊群组配置
SPECIAL_GROUP_ID = int(os.getenv("SPECIAL_GROUP_ID", "-1002312536972"))  # 特定播报群组ID

def get_config():
    """获取所有配置"""
    return {
        "telegram": TELEGRAM_CONFIG,
        "database": DB_CONFIG,
        "api": API_CONFIG,
        "game": GAME_CONFIG,
        "algorithm": ALGORITHM_CONFIG,
        "broadcast": BROADCAST_CONFIG,
        "prediction": PREDICTION_CONFIG,
        "cache": CACHE_CONFIG,
        "verification": VERIFICATION_CONFIG
    }

def log_config():
    """记录配置信息"""
    logger.info("加载配置完成")
    logger.debug(f"Telegram配置: {TELEGRAM_CONFIG}")
    logger.debug(f"数据库配置: {DB_CONFIG}")
    logger.debug(f"API配置: {API_CONFIG}")
    logger.debug(f"游戏规则配置: {GAME_CONFIG}")
    logger.debug(f"算法配置: {ALGORITHM_CONFIG}")
    logger.debug(f"播报配置: {BROADCAST_CONFIG}")
    logger.debug(f"预测配置: {PREDICTION_CONFIG}")
    logger.debug(f"缓存配置: {CACHE_CONFIG}")
    logger.debug(f"验证配置: {VERIFICATION_CONFIG}")

# 导出常用配置变量，方便直接导入
BOT_TOKEN = TELEGRAM_CONFIG["BOT_TOKEN"]
ADMIN_ID = TELEGRAM_CONFIG["ADMIN_ID"]
LOTTERY_API = API_CONFIG["LOTTERY_API"]
VERIFICATION_REQUIRED = VERIFICATION_CONFIG["REQUIRED"]
TARGET_GROUP_ID = VERIFICATION_CONFIG["TARGET_GROUP_ID"]
# SPECIAL_GROUP_ID 已在上面定义 