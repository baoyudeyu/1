from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

# 主键盘布局
MAIN_KEYBOARD = ReplyKeyboardMarkup([
    ['开奖播报', '停止播报'],
    ['单双预测', '停止单双'],
    ['大小预测', '停止大小'],
    ['杀组预测', '停止杀组'],
    ['双组预测', '停止双组']
], resize_keyboard=True)

# 帮助菜单键盘
HELP_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("📊 播报功能", callback_data='help_broadcast'),
     InlineKeyboardButton("🎯 预测功能", callback_data='help_prediction')],
    [InlineKeyboardButton("⚙️ 算法说明", callback_data='help_algorithm'),
     InlineKeyboardButton("❓ 常见问题", callback_data='help_faq')]
])

# 播报功能键盘
BROADCAST_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("📊 开始播报", callback_data="start_broadcast"),
        InlineKeyboardButton("🛑 停止播报", callback_data="stop_broadcast")
    ],
    [
        InlineKeyboardButton("📜 历史记录", callback_data="history_broadcast"),
        InlineKeyboardButton("📊 数据统计", callback_data="stats_broadcast")
    ],
    [
        InlineKeyboardButton("◀️ 返回帮助", callback_data="back_to_help"),
        InlineKeyboardButton("🏠 主菜单", callback_data="back_to_main")
    ]
])

# 预测功能键盘
PREDICTION_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🎲 单双预测", callback_data="start_single_double"),
        InlineKeyboardButton("📏 大小预测", callback_data="start_big_small")
    ],
    [
        InlineKeyboardButton("🎯 杀组预测", callback_data="start_kill_group"),
        InlineKeyboardButton("🎮 双组预测", callback_data="start_double_group")
    ],
    [
        InlineKeyboardButton("◀️ 返回帮助", callback_data="back_to_help"),
        InlineKeyboardButton("🏠 主菜单", callback_data="back_to_main")
    ]
])

# 算法说明键盘
ALGORITHM_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("📊 算法性能", callback_data="algorithm_performance"),
        InlineKeyboardButton("📈 切换记录", callback_data="algorithm_switches")
    ],
    [
        InlineKeyboardButton("🔍 详细说明", callback_data="algorithm_details"),
        InlineKeyboardButton("⚙️ 高级设置", callback_data="algorithm_settings")
    ],
    [
        InlineKeyboardButton("◀️ 返回帮助", callback_data="back_to_help"),
        InlineKeyboardButton("🏠 主菜单", callback_data="back_to_main")
    ]
])

# 常见问题键盘
FAQ_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("📞 联系管理员", callback_data="contact_admin"),
        InlineKeyboardButton("🔄 重启服务", callback_data="restart_service")
    ],
    [
        InlineKeyboardButton("📋 使用教程", callback_data="user_guide"),
        InlineKeyboardButton("⚙️ 系统设置", callback_data="system_settings")
    ],
    [
        InlineKeyboardButton("◀️ 返回帮助", callback_data="back_to_help"),
        InlineKeyboardButton("🏠 主菜单", callback_data="back_to_main")
    ]
])

# 返回键盘
BACK_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("◀️ 返回帮助", callback_data="back_to_help"),
        InlineKeyboardButton("🏠 主菜单", callback_data="back_to_main")
    ]
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