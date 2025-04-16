import json
import requests
import re
import time
from datetime import datetime
from loguru import logger
import random
from functools import lru_cache
import urllib3  # 添加导入

# 禁用不安全请求的警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from ..config.config_manager import GAME_CONFIG, LOTTERY_API, API_CONFIG
from ..data.cache_manager import cache
from ..config.proxy_config import get_proxy_settings, get_ssl_verify

# 预测类型名称映射
PREDICTION_TYPE_NAMES = {
    'single_double': '单双预测',
    'big_small': '大小预测',
    'kill_group': '杀组预测',
    'double_group': '双组预测'
}

def calculate_win_rate(history, pred_type):
    """计算最近100期的胜率"""
    if not history:
        return 0.0, 0
        
    # 只统计已开奖的记录，剔除未知结果的记录
    completed_records = [r for r in history if r.get('result') and r.get('result') != '未知']
    if not completed_records:
        return 0.0, 0
        
    # 取最近100期已开奖的记录
    recent_records = completed_records[-100:]
    correct_count = 0
    
    for record in recent_records:
        try:
            # 获取记录信息
            is_correct = record.get('is_correct')
            
            # 如果记录中已经包含了正确性信息，直接使用
            if is_correct is not None:
                if is_correct:
                    correct_count += 1
                continue
                
            # 否则，根据预测类型判断是否正确
            record_pred = record.get('prediction', '')
            is_big = record.get('is_big', False)
            is_odd = record.get('is_odd', False)
            
            if pred_type == 'single_double':
                # 单双预测 - 判断是否包含"单"或"双"，而不是完整的预测内容
                # 检查预测内容是否包含数字（如"小11"）
                if re.search(r'\d+', record_pred):
                    # 如果包含数字，需要精确匹配
                    actual_result = '单' if is_odd else '双'
                    # 提取预测中的单双部分
                    pred_single_double = '单' if '单' in record_pred else '双'
                    is_correct = pred_single_double == actual_result
                else:
                    # 原有逻辑
                    actual_result = '单' if is_odd else '双'
                    is_correct = ('单' in record_pred and actual_result == '单') or ('双' in record_pred and actual_result == '双')
            elif pred_type == 'big_small':
                # 大小预测 - 判断是否包含"大"或"小"，而不是完整的预测内容
                # 检查预测内容是否包含数字（如"小11"）
                if re.search(r'\d+', record_pred):
                    # 如果包含数字，需要精确匹配
                    actual_result = '大' if is_big else '小'
                    # 提取预测中的大小部分
                    pred_big_small = '大' if '大' in record_pred else '小'
                    is_correct = pred_big_small == actual_result
                else:
                    # 原有逻辑
                    actual_result = '大' if is_big else '小'
                    is_correct = ('大' in record_pred and actual_result == '大') or ('小' in record_pred and actual_result == '小')
            elif pred_type == 'kill_group':
                # 杀组预测 - 修复逻辑：预测要杀掉的组合与实际结果不同时才正确
                # 从预测内容中提取要杀掉的组合
                kill_combo = ""
                if "杀" in record_pred:
                    kill_combo = record_pred.replace("杀", "")
                actual_result = f"{'大' if is_big else '小'}{'单' if is_odd else '双'}"
                # 杀组预测成功：预测要杀掉的组合与实际结果不同
                is_correct = kill_combo != actual_result
            elif pred_type == 'double_group':
                # 双组预测
                try:
                    # 处理双组预测格式
                    if ':' in record_pred:
                        pred_parts = record_pred.split(':')[0].split('/')
                    else:
                        pred_parts = record_pred.split('/')
                        
                    actual_result = f"{'大' if is_big else '小'}{'单' if is_odd else '双'}"
                    is_correct = any(combo == actual_result for combo in pred_parts)
                except:
                    is_correct = False
            
            if is_correct:
                correct_count += 1
                
        except Exception as e:
            logger.warning(f"计算胜率时处理记录失败: {e}")
            continue
    
    # 计算胜率
    win_rate = correct_count / len(recent_records) * 100 if recent_records else 0
    
    return win_rate, len(recent_records)

