from datetime import datetime
from loguru import logger

from ..config.config_manager import CACHE_CONFIG

# 缓存机制
cache = {
    'last_broadcast_qihao': None,
    'last_prediction_qihao': None,
    'last_broadcast_message': None,
    'last_prediction_message': None,
    'last_lottery_data': None,
    'last_broadcast_time': None,
    'last_prediction_time': None,
    'cache_expiry': {}  # 缓存过期时间记录
}

def is_cache_valid(cache_key):
    """检查缓存是否有效"""
    if cache_key not in cache['cache_expiry']:
        return False
    return datetime.now().timestamp() < cache['cache_expiry'][cache_key]

def update_cache(cache_key, value, ttl):
    """更新缓存并设置过期时间"""
    cache[cache_key] = value
    cache['cache_expiry'][cache_key] = datetime.now().timestamp() + ttl

def cleanup_cache(context=None):
    """清理过期缓存"""
    if 'cache_expiry' not in cache:
        cache['cache_expiry'] = {}
        return
        
    current_time = datetime.now().timestamp()
    expired_keys = [
        key for key, expiry_time in cache['cache_expiry'].items()
        if current_time > expiry_time
    ]
    for key in expired_keys:
        if key in cache:
            del cache[key]
        del cache['cache_expiry'][key]
    logger.debug(f"已清理 {len(expired_keys)} 个过期缓存项") 