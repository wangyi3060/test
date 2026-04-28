"""
定时任务调度器
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import current_app
import logging

logger = logging.getLogger(__name__)

class SchedulerManager:
    """定时任务管理器"""
    
    def __init__(self, app=None):
        self.scheduler = None
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """初始化调度器"""
        self.scheduler = BackgroundScheduler()
        
        # 注册任务
        self._register_tasks(app)
        
        # 启动调度器
        self.scheduler.start()
        logger.info('=' * 50)
        logger.info('定时任务调度器已启动')
        logger.info('=' * 50)
        
        # 列出所有任务
        jobs = self.scheduler.get_jobs()
        logger.info(f'已注册 {len(jobs)} 个定时任务:')
        for job in jobs:
            logger.info(f"  - {job.name} ({job.id}): {job.next_run_time}")
    
    def _register_tasks(self, app):
        """注册所有定时任务"""
        
        # 每周五17:00发送周报
        self.scheduler.add_job(
            func=self.send_weekly_report,
            trigger=CronTrigger(day_of_week='fri', hour=17, minute=0),
            id='weekly_report',
            name='发送周报',
            replace_existing=True
        )
        logger.info('已注册任务: 发送周报 (每周五 17:00)')
        
        # 每天凌晨3点备份数据库
        self.scheduler.add_job(
            func=self.backup_database,
            trigger=CronTrigger(hour=3, minute=0),
            id='database_backup',
            name='数据库备份',
            replace_existing=True
        )
        logger.info('已注册任务: 数据库备份 (每天 03:00)')
        
        # 每小时清理过期令牌
        self.scheduler.add_job(
            func=self.clean_expired_tokens,
            trigger=CronTrigger(minute=0),
            id='clean_tokens',
            name='清理过期令牌',
            replace_existing=True
        )
        logger.info('已注册任务: 清理过期令牌 (每小时)')
        
        # 每天凌晨2点清理旧日志
        self.scheduler.add_job(
            func=self.clean_logs,
            trigger=CronTrigger(hour=2, minute=0),
            id='clean_logs',
            name='清理旧日志',
            replace_existing=True
        )
        logger.info('已注册任务: 清理旧日志 (每天 02:00)')
        
        # 每周日凌晨4点检查系统健康
        self.scheduler.add_job(
            func=self.check_system_health,
            trigger=CronTrigger(day_of_week='sun', hour=4, minute=0),
            id='health_check',
            name='系统健康检查',
            replace_existing=True
        )
        logger.info('已注册任务: 系统健康检查 (每周日 04:00)')
    
    def send_weekly_report(self):
        """发送周报邮件"""
        logger.info('=' * 50)
        logger.info('开始执行: 发送周报')
        logger.info('=' * 50)
        
        try:
            from app import get_session_factory
            from app.utils.email_helper import EmailHelper
            
            SessionFactory = get_session_factory()
            session = SessionFactory()
            
            # 获取本周工作记录
            sql = """
                SELECT * FROM work_records 
                WHERE YEARWEEK(work_date, 1) = YEARWEEK(CURDATE(), 1)
                ORDER BY work_date DESC
            """
            records = session.execute(sql).fetchall()
            
            logger.info(f"获取到 {len(records)} 条工作记录")
            
            # 生成HTML周报
            html_content = self._generate_weekly_report_html(records)
            
            # 获取收件人列表
            recipients = self._get_report_recipients(session)
            
            session.close()
            
            # 发送邮件
            email_helper = EmailHelper()
            email_helper.send_weekly_report(recipients, html_content)
            
            from app.utils.logger import log_system_event
            log_system_event('SEND_WEEKLY_REPORT', f'发送周报给 {len(recipients)} 人')
            
            logger.info(f'周报发送成功: {len(recipients)} 人')
            
        except Exception as e:
            logger.error(f'发送周报失败: {str(e)}', exc_info=True)
            from app.utils.logger import log_system_event
            log_system_event('SEND_WEEKLY_REPORT_FAILED', str(e))
        
        logger.info('=' * 50)
        logger.info('发送周报任务完成')
        logger.info('=' * 50)
    
    def _generate_weekly_report_html(self, records):
        """生成周报HTML"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset='UTF-8'>
            <style>
                body { font-family: Arial, sans-serif; }
                table { border-collapse: collapse; width: 100%; margin-top: 20px; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #4CAF50; color: white; }
                tr:nth-child(even) { background-color: #f2f2f2; }
                .header { background-color: #4CAF50; color: white; padding: 20px; text-align: center; }
                .summary { background-color: #f9f9f9; padding: 15px; margin: 20px 0; }
            </style>
        </head>
        <body>
            <div class='header'>
                <h1>IT运维工作周报</h1>
                <p>统计周期: 本周</p>
            </div>
            
            <div class='summary'>
                <h2>工作概览</h2>
                <p>总工单数: {}</p>
                <p>已完成: {}</p>
                <p>进行中: {}</p>
            </div>
            
            <h2>工作明细</h2>
            <table>
                <tr>
                    <th>编号</th>
                    <th>日期</th>
                    <th>内容</th>
                    <th>负责人</th>
                    <th>状态</th>
                    <th>科室</th>
                </tr>
        """.format(
            len(records),
            sum(1 for r in records if r[5] == 2),
            sum(1 for r in records if r[5] == 1)
        )
        
        for record in records:
            status = '已完成' if record[5] == 2 else '进行中'
            html += f"""
                <tr>
                    <td>{record[1]}</td>
                    <td>{record[2]}</td>
                    <td>{record[3]}</td>
                    <td>{record[4]}</td>
                    <td>{status}</td>
                    <td>{record[8]}</td>
                </tr>
            """
        
        html += """
            </table>
        </body>
        </html>
        """
        
        return html
    
    def _get_report_recipients(self, session):
        """获取报告收件人列表"""
        # 从配置表获取
        sql = "SELECT config_value FROM system_config WHERE config_key = 'report_recipients'"
        result = session.execute(sql).fetchone()
        
        if result:
            recipients = result[0].split(',')
            return [r.strip() for r in recipients if r.strip()]
        
        # 默认收件人
        return ['admin@company.com']
    
    def backup_database(self):
        """备份数据库"""
        logger.info('=' * 50)
        logger.info('开始执行: 数据库备份')
        logger.info('=' * 50)

        try:
            import os
            import subprocess
            from datetime import datetime
            from app.utils.logger import log_system_event
            from app import create_app

            # 创建应用上下文
            app = create_app()
            with app.app_context():
                # 从配置获取数据库信息
                db_config = current_app.config.get('DB_CONFIG', {})

                # 生成备份文件名
                backup_date = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_file = f"backup/it_ops_db_{backup_date}.sql"

                # 确保备份目录存在
                os.makedirs('backup', exist_ok=True)

                # 执行备份命令（包含完整的数据库结构）
                cmd = (
                    f'mysqldump -h {db_config["host"]} -P {db_config.get("port", 3306)} '
                    f'-u {db_config["user"]} -p{db_config["password"]} '
                    f'--default-character-set={db_config.get("charset", "utf8mb4")} '
                    f'--single-transaction --routines --triggers --events '
                    f'--databases {db_config["database"]} > {backup_file}'
                )

                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

                if result.returncode == 0:
                    log_system_event('DATABASE_BACKUP', f'数据库备份成功: {backup_file}')
                    logger.info(f'数据库备份成功: {backup_file}')

                    # 自动清理过期备份
                    try:
                        import glob as _glob
                        from datetime import timedelta as _td
                        from sqlalchemy import text
                        from app import get_session_factory
                        SessionFactory = get_session_factory()
                        session = SessionFactory()
                        result = session.execute(text("SELECT config_value FROM system_config WHERE config_key = 'backup_retention_days'")).fetchone()
                        session.close()
                        retention = int(result[0]) if result else 30
                        cutoff = datetime.now() - _td(days=retention)
                        pattern = os.path.join('backup', 'it_ops_db_*.sql')
                        deleted = 0
                        for fp in _glob.glob(pattern):
                            if datetime.fromtimestamp(os.stat(fp).st_mtime) < cutoff:
                                os.remove(fp)
                                deleted += 1
                        if deleted:
                            log_system_event('AUTO_CLEANUP_BACKUP', f'自动清理 {deleted} 个过期备份（保留{retention}天）')
                            logger.info(f'自动清理 {deleted} 个超过 {retention} 天的备份')
                    except Exception as e:
                        logger.warning(f'自动清理备份失败: {str(e)}')
                else:
                    log_system_event('DATABASE_BACKUP_FAILED', f'数据库备份失败: {result.stderr}')
                    logger.error(f'数据库备份失败: {result.stderr}')

        except Exception as e:
            logger.error(f'数据库备份异常: {str(e)}', exc_info=True)
            from app.utils.logger import log_system_event
            log_system_event('DATABASE_BACKUP_FAILED', str(e))

        logger.info('=' * 50)
        logger.info('数据库备份任务完成')
        logger.info('=' * 50)
    
    def clean_expired_tokens(self):
        """清理过期令牌（占位符）"""
        logger.debug('执行: 清理过期令牌')
        pass
    
    def clean_logs(self):
        """清理旧日志"""
        logger.info('=' * 50)
        logger.info('开始执行: 清理旧日志')
        logger.info('=' * 50)
        
        try:
            from app.tasks.log_cleaner import LogCleaner
            
            cleaner = LogCleaner()
            cleaner.run()
            
        except Exception as e:
            logger.error(f'清理日志失败: {str(e)}', exc_info=True)
            from app.utils.logger import log_system_event
            log_system_event('LOG_CLEANUP_FAILED', str(e))
        
        logger.info('=' * 50)
        logger.info('清理旧日志任务完成')
        logger.info('=' * 50)
    
    def check_system_health(self):
        """系统健康检查"""
        logger.info('=' * 50)
        logger.info('开始执行: 系统健康检查')
        logger.info('=' * 50)
        
        try:
            import os
            import psutil
            
            report = {
                'timestamp': datetime.now().isoformat(),
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_usage': {}
            }
            
            # 检查磁盘使用
            for path in ['/', 'logs', 'backup']:
                if os.path.exists(path):
                    usage = psutil.disk_usage(path)
                    report['disk_usage'][path] = {
                        'total': usage.total,
                        'used': usage.used,
                        'percent': usage.percent
                    }
            
            logger.info(f"系统健康报告:")
            logger.info(f"  CPU使用率: {report['cpu_percent']}%")
            logger.info(f"  内存使用率: {report['memory_percent']}%")
            for path, usage in report['disk_usage'].items():
                logger.info(f"  {path} 磁盘使用: {usage['percent']}%")
            
            # 记录到系统日志
            from app.utils.logger import log_system_event
            log_system_event('HEALTH_CHECK', f'CPU: {report["cpu_percent"]}%, 内存: {report["memory_percent"]}%')
            
        except Exception as e:
            logger.error(f'系统健康检查失败: {str(e)}', exc_info=True)
            from app.utils.logger import log_system_event
            log_system_event('HEALTH_CHECK_FAILED', str(e))
        
        logger.info('=' * 50)
        logger.info('系统健康检查任务完成')
        logger.info('=' * 50)

# 创建全局调度器实例
scheduler_manager = SchedulerManager()