def fetch_lottery_data(page=1, min_records=10, max_retries=None):
    """获取开奖数据
    page: 页码
    min_records: 最少需要获取的记录数
    max_retries: 最大重试次数
    """
    if max_retries is None:
        max_retries = API_CONFIG["MAX_RETRIES"]
        
    try:
        all_data = []
        current_page = page
        retry_count = 0
        
        # 记录上次API请求日志的时间
        last_api_log_time = cache.get('last_api_log_time', 0)
        current_time = time.time()
        should_log = current_time - last_api_log_time > 60  # 每分钟最多记录一次
        
        # 设置请求头，模拟浏览器访问
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.zuzu28.com/',
            'Origin': 'https://www.zuzu28.com',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        
        # 获取代理设置
        proxies = get_proxy_settings()
        verify_ssl = get_ssl_verify()
        
        # 记录网络设置信息
        if should_log and retry_count == 0:
            logger.info(f"使用代理: {bool(proxies)}, SSL验证: {verify_ssl}")
        
        # 增加会话级别的错误处理
        session = requests.Session()
        session.mount('http://', requests.adapters.HTTPAdapter(max_retries=3))
        session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
        
        while len(all_data) < min_records:
            try:
                # 减少日志输出
                if should_log:
                    logger.info(f"获取开奖数据，页码: {current_page}")
                    cache['last_api_log_time'] = current_time
                
                url = f"{LOTTERY_API}?page={current_page}&type=1"
                
                try:
                    # 首先尝试使用会话进行请求
                    response = session.get(
                        url,
                        headers=headers,
                        timeout=API_CONFIG["TIMEOUT"],
                        verify=verify_ssl,
                        proxies=proxies
                    )
                except (requests.RequestException, ConnectionResetError) as session_error:
                    if should_log:
                        logger.warning(f"会话请求失败，尝试直接请求: {session_error}")
                    
                    # 如果会话请求失败，尝试直接请求
                    response = requests.get(
                        url,
                        headers=headers,
                        timeout=API_CONFIG["TIMEOUT"],
                        verify=False,  # 直接禁用SSL验证
                        proxies=proxies
                    )
                
                response.raise_for_status()  # 检查HTTP错误
                
                # 尝试解析JSON数据
                try:
                    data = response.json()
                except json.JSONDecodeError as json_error:
                    if should_log:
                        logger.warning(f"JSON解析失败: {json_error}, 尝试修复响应")
                    
                    # 尝试修复和解析JSON响应
                    content = response.text
                    # 移除可能导致解析错误的字符
                    content = re.sub(r'[\x00-\x1F\x7F]', '', content)
                    data = json.loads(content)
                
                if data['code'] != 1 or not data['data']:
                    if should_log:
                        logger.warning(f"API返回无效数据: {data}")
                    break
                
                # 处理 API 返回的数据
                processed_data = []
                for item in data['data']:
                    # 确保数据包含必要的字段，处理字段名差异
                    processed_item = item.copy()
                    
                    # 处理 opencode 和 opennum 字段的一致性
                    if 'opennum' in item and 'opencode' not in item:
                        processed_item['opencode'] = item['opennum']
                    elif 'opencode' in item and 'opennum' not in item:
                        processed_item['opennum'] = item['opencode']
                    
                    processed_data.append(processed_item)
                
                all_data.extend(processed_data)
                current_page += 1
                
                if current_page > 5:  # 最多查询5页，防止无限循环
                    break
                    
                # 重置重试计数
                retry_count = 0
                
                # 成功获取数据后短暂休息，避免频繁请求
                time.sleep(random.uniform(0.5, 1.5))
                
            except (requests.RequestException, json.JSONDecodeError, KeyError, ConnectionResetError, ConnectionError) as e:
                retry_count += 1
                if retry_count > max_retries:
                    logger.error(f"获取开奖数据失败，超过最大重试次数: {e}")
                    break
                    
                logger.warning(f"获取开奖数据失败，重试中 ({retry_count}/{max_retries}): {e}")
                
                # 使用指数退避策略
                wait_time = 2 ** retry_count + random.uniform(0, 1)
                if should_log:
                    logger.info(f"等待 {wait_time:.2f} 秒后重试")
                time.sleep(wait_time)
                
        return all_data
        
    except Exception as e:
        logger.error(f"获取开奖数据失败: {e}")
        return []

@lru_cache(maxsize=128)
def parse_lottery_numbers(opennum):
    """解析开奖号码"""
    numbers = [int(n) for n in opennum.split('+')]
    return numbers

