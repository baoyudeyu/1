"""
代理配置模块，处理网络代理相关的配置
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 代理配置
PROXY_CONFIG = {
    "USE_PROXY": os.getenv("USE_PROXY", "0") == "1",  # 是否启用代理
    "HTTP_PROXY": os.getenv("HTTP_PROXY", ""),        # HTTP代理地址
    "HTTPS_PROXY": os.getenv("HTTPS_PROXY", ""),      # HTTPS代理地址
    "PROXY_USERNAME": os.getenv("PROXY_USERNAME", ""),  # 代理用户名
    "PROXY_PASSWORD": os.getenv("PROXY_PASSWORD", ""),  # 代理密码
    "NO_PROXY": os.getenv("NO_PROXY", "localhost,127.0.0.1"),  # 不使用代理的地址
    "VERIFY_SSL": os.getenv("VERIFY_SSL", "0") == "1"  # 是否验证SSL证书
}

def get_proxy_settings():
    """获取代理设置"""
    if not PROXY_CONFIG["USE_PROXY"]:
        return {}
        
    # 构建代理URL
    proxy_url = ""
    if PROXY_CONFIG["HTTP_PROXY"]:
        if PROXY_CONFIG["PROXY_USERNAME"] and PROXY_CONFIG["PROXY_PASSWORD"]:
            # 带认证的代理
            auth = f"{PROXY_CONFIG['PROXY_USERNAME']}:{PROXY_CONFIG['PROXY_PASSWORD']}@"
            http_proxy = PROXY_CONFIG["HTTP_PROXY"].replace("://", "://" + auth)
            https_proxy = PROXY_CONFIG["HTTPS_PROXY"].replace("://", "://" + auth) if PROXY_CONFIG["HTTPS_PROXY"] else http_proxy
        else:
            # 不带认证的代理
            http_proxy = PROXY_CONFIG["HTTP_PROXY"]
            https_proxy = PROXY_CONFIG["HTTPS_PROXY"] if PROXY_CONFIG["HTTPS_PROXY"] else http_proxy
            
        return {
            "http": http_proxy,
            "https": https_proxy
        }
    
    return {}
    
def get_ssl_verify():
    """获取SSL验证设置"""
    return PROXY_CONFIG["VERIFY_SSL"] 