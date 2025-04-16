import os
import sys
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

# 主键盘布局
MAIN_KEYBOARD = ReplyKeyboardMarkup([
    ['开奖播报', '停止播报'],
    ['单双预测', '大小预测'],
    ['杀组预测', '双组预测'],
    ['系统状态']
], resize_keyboard=True)

# 帮助菜单键盘
HELP_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("📊 播报功能", callback_data="help_broadcast"),
     InlineKeyboardButton("🎯 预测功能", callback_data="help_prediction")],
    [InlineKeyboardButton("⚙️ 算法说明", callback_data="help_algorithm"),
     InlineKeyboardButton("❓ 常见问题", callback_data="help_faq")],
    [InlineKeyboardButton("🏠 返回主菜单", callback_data="back_to_start")]
])

# 播报功能键盘
BROADCAST_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("📊 开始播报", callback_data="start_broadcast"),
     InlineKeyboardButton("🛑 停止播报", callback_data="stop_broadcast")],
    [InlineKeyboardButton("🔙 返回帮助", callback_data="view_help")]
])

# 预测功能键盘
PREDICTION_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🎲 单双预测", callback_data="start_single_double"),
     InlineKeyboardButton("📏 大小预测", callback_data="start_big_small")],
    [InlineKeyboardButton("🎯 杀组预测", callback_data="start_kill_group"),
     InlineKeyboardButton("🎮 双组预测", callback_data="start_double_group")],
    [InlineKeyboardButton("🔙 返回帮助", callback_data="view_help")]
])

# 算法说明键盘
ALGORITHM_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔄 切换算法", callback_data="switch_algorithm")],
    [InlineKeyboardButton("🔙 返回帮助", callback_data="view_help")]
])

# 常见问题键盘
FAQ_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("👨‍💻 联系管理员", url="https://t.me/admin")],
    [InlineKeyboardButton("🔙 返回帮助", callback_data="view_help")]
])

# 返回键盘
BACK_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔙 返回", callback_data="view_help")]
])

# 获取键盘布局的函数
def get_keyboard_by_type(keyboard_type):
    """根据类型获取键盘布局"""
    keyboards = {
        'main': MAIN_KEYBOARD,
        'help': HELP_KEYBOARD,
        'broadcast': BROADCAST_KEYBOARD,
        'prediction': PREDICTION_KEYBOARD,
        'algorithm': ALGORITHM_KEYBOARD,
        'faq': FAQ_KEYBOARD,
        'back': BACK_KEYBOARD
    }
    return keyboards.get(keyboard_type, BACK_KEYBOARD) 