def check_combination_type(numbers):
    """判断开奖号码组合类型"""
    # 排序后的号码用于判断顺子
    sorted_nums = sorted(numbers)
    
    # 判断豹子
    if len(set(numbers)) == 1:
        return "豹子"
    
    # 判断对子
    if len(set(numbers)) == 2:
        return "对子"
    
    # 判断顺子
    def is_sequence(nums):
        # 普通顺子
        if nums[2] - nums[1] == 1 and nums[1] - nums[0] == 1:
            return True
        # 特殊顺子 (890, 901, 012)
        if nums == [0, 1, 2] or nums == [8, 9, 0] or nums == [9, 0, 1]:
            return True
        return False
    
    if is_sequence(sorted_nums):
        return "顺子"
    
    return "杂六"

def analyze_lottery_data(opennum, total_sum):
    """分析开奖数据"""
    numbers = parse_lottery_numbers(opennum)
    
    is_big = total_sum >= GAME_CONFIG["BIG_BOUNDARY"]
    is_odd = total_sum % 2 == 1
    combination_type = check_combination_type(numbers)
    
    return {
        'is_big': is_big,
        'is_odd': is_odd,
        'combination_type': combination_type
    }

def process_double_group_numbers(numbers_text, prediction_content=""):
    """处理双组预测特码"""
    try:
        # 从文本中提取数字
        if "[" in numbers_text and "]" in numbers_text:
            # 提取方括号中的内容
            inner_content = numbers_text[numbers_text.find("[") + 1:numbers_text.find("]")]
            # 分割数字
            number_parts = inner_content.split(",")
            # 清理每个数字
            formatted_numbers = []
            for num_part in number_parts:
                # 清理可能的引号、空格等
                num_str = num_part.strip().strip("`").strip("'").strip("\"").strip()
                if num_str:
                    try:
                        # 转换为整数再格式化，确保两位数
                        num_int = int(num_str)
                        # 确保数字在0-27范围内
                        num_int = max(0, min(num_int, 27))
                        formatted_numbers.append(f"{num_int:02d}")
                    except ValueError:
                        # 如果无法转换为整数，检查是否已经是格式化的数字
                        if num_str.isdigit() and len(num_str) <= 2:
                            formatted_numbers.append(f"{int(num_str):02d}")
        else:
            # 如果没有方括号，尝试从整个文本中提取数字
            formatted_numbers = []
            # 使用正则表达式提取所有数字
            import re
            number_matches = re.findall(r'\b\d{1,2}\b', numbers_text)
            for num_str in number_matches:
                try:
                    num_int = int(num_str)
                    # 确保数字在0-27范围内
                    num_int = max(0, min(num_int, 27))
                    formatted_numbers.append(f"{num_int:02d}")
                except ValueError:
                    continue
        
        # 如果没有提取到足够的数字，尝试从预测内容中分析组合类型并生成数字
        if len(formatted_numbers) < 2 and prediction_content:
            # 解析预测内容中的组合类型
            prediction_types = []
            if "大单" in prediction_content:
                prediction_types.append("大单")
            if "大双" in prediction_content:
                prediction_types.append("大双")
            if "小单" in prediction_content:
                prediction_types.append("小单")
            if "小双" in prediction_content:
                prediction_types.append("小双")
            
            # 如果找到了组合类型，生成符合条件的特码
            if prediction_types:
                generated_numbers = generate_numbers_by_prediction_types(prediction_types)
                # 将生成的数字添加到格式化数字列表
                for num in generated_numbers:
                    if num not in formatted_numbers:
                        formatted_numbers.append(num)
        
        # 确保至少有两个不同的数字
        while len(formatted_numbers) < 2:
            # 如果已有一个数字，确保生成一个不同区间的数字
            if formatted_numbers:
                existing_num = int(formatted_numbers[0])
                # 生成一个不同区间的数字
                if existing_num < 14:  # 如果现有数字是小区间
                    new_num = random.randint(14, 27)  # 生成大区间数字
                else:  # 如果现有数字是大区间
                    new_num = random.randint(0, 13)  # 生成小区间数字
            else:
                # 如果没有数字，随机生成两个来自不同区间的数字
                small_num = random.randint(0, 13)
                large_num = random.randint(14, 27)
                formatted_numbers.append(f"{small_num:02d}")
                formatted_numbers.append(f"{large_num:02d}")
                break
            
            # 格式化并添加新生成的数字
            new_num_str = f"{new_num:02d}"
            if new_num_str not in formatted_numbers:
                formatted_numbers.append(new_num_str)
        
        # 移除可能的重复数字
        formatted_numbers = list(set(formatted_numbers))
        
        # 如果仍然不足两个数字，再次使用随机数字补充
        while len(formatted_numbers) < 2:
            new_num = f"{random.randint(0, 27):02d}"
            if new_num not in formatted_numbers:
                formatted_numbers.append(new_num)
        
        # 排序数字以保持一致性
        formatted_numbers.sort(key=lambda x: int(x))
        
        # 最多保留两个数字
        formatted_numbers = formatted_numbers[:2]
        
        # 构建标记格式
        formatted_nums = [f"`{num}`" for num in formatted_numbers]
        return f"[{','.join(formatted_nums)}]"
    except Exception as e:
        logger.warning(f"处理双组预测特码失败: {e}")
        # 生成两个均衡分布的随机数字作为后备
        small_num = f"{random.randint(0, 13):02d}"
        large_num = f"{random.randint(14, 27):02d}"
        return f"[`{small_num}`,`{large_num}`]"

