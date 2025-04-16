import asyncio
import os
import sys
import warnings

# 关闭Python-telegram-bot的警告
warnings.filterwarnings("ignore", category=UserWarning, module="telegram")

from telegram import Update, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler, ApplicationBuilder
from loguru import logger

from features.config.config_manager import BOT_TOKEN, log_config, VERIFICATION_CONFIG
from features.data.db_manager import db_manager
from features.utils.message_handler import handle_message
from features.ui.commands import (
    start, help_command, status_command, handle_help_callback,
    handle_broadcast_callback, handle_prediction_callback
)
from features.utils.error_handler import error_handler
from features.services.lottery_update import check_lottery_update, initialize_lottery_data
from features.data.cache_manager import cleanup_cache, CACHE_CONFIG
from features.services.prediction import verify_prediction
from features.services.verification.verification_service import (
    handle_verification_callback, clear_verification_cache, process_group_message,
    process_chat_member_updated, periodic_verification_check
)

async def post_init_setup(application: Application):
    """在机器人启动后设置命令菜单"""
    logger.info("设置命令菜单只在私聊中可见...")
    try:
        commands = [
            ("start", "开始使用机器人"),
            ("help", "显示帮助信息"),
            ("status", "显示机器人状态")
        ]
        # 设置私聊命令
        await application.bot.set_my_commands(
            commands,
            scope=BotCommandScopeAllPrivateChats()
        )
        # 清除群组命令
        await application.bot.delete_my_commands(
            scope=BotCommandScopeAllGroupChats()
        )
        logger.info("命令菜单设置成功")
    except Exception as e:
        logger.error(f"设置命令菜单失败: {e}")

