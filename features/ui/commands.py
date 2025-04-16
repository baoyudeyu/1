import os
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger

from ..config.config_manager import ADMIN_ID, VERIFICATION_CONFIG
from ..data.db_manager import db_manager
from ..utils.message_utils import send_message_with_retry, edit_message_with_retry
from ..services.prediction import start_prediction
from ..prediction import predictor
from ..services.verification.verification_service import verify_user_access
from .keyboard_layouts import (
    MAIN_KEYBOARD, HELP_KEYBOARD, BROADCAST_KEYBOARD, 
    PREDICTION_KEYBOARD, ALGORITHM_KEYBOARD, FAQ_KEYBOARD, BACK_KEYBOARD
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /start 命令"""
    # 添加验证流程
    has_access = await verify_user_access(update, context)
    if not has_access:
        # 如果验证失败，不继续执行
        return
    
    welcome_message = (
        "🎮 *欢迎使用28游戏预测机器人* 🎮\n\n"
        "🔮 *主要功能*\n"
        "• 📊 实时开奖播报与数据分析\n"
        "• 🎯 基础预测功能\n"
        "• 📈 多维度数据统计与趋势分析\n\n"
        "🎲 *预测类型*\n"
        "• 单双预测 | 大小预测\n"
        "• 杀组预测 | 双组预测\n\n"
        "📱 *使用指南*\n"
        "请点击下方按钮开始使用各项功能："
    )
    
    # 创建内联键盘，将功能说明与按钮直接绑定
    START_INLINE_KEYBOARD = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 开奖播报", callback_data="start_broadcast"),
         InlineKeyboardButton("🛑 停止播报", callback_data="stop_broadcast")],
        [InlineKeyboardButton("🎲 单双预测", callback_data="start_single_double"),
         InlineKeyboardButton("📏 大小预测", callback_data="start_big_small")],
        [InlineKeyboardButton("🎮 双组预测", callback_data="start_double_group"),
         InlineKeyboardButton("🎯 杀组预测", callback_data="start_kill_group")],
        [InlineKeyboardButton("📊 系统状态", callback_data="view_status")]
    ])
    
    # 发送欢迎消息和内联键盘
    await update.message.reply_text(
        welcome_message,
        parse_mode='Markdown',
        reply_markup=START_INLINE_KEYBOARD
    )
    
    # 同时发送主键盘，方便用户后续操作
    await update.message.reply_text(
        "您也可以使用下方键盘快速操作：",
        reply_markup=MAIN_KEYBOARD
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /help 命令"""
    # 验证用户权限
    has_access = await verify_user_access(update, context)
    if not has_access:
        # 如果验证失败，不继续执行
        return
        
    help_message = (
        "📚 *帮助中心* 📚\n\n"
        "请选择以下选项获取详细帮助：\n\n"
        "📊 *播报功能* - 实时开奖结果推送\n"
        "🎯 *预测功能* - 智能预测与算法说明\n"
        "⚙️ *算法说明* - 动态切换与性能优化\n"
        "❓ *常见问题* - 使用指南与问题解答\n\n"
        "💡 *提示*：点击下方按钮进入对应的帮助页面"
    )
    await update.message.reply_text(
        help_message,
        parse_mode='Markdown',
        reply_markup=HELP_KEYBOARD
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /status 命令"""
    # 验证用户权限
    has_access = await verify_user_access(update, context)
    if not has_access:
        # 如果验证失败，不继续执行
        return
        
    from ..utils.message_handler import is_broadcasting
    
    # 获取当前时间
    from datetime import datetime
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    status_message = (
        "📊 *系统状态监控* 📊\n\n"
        f"⏱️ *当前时间*: {current_time}\n\n"
        "🔄 *服务状态*\n"
        f"• 开奖播报: {'🟢 运行中' if is_broadcasting else '🔴 已停止'}\n"
        "• 预测功能: 🟢 可用\n\n"
        "🧠 *算法状态*\n"
    )
    
    # 添加算法信息
    for pred_type, type_name in [
        ('single_double', '单双'),
        ('big_small', '大小'),
        ('kill_group', '杀组'),
        ('double_group', '双组')
    ]:
        algo_num = predictor.current_algorithms.get(pred_type, 1)
        best_algo = predictor.get_best_algorithm(pred_type)
        status_message += f"• {type_name}: {algo_num}号算法"
        
        if best_algo:
            success_rate = best_algo['success_rate'] * 100
            status_message += f" | 准确率: {success_rate:.1f}%\n"
        else:
            status_message += "\n"
    
    # 添加系统性能信息
    status_message += (
        "\n📈 *系统性能*\n"
        "• 动态切换: 已启用\n"
        "• 自适应学习: 已启用\n"
        "• 趋势分析: 已启用\n"
        "\n💡 *提示*: 使用 /help 查看更多功能说明"
    )
    
    await update.message.reply_text(
        status_message,
        parse_mode='Markdown'
    )

async def handle_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理帮助菜单回调"""
    query = update.callback_query
    
    # 必须回应所有的回调查询，否则用户会看到加载图标
    await query.answer()
    
    # 检查是否在目标群组中，如果是则不响应
    if update.effective_chat.id == VERIFICATION_CONFIG["TARGET_GROUP_ID"]:
        logger.info(f"忽略来自目标群组 {update.effective_chat.id} 的帮助回调")
        return
    
    if query.data == 'view_help':
        # 直接调用help_command的逻辑
        message = (
            "📚 *帮助中心* 📚\n\n"
            "请选择以下选项获取详细帮助：\n\n"
            "📊 *播报功能* - 实时开奖结果推送\n"
            "🎯 *预测功能* - 智能预测与算法说明\n"
            "⚙️ *算法说明* - 动态切换与性能优化\n"
            "❓ *常见问题* - 使用指南与问题解答\n\n"
            "💡 *提示*：点击下方按钮进入对应的帮助页面"
        )
        await edit_message_with_retry(
        context,
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        text=message,
        parse_mode='Markdown',
        reply_markup=HELP_KEYBOARD
        )
        return
        
    elif query.data == 'view_status':
        # 获取状态信息
        from ..utils.message_handler import is_broadcasting
        
        # 获取当前时间
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        status_message = (
            "📊 *系统状态监控* 📊\n\n"
            f"⏱️ *当前时间*: {current_time}\n\n"
            "🔄 *服务状态*\n"
            f"• 开奖播报: {'🟢 运行中' if is_broadcasting else '🔴 已停止'}\n"
            "• 预测功能: 🟢 可用\n\n"
            "🧠 *算法状态*\n"
        )
        
        # 添加算法信息
        for pred_type, type_name in [
            ('single_double', '单双'),
            ('big_small', '大小'),
            ('kill_group', '杀组'),
            ('double_group', '双组')
        ]:
            algo_num = predictor.current_algorithms.get(pred_type, 1)
            best_algo = predictor.get_best_algorithm(pred_type)
            status_message += f"• {type_name}: {algo_num}号算法"
            
            if best_algo:
                success_rate = best_algo['success_rate'] * 100
                status_message += f" | 准确率: {success_rate:.1f}%\n"
            else:
                status_message += "\n"
        
        # 添加系统性能信息
        status_message += (
            "\n📈 *系统性能*\n"
            "• 动态切换: 已启用\n"
            "• 自适应学习: 已启用\n"
            "• 趋势分析: 已启用\n"
            "\n💡 *提示*: 使用 /help 查看更多功能说明"
        )
        
        # 创建返回主菜单的按钮
        back_to_start = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 返回主菜单", callback_data="back_to_start")]
        ])
        
        await edit_message_with_retry(
        context,
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        text=status_message,
        parse_mode='Markdown',
        reply_markup=back_to_start
        )
        return
        
    elif query.data == 'back_to_start':
        # 返回主菜单
        welcome_message = (
            "🎮 *欢迎使用28游戏预测机器人* 🎮\n\n"
            "🔮 *主要功能*\n"
            "• 📊 实时开奖播报与数据分析\n"
            "• 🎯 基础预测功能\n"
            "• 📈 多维度数据统计与趋势分析\n\n"
            "🎲 *预测类型*\n"
            "• 单双预测 | 大小预测\n"
            "• 杀组预测 | 双组预测\n\n"
            "📱 *使用指南*\n"
            "请点击下方按钮开始使用各项功能："
        )
        
        # 创建内联键盘，将功能说明与按钮直接绑定
        START_INLINE_KEYBOARD = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 开奖播报", callback_data="start_broadcast"),
             InlineKeyboardButton("🛑 停止播报", callback_data="stop_broadcast")],
            [InlineKeyboardButton("🎲 单双预测", callback_data="start_single_double"),
             InlineKeyboardButton("📏 大小预测", callback_data="start_big_small")],
            [InlineKeyboardButton("🎮 双组预测", callback_data="start_double_group"),
             InlineKeyboardButton("🎯 杀组预测", callback_data="start_kill_group")],
            [InlineKeyboardButton("📊 系统状态", callback_data="view_status")]
        ])
        
        await edit_message_with_retry(
        context,
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        text=welcome_message,
        parse_mode='Markdown',
        reply_markup=START_INLINE_KEYBOARD
        )
        return
    
    # 处理原有的回调数据
    if query.data == 'help_broadcast':
        message = (
            "📊 *开奖播报功能* 📊\n\n"
            "实时接收最新开奖结果的推送服务。\n\n"
            "🔘 *开启方式*\n"
            "• 点击「开奖播报」按钮\n"
            "• 点击内联键盘的「📊 开奖播报」\n\n"
            "🔘 *关闭方式*\n"
            "• 点击「停止播报」按钮\n"
            "• 点击内联键盘的「🛑 停止播报」\n\n"
            "📋 *播报内容*\n"
            "• 期号与开奖时间\n"
            "• 开奖号码与和值\n"
            "• 大小单双分析\n"
            "• 最近十期走势\n\n"
            "⚙️ *相关设置*\n"
            "• 可通过管理员调整播报频率\n"
            "• 播报格式优化适配各种设备\n\n"
            "🔔 *注意事项*：开启后将持续接收推送，直到手动关闭"
        )
        
        await edit_message_with_retry(
        context,
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        text=message,
        parse_mode='Markdown',
        reply_markup=BACK_KEYBOARD
        )
        return
        
    elif query.data == 'help_prediction':
        message = (
            "🎯 *预测功能说明* 🎯\n\n"
            "基于智能算法的游戏结果预测服务。\n\n"
            "📊 *预测类型*\n"
            "• 单双预测：预测下一期结果为单数或双数\n"
            "• 大小预测：预测下一期结果为大数或小数\n"
            "• 杀组预测：排除一种可能性最小的组合\n"
            "• 双组预测：同时预测两种可能性最大的组合\n\n"
            "🧠 *算法特点*\n"
            "• 多算法智能切换\n"
            "• 自适应学习能力\n"
            "• 连续预测准确率分析\n"
            "• 趋势识别与波段抓取\n\n"
            "📈 *查看方式*\n"
            "• 点击对应预测按钮（单次预测）\n"
            "• 自动预测将定期推送\n\n"
            "⚠️ *免责声明*：预测结果仅供参考，不构成任何投资建议"
        )
        
        await edit_message_with_retry(
        context,
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        text=message,
        parse_mode='Markdown',
        reply_markup=BACK_KEYBOARD
        )
        return
        
    elif query.data == 'help_algorithm':
        message = (
            "⚙️ *算法原理说明* ⚙️\n\n"
            "🧠 *多算法系统*\n"
            "• 算法1：基于频率分析的预测\n"
            "• 算法2：基于周期循环的预测\n"
            "• 算法3：基于趋势转换的预测\n\n"
            "🔄 *动态切换机制*\n"
            "• 根据预测表现自动选择最优算法\n"
            "• 系统持续监控每个算法的准确率\n"
            "• 当准确率下降时自动切换算法\n\n"
            "📊 *性能优化逻辑*\n"
            "• 算法会自我学习并优化预测策略\n"
            "• 权重调整基于历史预测结果\n"
            "• 定期重新训练以适应新趋势\n\n"
            "🔍 *查看当前算法*\n"
            "可通过「系统状态」命令查看当前各预测类型使用的算法编号及准确率"
        )
        
        await edit_message_with_retry(
        context,
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        text=message,
        parse_mode='Markdown',
        reply_markup=BACK_KEYBOARD
        )
        return
        
    elif query.data == 'help_faq':
        message = (
            "❓ *常见问题解答* ❓\n\n"
            "🔍 *如何使用预测功能？*\n"
            "点击「单双预测」「大小预测」「杀组预测」或「双组预测」按钮，系统会立即生成当前最优算法的预测结果。\n\n"
            "🎲 *预测准确率如何？*\n"
            "系统会不断自我学习和优化算法，目前平均准确率在70%左右，但会因游戏规律变化而波动。\n\n"
            "🔐 *如何通过验证？*\n"
            "首次使用机器人时，您需要加入加拿大之家 (@id520) 群组，然后点击验证按钮。系统会自动检查您是否加入了群组，验证通过后即可使用全部功能。\n\n"
            "⏰ *预测多久更新一次？*\n"
            "系统每210秒会自动更新一次预测，您也可以随时手动获取最新预测。\n\n"
            "🛠 *遇到问题怎么办？*\n"
            "如有任何使用问题，请联系管理员寻求帮助。"
        )
        
        await edit_message_with_retry(
        context,
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        text=message,
        parse_mode='Markdown',
        reply_markup=BACK_KEYBOARD
        )
        return
    else:
        message = "请选择帮助选项"
        reply_markup = BACK_KEYBOARD
    
    # 使用edit_message_with_retry替代直接调用edit_message_text
    await edit_message_with_retry(
        context,
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        text=message, 
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理播报功能回调"""
    query = update.callback_query
    await query.answer()
    
    # 检查是否在目标群组中，如果是则不响应
    if update.effective_chat.id == VERIFICATION_CONFIG["TARGET_GROUP_ID"]:
        logger.info(f"忽略来自目标群组 {update.effective_chat.id} 的广播回调")
        return
    
    from ..utils.message_handler import start_broadcasting, stop_broadcasting, check_broadcasting_status
    from ..services.broadcast import send_broadcast
    
    if query.data == 'start_broadcast':
        # 启动播报
        success = start_broadcasting(update.effective_chat.id)
        if success:
            # 检查广播状态
            broadcasting_active = check_broadcasting_status()
            if not broadcasting_active:
                logger.warning("广播状态未正确更新，强制更新状态")
                # 再次尝试启动广播
                start_broadcasting(update.effective_chat.id)
            
            # 发送初始播报
            await send_broadcast(context, update.effective_chat.id)
            
            message = (
                "✅ *开奖播报已启动* ✅\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "📊 系统将自动推送最新开奖结果\n"
                "📋 每期结果包含以下信息：\n"
                "• 期号和开奖时间\n"
                "• 开奖号码和和值\n"
                "• 大小单双分析\n"
                "• 组合形态分析\n\n"
                "🔔 请保持聊天窗口开启以接收推送"
            )
            
            # 记录日志
            logger.info(f"用户 {update.effective_chat.id} 通过按钮启动了开奖播报")
        else:
            message = "❌ 播报启动失败，请稍后重试"
            logger.error(f"用户 {update.effective_chat.id} 尝试启动播报失败")
            
    elif query.data == 'stop_broadcast':
        # 停止播报
        success = stop_broadcasting(update.effective_chat.id)
        if success:
            # 检查广播状态
            broadcasting_active = check_broadcasting_status()
            if broadcasting_active and not db_manager.get_active_chats():
                logger.warning("广播状态未正确更新，强制更新状态")
                # 再次尝试停止广播
                stop_broadcasting(update.effective_chat.id)
                # 再次检查广播状态，确保状态正确
                broadcasting_active = check_broadcasting_status()
                logger.info(f"再次检查后，广播状态={broadcasting_active}")
            
            message = (
                "🛑 *开奖播报已停止* 🛑\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "您可以随时点击「开始播报」重新启动服务"
            )
            
            # 记录日志
            logger.info(f"用户 {update.effective_chat.id} 通过按钮停止了开奖播报")
        else:
            message = "❌ 播报停止失败，请稍后重试"
            logger.error(f"用户 {update.effective_chat.id} 尝试停止播报失败")
    
    # 创建返回主菜单的按钮
    back_to_start = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 返回主菜单", callback_data="back_to_start")]
    ])
    
    await edit_message_with_retry(
        context,
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        text=message,
        parse_mode='Markdown',
        reply_markup=back_to_start
    )

async def handle_prediction_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理预测功能回调"""
    query = update.callback_query
    await query.answer()
    
    # 检查是否在目标群组中，如果是则不响应
    if update.effective_chat.id == VERIFICATION_CONFIG["TARGET_GROUP_ID"]:
        logger.info(f"忽略来自目标群组 {update.effective_chat.id} 的预测回调")
        return
    
    # 预测类型映射
    prediction_types = {
        'start_single_double': {
            'type': 'single_double',
            'name': '单双预测',
            'desc': '预测下一期开奖结果的单双属性'
        },
        'start_big_small': {
            'type': 'big_small',
            'name': '大小预测',
            'desc': '预测下一期开奖结果的大小属性'
        },
        'start_kill_group': {
            'type': 'kill_group',
            'name': '杀组预测',
            'desc': '预测下一期开奖结果排除的组合'
        },
        'start_double_group': {
            'type': 'double_group',
            'name': '双组预测',
            'desc': '预测下一期可能出现的两种组合'
        }
    }
    
    # 处理预测功能回调
    if query.data in prediction_types:
        pred_info = prediction_types[query.data]
        
        # 发送预测
        success = await start_prediction(update, context, pred_info['type'])
        
        if success:
            message = (
                f"✅ *{pred_info['name']}已发送* ✅\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🎯 {pred_info['desc']}\n"
                "🧠 预测算法会根据历史数据自动优化\n"
                "📈 您可以通过系统状态查看预测准确率\n\n"
                "⚠️ 预测结果仅供参考，请理性参考\n\n"
                "💡 如需新的预测，请再次点击预测按钮"
            )
        else:
            message = f"❌ {pred_info['name']}发送失败，请稍后重试"
    else:
        message = "❓ 未知的预测类型，请重新选择"
    
    # 创建返回主菜单的按钮
    back_to_start = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 返回主菜单", callback_data="back_to_start")]
    ])
    
    await edit_message_with_retry(
        context,
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        text=message,
        parse_mode='Markdown',
        reply_markup=back_to_start
    ) 