def generate_number_for_prediction_type(pred_type):
    """为特定预测类型生成一个符合条件的特码数字"""
    # 定义各类型的数字范围
    type_ranges = {
        '大单': list(range(15, 28, 2)),  # 15,17,19,21,23,25,27
        '大双': list(range(14, 28, 2)),  # 14,16,18,20,22,24,26
        '小单': list(range(1, 14, 2)),   # 1,3,5,7,9,11,13
        '小双': list(range(0, 14, 2))    # 0,2,4,6,8,10,12
    }
    
    # 查找匹配的类型范围
    for type_name, num_range in type_ranges.items():
        if type_name in pred_type:
            # 从符合条件的范围中随机选择一个数字
            if num_range:
                # 增加额外随机性：10%的概率选择范围内的极值
                if random.random() < 0.1:
                    if type_name == '大单' or type_name == '大双':
                        # 大范围选择高极值
                        high_extremes = num_range[-3:] if len(num_range) >= 3 else num_range
                        num = random.choice(high_extremes)
                    else:
                        # 小范围选择低极值
                        low_extremes = num_range[:3] if len(num_range) >= 3 else num_range
                        num = random.choice(low_extremes)
                else:
                    # 常规随机选择
                    num = random.choice(num_range)
                return f"{num:02d}"
            break
    
    # 如果没有匹配到任何类型，在整个范围内随机选择
    return f"{random.randint(0, 27):02d}"

def generate_numbers_by_prediction_types(prediction_types):
    """根据预测类型生成符合条件的特码数字列表"""
    numbers = []
    used_ranges = []  # 记录已使用的数字区间
    
    # 为每种预测类型生成一个特码
    for pred_type in prediction_types:
        retry_count = 0
        while retry_count < 3:  # 最多尝试3次以避免无限循环
            number = generate_number_for_prediction_type(pred_type)
            if number:
                num_value = int(number)
                
                # 判断这个数字是否在已使用的范围内
                in_used_range = False
                for range_min, range_max in used_ranges:
                    if range_min <= num_value <= range_max:
                        in_used_range = True
                        break
                
                if not in_used_range or retry_count == 2:
                    numbers.append(number)
                    # 记录这个数字周围的范围
                    range_min = max(0, num_value - 5)
                    range_max = min(27, num_value + 5)
                    used_ranges.append((range_min, range_max))
                    break
            
            retry_count += 1
    
    # 如果没有生成任何数字，添加均匀分布的随机数字
    if not numbers:
        # 生成一个0-13范围内的数字和一个14-27范围内的数字
        small_number = random.randint(0, 13)
        large_number = random.randint(14, 27)
        numbers = [f"{small_number:02d}", f"{large_number:02d}"]
    
    # 如果只生成了一个数字，添加另一个互补范围的数字
    if len(numbers) == 1:
        first_num = int(numbers[0])
        if first_num < 14:
            # 第一个是小范围，添加一个大范围数字
            second_num = random.randint(14, 27)
        else:
            # 第一个是大范围，添加一个小范围数字
            second_num = random.randint(0, 13)
        numbers.append(f"{second_num:02d}")
    
    # 确保返回的数字不重复
    numbers = list(set(numbers))
    while len(numbers) < 2:
        new_num = f"{random.randint(0, 27):02d}"
        if new_num not in numbers:
            numbers.append(new_num)
    
    # 对数字进行排序
    numbers.sort(key=lambda x: int(x))
    
    return numbers