def main():
    """启动机器人"""
    try:
        logger.info("正在启动机器人...")
        
        # 检查环境
        import platform, os
        logger.info(f"操作系统: {platform.system()} {platform.release()}")
        logger.info(f"Python版本: {platform.python_version()}")
        logger.info(f"当前工作目录: {os.getcwd()}")
        
        # 检查是否是宝塔环境
        is_bt = os.path.exists('/www/server/panel/class')
        logger.info(f"宝塔环境: {'是' if is_bt else '否'}")
        
        # 记录配置信息
        log_config()
        
        # 确保数据库目录存在
        logger.info("检查数据库连接...")
        if db_manager.connect():
            logger.info("数据库连接成功")
        else:
            logger.error("数据库连接失败，请检查配置和权限")
            # 如果数据库连接失败，可能需要退出或采取其他措施
            # sys.exit(1)
        
        # 初始化预测器
        from features.prediction import predictor
        logger.info("初始化预测器...")
        logger.info(f"当前算法配置: {predictor.current_algorithms}")
        
        # 初始化机器人数据
        logger.info("初始化机器人数据...")
        if initialize_lottery_data():
            logger.info("机器人数据初始化成功")
        else:
            logger.warning("机器人数据初始化失败，请检查网络连接和API设置")
        
        # 创建应用 - 使用ApplicationBuilder并注册post_init
        builder = Application.builder().token(BOT_TOKEN)\
            .connect_timeout(30)\
            .pool_timeout(30)\
            .read_timeout(30)\
            .write_timeout(30)\
            .get_updates_connect_timeout(30)\
            .get_updates_pool_timeout(30)\
            .get_updates_read_timeout(30)\
            .post_init(post_init_setup) # 注册post_init函数
        
        application = builder.build()
        
        logger.info("机器人已配置，超时设置为30秒")
        
        # 添加处理程序
        application.add_handler(CommandHandler("start", start, ~filters.Chat(chat_id=VERIFICATION_CONFIG["TARGET_GROUP_ID"])))
        application.add_handler(CommandHandler("help", help_command, ~filters.Chat(chat_id=VERIFICATION_CONFIG["TARGET_GROUP_ID"])))
        application.add_handler(CommandHandler("status", status_command, ~filters.Chat(chat_id=VERIFICATION_CONFIG["TARGET_GROUP_ID"])))
        
        # 添加回调查询处理程序 - 使用过滤器确保不在目标群组中响应
        # 创建通用的非目标群过滤器
        not_target_group_filter = ~filters.Chat(chat_id=VERIFICATION_CONFIG["TARGET_GROUP_ID"])
        
        application.add_handler(CallbackQueryHandler(
            handle_verification_callback, 
            pattern='^verify_membership$'
        ))
        
        application.add_handler(CallbackQueryHandler(
            handle_broadcast_callback, 
            pattern='^(start_broadcast|stop_broadcast)$'
        ))
        
        application.add_handler(CallbackQueryHandler(
            handle_prediction_callback, 
            pattern='^(start_single_double|stop_single_double|start_big_small|stop_big_small|start_kill_group|stop_kill_group|start_double_group|stop_double_group)$'
        ))
        
        # 处理其他所有回调
        application.add_handler(CallbackQueryHandler(
            handle_help_callback
        ))
        
        # 添加文本消息处理
        application.add_handler(MessageHandler(
            # 过滤条件：文本消息 且 非命令 且 不是来自目标群组(@id520)的消息
            filters.TEXT & ~filters.COMMAND & ~filters.Chat(chat_id=VERIFICATION_CONFIG["TARGET_GROUP_ID"]), 
            handle_message
        ))
        
        # 添加群组消息处理器（用于更新用户状态，但不响应任何命令）
        application.add_handler(MessageHandler(
            # 仅处理来自目标群组的消息，用于更新用户状态
            filters.Chat(chat_id=VERIFICATION_CONFIG["TARGET_GROUP_ID"]) & ~filters.COMMAND,
            process_group_message
        ))
        
        # 添加群组成员更新处理器（监听用户加入和离开群组）
        from telegram.ext import ChatMemberHandler
        application.add_handler(ChatMemberHandler(
            callback=process_chat_member_updated
        ))
        
        # 添加定时任务
        job_queue = application.job_queue
        logger.info(f"获取到job_queue: {job_queue}")
        
        # 添加定时任务 - 开奖数据更新
        check_interval = 1  # 固定为1秒
        logger.info(f"设置开奖检查间隔为 {check_interval} 秒")
        job_queue.run_repeating(check_lottery_update, interval=check_interval, first=0)
        
        # 添加定时任务 - 预测验证
        async def async_verify_prediction(context):
            """异步包装verify_prediction函数"""
            from features.services.prediction import verify_prediction
            verify_prediction(context)  # 不需要await，这是一个同步函数
        
        job_queue.run_repeating(async_verify_prediction, interval=600, first=10)  # 10分钟检查一次预测
        
        # 添加定时任务 - 缓存清理
        cleanup_interval = CACHE_CONFIG["CLEANUP_INTERVAL"]
        job_queue.run_repeating(cleanup_cache, interval=cleanup_interval, first=cleanup_interval)
        
        # 添加定时任务 - 周期性验证检查（每小时检查一次）
        verification_check_interval = VERIFICATION_CONFIG["CHECK_INTERVAL"]  # 默认60秒 * 60 = 1小时
        job_queue.run_repeating(
            periodic_verification_check,
            interval=verification_check_interval, 
            first=verification_check_interval
        )
        logger.info(f"周期性验证检查任务已设置，间隔为 {verification_check_interval} 秒")
        
        # 添加错误处理器
        application.add_error_handler(error_handler)
        
        # 启动机器人，使用优化的轮询设置
        application.run_polling(
            # 只接收消息、回调和内联查询更新，丢弃其他类型以减少处理负担
            allowed_updates=['message', 'callback_query', 'inline_query', 'my_chat_member', 'chat_member'],
            # 丢弃所有待处理的更新，只处理新的命令
            drop_pending_updates=True,
            # 设置轮询超时，避免长时间挂起
            timeout=30,
            # 设置轮询间隔，减少API请求频率
            poll_interval=0.5,
            # 设置关闭超时，确保在关闭时能够正确清理资源
            close_loop=False
        )
    except Exception as e:
        logger.error(f"启动机器人失败: {e}")
        # 打印完整错误堆栈跟踪
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")

if __name__ == "__main__":
    main() 