def format_broadcast_message(records):
    """格式化播报消息"""
    try:
        # 确保只取最近10期数据
        records = records[:10]
        # 按期号从小到大排序
        sorted_records = sorted(records, key=lambda x: x[1])
        
        message = "📊 开奖播报\n\n"
        
        if not records:
            return "暂无开奖记录"
        
        # 获取最新一期记录
        latest_record = sorted_records[-1]
        
        # 确保记录包含所有必要字段
        if len(latest_record) < 8:
            logger.error(f"记录格式错误: {latest_record}")
            return "数据格式错误"
            
        # 1. 最新开奖单独提炼 - 分行显示
        qihao = latest_record[1]
        opennum = latest_record[3]
        total_sum = latest_record[4]
        is_big = latest_record[5]
        is_odd = latest_record[6]
        combination = latest_record[7]
        
        message += f"🔥 最新开奖 {qihao}期\n"
        message += f"号码: `{opennum}`\n"
        message += f"和值: `{int(total_sum):02d}`\n"
        message += f"组合: `{is_big and '大' or '小'}{is_odd and '单' or '双'}` `{combination}`\n\n"
        
        # 2. 历史记录 - 去掉最新的一期，只展示之前的记录
        message += "📈 历史记录:\n"
        
        # 检查是否有足够的历史记录可显示
        history_records = sorted_records[:-1]  # 排除最新一期
        
        if not history_records:
            # 尝试从数据库获取更多记录
            try:
                from ..data.db_manager import db_manager
                more_records = db_manager.get_recent_records(15)  # 获取更多历史记录
                
                if more_records and len(more_records) > 1:
                    # 重新按期号排序
                    more_sorted_records = sorted(more_records, key=lambda x: x[1])
                    # 使用除了最新记录之外的记录
                    history_records = [r for r in more_sorted_records if r[1] != qihao]
                    
                    # 倒序展示历史记录(最新的先显示)
                    for record in reversed(history_records[:9]):  # 最多显示9条历史记录
                        if len(record) >= 8:  # 确保记录格式正确
                            record_qihao = record[1]
                            record_opennum = record[3]
                            record_sum = record[4]
                            record_is_big = record[5]
                            record_is_odd = record[6]
                            record_combination = record[7]
                            
                            # 使用与图片一致的格式，确保sum值为两位数
                            message += f"• `{record_qihao}`期: `{record_opennum}`=`{int(record_sum):02d}` `{record_is_big and '大' or '小'}{record_is_odd and '单' or '双'}` `{record_combination}`\n"
                else:
                    message += "暂无历史记录\n"
            except Exception as e:
                logger.error(f"尝试获取更多历史记录失败: {e}")
                message += "暂无历史记录\n"
        else:
            # 正常情况：倒序展示历史记录(最新的先显示)
            for record in reversed(history_records):  # 排除最新一期
                if len(record) >= 8:  # 确保记录格式正确
                    record_qihao = record[1]
                    record_opennum = record[3]
                    record_sum = record[4]
                    record_is_big = record[5]
                    record_is_odd = record[6]
                    record_combination = record[7]
                    
                    # 使用与图片一致的格式，确保sum值为两位数
                    message += f"• `{record_qihao}`期: `{record_opennum}`=`{int(record_sum):02d}` `{record_is_big and '大' or '小'}{record_is_odd and '单' or '双'}` `{record_combination}`\n"
        
        return message
            
    except Exception as e:
        logger.error(f"格式化播报消息失败: {e}")
        return "格式化消息失败"

def format_prediction_message(prediction, history=None):
    """格式化预测消息"""
    try:
        # 解析预测数据
        pred_type = prediction.get('prediction_type', '')
        pred_content = prediction.get('prediction', '')
        qihao = prediction.get('qihao', '')
        algorithm_used = prediction.get('algorithm_used', None)
        switch_info = prediction.get('switch_info', None)
        
        # 获取预测类型名称
        pred_type_name = PREDICTION_TYPE_NAMES.get(pred_type, pred_type)
        
        # 计算胜率
        win_rate = 0.0
        win_count = 0
        if history:
            win_rate, win_count = calculate_win_rate(history, pred_type)
        
        # 构建消息 - 修改为显示整数百分比
        message = f"📊 {pred_type_name}丨 胜率：{int(win_rate)}% ({win_count}期)\n"
        
        # 添加历史记录
        if history:
            try:
                # 确保历史记录是列表
                if isinstance(history, list):
                    # 固定显示的历史记录数量为10期
                    display_limit = 10
                    # 只显示已有结果且结果不是"未知"的记录
                    valid_history = [
                        record for record in history 
                        if 'result' in record and record.get('result') != '未知'
                    ]
                    
                    # 按期号从小到大排序
                    valid_history.sort(key=lambda x: int(x.get('qihao', '0')))
                    
                    # 取最近的记录
                    display_history = valid_history[-display_limit:]
                    
                    # 非智能推荐的历史记录处理
                    message += "历史开奖结果：\n"
                    
                    for record in display_history:
                        try:
                            # 获取历史记录信息
                            record_qihao = record.get('qihao', '未知')
                            record_pred = record.get('prediction', '')
                            
                            # 获取开奖结果
                            result = record.get('result', '未知')
                            if result == '未知':
                                continue
                            
                            # 修改结果描述格式
                            total_sum = record.get('sum', 0)
                            is_big = record.get('is_big', False)
                            is_odd = record.get('is_odd', False)
                            combination_type = record.get('combination_type', '未知')
                            # 构建符合模板的结果描述: "0+9+5=14 大双 杂六"
                            result_desc = f"`{result}`=`{int(total_sum):02d}` `{is_big and '大' or '小'}{is_odd and '单' or '双'}` `{combination_type}`"
                            
                            # 判断预测是否正确
                            try:
                                prediction_correct = False
                                
                                if pred_type == 'single_double':
                                    # 单双预测
                                    actual_result = '单' if is_odd else '双'
                                    prediction_correct = ('单' in record_pred and actual_result == '单') or ('双' in record_pred and actual_result == '双')
                                elif pred_type == 'big_small':
                                    # 大小预测
                                    actual_result = '大' if is_big else '小'
                                    prediction_correct = ('大' in record_pred and actual_result == '大') or ('小' in record_pred and actual_result == '小')
                                elif pred_type == 'kill_group':
                                    # 杀组预测
                                    actual_result = f"{'大' if is_big else '小'}{'单' if is_odd else '双'}"
                                    kill_combo = ""
                                    if "杀" in record_pred:
                                        kill_combo = record_pred.replace("杀", "")
                                    prediction_correct = kill_combo != actual_result
                                elif pred_type == 'double_group':
                                    # 双组预测
                                    actual_result = f"{'大' if is_big else '小'}{'单' if is_odd else '双'}"
                                    if ':' in record_pred:
                                        pred_parts = record_pred.split(':')[0].split('/')
                                    else:
                                        pred_parts = record_pred.split('/')
                                    prediction_correct = any(combo == actual_result for combo in pred_parts)
                            except Exception as e:
                                logger.warning(f"判断预测正确性失败: {e}")
                                continue
                            
                            # 添加结果标记
                            result_mark = "✅" if prediction_correct else "❌"
                            
                            # 格式化记录行 - 确保使用一致的反引号包裹，不再显示算法号
                            if pred_type == 'double_group':
                                # 双组预测特殊格式
                                try:
                                    if ':' in record_pred:
                                        pred_text = record_pred.split(':')[0]
                                        numbers_text = record_pred.split(':')[1].strip() if len(record_pred.split(':')) > 1 else ""
                                        
                                        # 使用辅助函数处理特码数字，传入预测内容
                                        numbers_formatted = process_double_group_numbers(numbers_text, pred_text)
                                        
                                        # 构建输出行
                                        message += f"`{record_qihao}`期：`{pred_text}`"
                                        message += f" {numbers_formatted}➡️{result_desc} {result_mark}\n"
                                    else:
                                        # 不包含冒号的情况，传入预测内容
                                        numbers_formatted = process_double_group_numbers("", record_pred)
                                        message += f"`{record_qihao}`期：`{record_pred}` {numbers_formatted}➡️{result_desc} {result_mark}\n"
                                except Exception as e:
                                    logger.warning(f"格式化双组预测记录失败: {e}")
                                    continue
                            else:
                                # 所有预测类型都不显示算法号
                                message += f"`{record_qihao}`期：`{record_pred}`➡️{result_desc} {result_mark}\n"
                        except Exception as e:
                            logger.warning(f"处理单条历史记录失败: {e}")
                            continue
            except Exception as e:
                logger.error(f"处理历史记录部分失败: {e}")
                message += "历史记录处理失败\n"
        
        # 添加一条横线分割历史记录和最新预测
        message += "\n"
        
        # 不再需要获取算法号，因为不再显示
        
        # 添加最新预测
        if pred_type == 'double_group':
            # 双组预测特殊格式
            try:
                if ':' in pred_content:
                    # 解析带特码的双组预测
                    pred_parts = pred_content.split(':')
                    combos = pred_parts[0]
                    numbers = pred_parts[1].strip() if len(pred_parts) > 1 else ""
                    
                    # 使用辅助函数处理特码数字
                    numbers_formatted = process_double_group_numbers(numbers, combos)
                    
                    # 构建输出行
                    message += f"`{qihao}`期：`{combos}` {numbers_formatted}"
                else:
                    # 不包含冒号的情况
                    numbers_formatted = process_double_group_numbers("", pred_content)
                    message += f"`{qihao}`期：`{pred_content}` {numbers_formatted}"
            except Exception as e:
                logger.warning(f"格式化双组预测失败: {e}")
                message += f"`{qihao}`期：`{pred_content}`"
        else:
            # 其他预测类型
            message += f"`{qihao}`期：`{pred_content}`"
        
        return message
    except Exception as e:
        logger.error(f"格式化预测消息失败: {e}")
        return f"格式化消息失败: {str(e)}"

def parse_datetime(date_str):
    """解析日期时间字符串"""
    try:
        # 尝试多种格式解析
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y年%m月%d日 %H:%M:%S",
            "%m-%d %H:%M:%S"  # 添加MM-DD格式支持
        ]
        
        current_year = datetime.now().year
        
        for fmt in formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                # 对于没有年份的格式，添加当前年份
                if fmt == "%m-%d %H:%M:%S":
                    return parsed_date.replace(year=current_year)
                return parsed_date
            except ValueError:
                continue
        
        # 检查是否为"MM-d HH:mm:ss"格式（如"04-6 02:22:30"）
        match = re.search(r'(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2}):(\d{1,2})', date_str)
        if match:
            month, day, hour, minute, second = map(int, match.groups())
            return datetime(current_year, month, day, hour, minute, second)
        
        # 尝试提取日期部分（原有逻辑）
        match = re.search(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})[日]?\s+(\d{1,2}):(\d{1,2}):(\d{1,2})', date_str)
        if match:
            year, month, day, hour, minute, second = map(int, match.groups())
            return datetime(year, month, day, hour, minute, second)
        
        # 如果还是失败，返回当前时间
        logger.warning(f"无法解析日期时间: {date_str}，使用当前时间")
        return datetime.now()
    except Exception as e:
        logger.error(f"解析日期时间失败: {date_str}, {e}")
        return datetime.now()

def format_lottery_record(record):
    """格式化开奖记录为消息格式"""
    try:
        # 解析记录信息
        qihao = record[1]
        # 检查时间是否为None
        if record[2] is None:
            opentime = "未知时间"
        else:
            opentime = record[2].strftime("%Y-%m-%d %H:%M:%S")
        opennum = record[3]
        total_sum = record[4]
        is_big = record[5]
        is_odd = record[6]
        combination = record[7]
        
        # 构建消息
        message = f"🔢 *{qihao}期开奖结果* 🔢\n"
        message += f"⏱️ 开奖时间: {opentime}\n"
        message += f"🎲 开奖号码: {opennum}\n"
        message += f"📊 和值: {total_sum}\n"
        message += f"📈 结果: {'大' if is_big else '小'}{'单' if is_odd else '双'}\n"
        message += f"🎯 类型: {combination}\n"
        
        return message
    except Exception as e:
        logger.error(f"格式化开奖记录失败: {e}")
        return f"格式化开奖记录失败: {e}" 