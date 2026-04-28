"""
IT 运维与资产库存综合管理平台
主应用初始化文件
"""

from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import sys
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler, WatchedFileHandler
from urllib.parse import quote_plus
import time
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from functools import wraps
from datetime import datetime, timedelta
import socket

# 加载环境变量（兼容 env.cfg 和 .env）
# 先尝试当前目录，再尝试exe所在目录
def _find_env_file():
    """查找配置文件"""
    candidates = ['env.cfg', '.env']
    # 1. 当前工作目录
    for f in candidates:
        if os.path.exists(f):
            return f
    # 2. PyInstaller打包后exe所在目录
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        for f in candidates:
            p = os.path.join(exe_dir, f)
            if os.path.exists(p):
                return p
    return None

_env_file = _find_env_file()
if _env_file:
    load_dotenv(_env_file)
    from app.secure_config import decrypt_env_value
    decrypt_env_value(_env_file)

# 内存缓存系统（不依赖Redis）
class MemoryCache:
    def __init__(self):
        self._cache = {}

    def get(self, key):
        item = self._cache.get(key)
        if item:
            if datetime.now() < item['expires']:
                return item['data']
            else:
                del self._cache[key]
        return None

    def set(self, key, data, ttl=300):
        self._cache[key] = {
            'data': data,
            'expires': datetime.now() + timedelta(seconds=ttl)
        }

    def delete(self, key):
        if key in self._cache:
            del self._cache[key]

    def delete_prefix(self, prefix):
        """删除所有以指定前缀开头的缓存键"""
        keys_to_delete = [k for k in self._cache.keys() if k.startswith(prefix)]
        for key in keys_to_delete:
            del self._cache[key]

    def clear(self):
        self._cache.clear()

# 全局缓存实例
cache = MemoryCache()

# 缓存装饰器
def cached(ttl=300, key_prefix=''):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{key_prefix}:{request.path}:{str(request.args)}"

            # 尝试从缓存读取
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                return cached_data

            # 执行原始函数
            result = f(*args, **kwargs)

            # 缓存结果
            if isinstance(result, tuple):
                cache.set(cache_key, result[0], ttl)
            else:
                cache.set(cache_key, result, ttl)

            return result
        return decorated_function
    return decorator

def setup_logging(app):
    """配置日志系统"""
    # 创建logs目录
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 配置日志格式（使用中文日期）
    class ChineseFormatter(logging.Formatter):
        def formatTime(self, record, datefmt=None):
            import time
            ct = self.converter(record.created)
            if datefmt:
                s = time.strftime(datefmt, ct)
            else:
                t = time.strftime('%Y年%m月%d日 %H:%M:%S', ct)
                s = f"{t},{int(record.created % 1 * 1000):03d}"
            return s

    formatter = ChineseFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    
    # 进程安全的文件处理器（避免多进程锁定冲突）
    # 使用进程ID后缀实现进程分离
    pid = os.getpid()
    log_file = os.path.join(log_dir, f'app_{pid}.log')
    error_log_file = os.path.join(log_dir, f'error_{pid}.log')

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=100 * 1024 * 1024,  # 100MB
        backupCount=5,
        encoding='utf-8',
        delay=False
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=100 * 1024 * 1024,  # 100MB
        backupCount=5,
        encoding='utf-8',
        delay=False
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # 配置Flask日志（添加进程ID标识）
    app.logger.handlers.clear()  # 清除现有handlers避免重复
    app.logger.addHandler(file_handler)
    app.logger.addHandler(error_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.INFO)

    # 配置第三方库日志
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)  # 降低werkzeug日志级别

    # 记录启动信息
    app.logger.info(f"日志系统已启动 - 进程ID: {pid} - 主机: {socket.gethostname()}")

    return app.logger

def get_base_dir():
    """获取项目根目录，兼容PyInstaller打包和普通运行"""
    if getattr(sys, 'frozen', False):
        # PyInstaller --onedir 打包后
        # exe所在目录: dist/IT-SERVER/IT-SERVER.exe
        # _internal目录: dist/IT-SERVER/_internal/
        # 打包数据(static/database)在 _internal/ 下
        # 但我们需要的是exe旁边的 static/database（构建时手动复制的）
        exe_dir = os.path.dirname(sys.executable)
        # 优先使用exe旁边的目录（用户手动复制的）
        if os.path.exists(os.path.join(exe_dir, 'static')):
            return exe_dir
        # 回退到PyInstaller的_internal目录
        internal_dir = os.path.join(exe_dir, '_internal')
        if os.path.exists(os.path.join(internal_dir, 'static')):
            return internal_dir
        return exe_dir
    else:
        # 普通运行，app/__init__.py的上级
        return os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


def create_app():
    """创建Flask应用实例"""
    # 获取项目根目录
    basedir = get_base_dir()
    
    # 明确指定静态文件文件夹
    static_folder = os.path.join(basedir, 'static')
    
    app = Flask(__name__, static_folder=static_folder, static_url_path='/static')

    # 配置日志
    logger = setup_logging(app)
    logger.info("=" * 50)
    logger.info("应用启动中...")
    logger.info("=" * 50)
    logger.info(f"静态文件目录: {static_folder}")
    
    # 配置CORS
    CORS(app)
    
    # 加载配置
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 3600))
    app.config['JWT_TOKEN_LOCATION'] = ['headers']  # JWT token位置：headers/cookies
    app.config['JWT_HEADER_NAME'] = 'Authorization'  # JWT header名称
    app.config['JWT_HEADER_TYPE'] = 'Bearer'  # JWT token类型

    # 初始化JWT Manager
    jwt = JWTManager(app)

    # 数据库配置
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 3306)),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('DB_NAME', 'it_ops_db'),
        'charset': os.getenv('DB_CHARSET', 'utf8mb4')
    }
    
    app.config['DB_CONFIG'] = db_config
    logger.info(f"数据库配置: {db_config['host']}:{db_config['port']}/{db_config['database']}")
    
    # LDAP配置：优先从数据库system_config读取，环境变量作为兜底
    ldap_config = {
        'server': os.getenv('LDAP_SERVER', ''),
        'base_dn': os.getenv('LDAP_BASE_DN', ''),
        'bind_user': os.getenv('LDAP_BIND_USER', ''),
        'bind_password': os.getenv('LDAP_BIND_PASSWORD', ''),
        'user_search': os.getenv('LDAP_USER_SEARCH', ''),
        'group_search': os.getenv('LDAP_GROUP_SEARCH', '')
    }
    # 尝试从数据库加载LDAP配置（覆盖环境变量默认值）
    # 使用超时保护，避免数据库不可用时卡死启动
    try:
        _db_cfg = db_config
        import pymysql
        _conn = pymysql.connect(
            host=_db_cfg['host'], port=_db_cfg['port'],
            user=_db_cfg['user'], password=_db_cfg['password'],
            database=_db_cfg['database'], charset=_db_cfg['charset'],
            connect_timeout=5, read_timeout=5, write_timeout=5
        )
        _cursor = _conn.cursor(pymysql.cursors.DictCursor)
        _cursor.execute("SELECT config_key, config_value FROM system_config WHERE config_key LIKE 'ldap_%'")
        for row in _cursor.fetchall():
            key = row['config_key']  # ldap_server, ldap_base_dn, ...
            value = row['config_value'] or ''
            # ldap_server -> server, ldap_base_dn -> base_dn, ...
            field = key.replace('ldap_', '', 1)
            if field in ldap_config:
                ldap_config[field] = value
        _cursor.close()
        _conn.close()
        logger.info("从数据库加载LDAP配置完成")
    except Exception as e:
        logger.warning(f"从数据库加载LDAP配置失败，使用环境变量: {e}")

    app.config['LDAP_CONFIG'] = ldap_config
    if ldap_config['server']:
        logger.info(f"LDAP服务器: {ldap_config['server']}")
    else:
        logger.info("LDAP未配置，将使用Everyone角色")
    
    # SMTP配置
    smtp_config = {
        'host': os.getenv('SMTP_HOST', ''),
        'port': int(os.getenv('SMTP_PORT', 587)),
        'user': os.getenv('SMTP_USER', ''),
        'password': os.getenv('SMTP_PASSWORD', ''),
        'from_addr': os.getenv('SMTP_FROM', ''),
        'from_name': os.getenv('SMTP_FROM_NAME', ''),
        'use_tls': os.getenv('SMTP_USE_TLS', '1') == '1'
    }
    app.config['SMTP_CONFIG'] = smtp_config
    if smtp_config['host']:
        logger.info(f"SMTP服务器: {smtp_config['host']}")

    # 腾讯云短信配置
    sms_config = {
        'secret_id': os.getenv('SMS_SECRET_ID', ''),
        'secret_key': os.getenv('SMS_SECRET_KEY', ''),
        'sdk_app_id': os.getenv('SMS_SDK_APP_ID', ''),
        'template_id': os.getenv('SMS_TEMPLATE_ID', ''),
        'sign_name': os.getenv('SMS_SIGN_NAME', ''),
        'region': os.getenv('SMS_REGION', 'ap-guangzhou')
    }
    app.config['SMS_CONFIG'] = sms_config
    if sms_config['secret_id'] and sms_config['sdk_app_id']:
        logger.info(f"腾讯云短信已配置: SDK App ID = {sms_config['sdk_app_id']}")

    # 企业微信配置
    work_wechat_config = {
        'corp_id': os.getenv('WORK_WECHAT_CORP_ID', ''),
        'agent_id': os.getenv('WORK_WECHAT_AGENT_ID', ''),
        'app_secret': os.getenv('WORK_WECHAT_APP_SECRET', ''),
        'notify_inspection': os.getenv('WORK_WECHAT_NOTIFY_INSPECTION', ''),
        'notify_approval': os.getenv('WORK_WECHAT_NOTIFY_APPROVAL', ''),
        'notify_repair': os.getenv('WORK_WECHAT_NOTIFY_REPAIR', '')
    }
    app.config['WORK_WECHAT_CONFIG'] = work_wechat_config
    if work_wechat_config['corp_id'] and work_wechat_config['agent_id']:
        logger.info(f"企业微信应用已配置: Agent ID = {work_wechat_config['agent_id']}")

    # IP白名单
    allow_ips = os.getenv('ALLOW_IPS', '127.0.0.1')
    app.config['ALLOW_IPS'] = [ip.strip() for ip in allow_ips.split(',')]
    logger.info(f"IP白名单: {app.config['ALLOW_IPS']}")
    
    # 注册蓝图
    try:
        from app.routes import (
            auth_bp, work_bp, repair_bp, inventory_bp,
            asset_bp, log_bp, config_bp, report_bp, user_bp, department_bp, approval_bp, ip_whitelist_bp
        )
        # 导入路由模块后才能访问 analytics_bp、schedule_bp 和 inspection_bp
        from app.routes import analytics_routes, schedule_routes, inspection_routes, holiday_routes, backup_routes, campus_routes, machine_room_routes, notification_routes, system_notification_routes, duty_record_routes
        analytics_bp = analytics_routes.analytics_bp
        backup_bp = backup_routes.backup_bp
        schedule_bp = schedule_routes.schedule_bp
        inspection_bp = inspection_routes.inspection_bp
        holiday_bp = holiday_routes.holiday_bp
        campus_bp = campus_routes.campus_bp
        machine_room_bp = machine_room_routes.machine_room_bp
        notification_bp = notification_routes.notification_bp
        system_notification_bp = system_notification_routes.system_notification_bp
        duty_record_bp = duty_record_routes.duty_record_bp
        app.register_blueprint(auth_bp, url_prefix='/api/auth')
        app.register_blueprint(work_bp, url_prefix='/api/work')
        app.register_blueprint(repair_bp, url_prefix='/api/repair')
        app.register_blueprint(inventory_bp, url_prefix='/api/inventory')
        app.register_blueprint(asset_bp, url_prefix='/api/asset')
        app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
        app.register_blueprint(log_bp, url_prefix='/api/log')
        app.register_blueprint(config_bp, url_prefix='/api/config')
        app.register_blueprint(report_bp, url_prefix='/api/report')
        app.register_blueprint(user_bp, url_prefix='/api/user')
        app.register_blueprint(department_bp, url_prefix='/api/department')
        app.register_blueprint(approval_bp, url_prefix='/api/approval')
        app.register_blueprint(schedule_bp, url_prefix='/api/schedule')
        app.register_blueprint(inspection_bp, url_prefix='/api/inspection')
        app.register_blueprint(holiday_bp)
        app.register_blueprint(backup_bp, url_prefix='/api/backup')
        app.register_blueprint(campus_bp, url_prefix='/api/campus')
        app.register_blueprint(machine_room_bp, url_prefix='/api/machine-room')
        app.register_blueprint(notification_bp, url_prefix='/api/notification')
        app.register_blueprint(system_notification_bp, url_prefix='/api/system-notification')
        app.register_blueprint(duty_record_bp, url_prefix='/api/duty-record')
        app.register_blueprint(ip_whitelist_bp, url_prefix='/api/ip-whitelist')
        logger.info("所有蓝图注册成功")
    except Exception as e:
        logger.error(f"蓝图注册失败: {str(e)}")
        raise


    # 根路由 - 直接返回前端页面（禁用缓存，确保总是获取最新版本）
    @app.route('/')
    def index():
        """返回前端登录页面"""
        logger.info(f"访问根路径: {request.remote_addr}")
        response = app.send_static_file('index.html')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    # 静态文件路由 - 添加缓存控制
    @app.route('/static/<path:filename>')
    def serve_static(filename):
        """提供静态文件 - 添加缓存控制提升加载速度"""
        # JS和CSS文件缓存7天，启用Gzip压缩
        if filename.endswith('.js') or filename.endswith('.css'):
            from flask import make_response
            import gzip
            from io import BytesIO

            response = make_response(app.send_static_file(filename))

            # 添加缓存头
            response.cache_control.max_age = 7 * 24 * 3600  # 7天
            response.cache_control.public = True
            response.headers['Vary'] = 'Accept-Encoding'

            # 检查客户端是否支持Gzip
            accept_encoding = request.headers.get('Accept-Encoding', '')
            if 'gzip' in accept_encoding:
                # 读取文件内容并压缩
                file_path = os.path.join(static_folder, filename)
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    compressed = gzip.compress(content, compresslevel=6)

                    # 替换响应内容
                    response.set_data(compressed)
                    response.headers['Content-Encoding'] = 'gzip'
                    response.headers['Content-Length'] = len(compressed)
                    # 修正Content-Type
                    if filename.endswith('.js'):
                        response.headers['Content-Type'] = 'application/javascript'
                    elif filename.endswith('.css'):
                        response.headers['Content-Type'] = 'text/css'

            return response
        else:
            logger.debug(f"访问静态文件: /static/{filename}")
            return app.send_static_file(filename)

    # Favicon路由 - 避免控制台404错误
    @app.route('/favicon.ico')
    def favicon():
        """返回空响应避免404错误"""
        return '', 204

    # 健康检查端点
    @app.route('/health')
    def health_check():
        """健康检查端点，用于负载均衡器和监控系统"""
        try:
            # 检查数据库连接
            engine = get_db_engine()
            with engine.connect() as conn:
                conn.execute('SELECT 1')

            return jsonify({
                'status': 'healthy',
                'timestamp': int(time.time()),
                'service': 'IT Operations Management System'
            }), 200
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': int(time.time())
            }), 503

    # 系统状态端点
    @app.route('/api/system/status')
    @jwt_required()
    def system_status():
        """获取系统状态，仅供管理员查看"""
        try:
            from flask import current_app
            user_id = get_jwt_identity()

            # 检查权限
            engine = get_db_engine()
            with engine.connect() as conn:
                result = conn.execute(
                    "SELECT GROUP_CONCAT(ur.role_name) as roles "
                    "FROM user_roles ur WHERE ur.user_id = %s GROUP BY ur.user_id",
                    (user_id,)
                )
                roles = result.fetchone()[0].split(',') if result.rowcount > 0 else []

            if 'Super_Admin' not in roles and 'Asset_Admins' not in roles:
                return jsonify({'error': 'Permission denied'}), 403

            return jsonify({
                'status': 'running',
                'version': '2.0.0',
                'timestamp': int(time.time()),
                'database': 'connected'
            }), 200
        except Exception as e:
            logger.error(f"System status check failed: {str(e)}")
            return jsonify({'error': str(e)}), 500


    # 注册中间件
    from app.middleware import ip_whitelist_middleware
    app.before_request(ip_whitelist_middleware)
    logger.info("中间件注册成功")

    # 全局响应处理：确保浏览器知道不再使用 Service Worker
    @app.after_request
    def set_security_headers(response):
        response.headers['Service-Worker-Allowed'] = '/'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    # 404 路由 - 直接返回空 HTML，避免浏览器因 JSON 404 而等待
    @app.errorhandler(404)
    def not_found(e):
        if '/.well-known/' in request.path:
            return '', 404
        if 'remaker-global.zingfront.com' in request.url or 'staticfile.org' in request.url:
            return '', 404
        # AJAX 请求返回 JSON
        if request.path.startswith('/api/'):
            logger.warning(f"404 Not Found: {request.path}")
            return jsonify({'error': 'Not Found', 'message': 'Resource not found'}), 404
        return '', 404

    @app.errorhandler(403)
    def forbidden(e):
        logger.warning(f"403 Forbidden: {request.path} - {request.remote_addr}")
        return jsonify({'error': 'Forbidden', 'message': 'Access denied'}), 403

    @app.errorhandler(405)
    def method_not_allowed(e):
        from flask import request
        logger.warning(f"405 Method Not Allowed: {request.path} - {request.method} - 允许的方法: {e.valid_methods}")
        # 添加更详细的日志，包含请求来源
        logger.warning(f"405详细 - User-Agent: {request.headers.get('User-Agent')}")
        return jsonify({'error': 'Method Not Allowed', 'message': f'该请求不允许 {request.method} 方法，允许的方法: {e.valid_methods}'}), 405

    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f"500 Internal Server Error: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500

    @app.errorhandler(502)
    def bad_gateway(e):
        logger.error(f"502 Bad Gateway: {str(e)}", exc_info=True)
        return jsonify({'error': 'Bad Gateway', 'message': 'Service unavailable'}), 502

    @app.errorhandler(503)
    def service_unavailable(e):
        logger.error(f"503 Service Unavailable: {str(e)}", exc_info=True)
        return jsonify({'error': 'Service Unavailable', 'message': 'Service temporarily unavailable'}), 503

    @app.errorhandler(504)
    def gateway_timeout(e):
        logger.error(f"504 Gateway Timeout: {str(e)}", exc_info=True)
        return jsonify({'error': 'Gateway Timeout', 'message': 'Request timeout'}), 504

    @app.errorhandler(Exception)
    def handle_exception(e):
        logger.error(f"未捕获的异常: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500
    
    # 数据库连接测试（异步，不阻塞启动）
    import threading
    def test_db_background():
        try:
            test_db_connection(app.config['DB_CONFIG'])
            logger.info("数据库连接测试成功")
        except Exception as e:
            logger.error(f"数据库连接测试失败: {str(e)}")
            logger.info("提示: 应用将继续运行，部分功能可能受限")
            logger.info("解决方法: 1) 启动 MySQL 服务  2) 或切换到 SQLite 模式")

    # 在后台线程中测试数据库连接
    db_test_thread = threading.Thread(target=test_db_background, daemon=True)
    db_test_thread.start()
    
    logger.info("=" * 50)
    logger.info("应用初始化完成")
    logger.info("=" * 50)

    # 启动排班提醒定时任务
    try:
        from app.utils.schedule_reminder import init_scheduler
        init_scheduler(app)
        logger.info("排班提醒定时任务已启动")
    except Exception as e:
        logger.warning(f"排班提醒定时任务启动失败: {str(e)}")

    return app

def test_db_connection(db_config):
    """测试数据库连接"""
    try:
        # URL编码密码以处理特殊字符
        encoded_password = quote_plus(db_config['password'])
        connection_string = (
            f"mysql+pymysql://{db_config['user']}:{encoded_password}@"
            f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
        )
        engine = create_engine(connection_string, pool_pre_ping=True, connect_args={'connect_timeout': 5})
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        raise e

# 数据库引擎单例（避免每次请求都创建新引擎和新连接池）
_db_engine = None

# 创建数据库引擎
def get_db_engine():
    """获取数据库引擎（单例模式，复用连接池）"""
    global _db_engine
    if _db_engine is not None:
        return _db_engine

    # 直接从环境变量读取配置，不需要创建 Flask 应用
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 3306)),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('DB_NAME', 'it_ops_db'),
        'charset': os.getenv('DB_CHARSET', 'utf8mb4')
    }

    encoded_password = quote_plus(db_config['password'])
    connection_string = (
        f"mysql+pymysql://{db_config['user']}:{encoded_password}@"
        f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
    )

    _db_engine = create_engine(
        connection_string,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=20,
        max_overflow=40,
        pool_timeout=10,
        echo=False,
        pool_use_lifo=True,
        connect_args={
            'connect_timeout': 5,
        }
    )

    # 设置每个连接使用操作系统本地时区，确保NOW()返回本地时间
    from sqlalchemy import event
    @event.listens_for(_db_engine, "connect")
    def set_session_timezone(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        try:
            import time as _time
            offset_seconds = -_time.timezone if _time.daylight == 0 else -_time.altzone
            offset_hours = offset_seconds // 3600
            offset_minutes = (offset_seconds % 3600) // 60
            tz_str = f'+{offset_hours:02d}:{offset_minutes:02d}' if offset_seconds >= 0 else f'{offset_hours:02d}:{offset_minutes:02d}'
            cursor.execute(f"SET time_zone = '{tz_str}'")
        except Exception:
            cursor.execute("SET time_zone = '+08:00'")  # 默认中国时区
        finally:
            cursor.close()

    return _db_engine

# 创建会话工厂
def get_session_factory():
    """获取数据库会话工厂"""
    engine = get_db_engine()
    return sessionmaker(bind=engine)

if __name__ == '__main__':
    app = create_app()

    # 端口优先级：显式环境变量(非默认值) > 数据库 server_port > 默认 5000
    host = os.getenv('FLASK_HOST', os.getenv('APP_HOST', '0.0.0.0'))
    _env_port = os.getenv('FLASK_PORT') or os.getenv('APP_PORT') or ''
    port = 0
    if _env_port:
        env_port_int = int(_env_port)
        if env_port_int != 5000:
            port = env_port_int
    if not port:
        try:
            from sqlalchemy import text
            SessionFactory = get_session_factory()
            session = SessionFactory()
            result = session.execute(text("SELECT config_value FROM system_config WHERE config_key='server_port'")).fetchone()
            session.close()
            if result and result[0]:
                db_port = int(result[0])
                if db_port != 5000 or not _env_port:
                    port = db_port
                    app.logger.info(f"从数据库读取端口: {port}")
        except Exception as e:
            app.logger.warning(f"从数据库读取端口失败: {e}")
    if not port:
        port = 5000

    debug = os.getenv('DEBUG', 'False').lower() == 'true'

    app.logger.info(f"启动服务: http://{host}:{port}")
    app.logger.info(f"调试模式: {debug}")

    try:
        app.run(host=host, port=port, debug=debug, threaded=True, use_reloader=False)
    except Exception as e:
        app.logger.error(f"服务启动失败: {str(e)}", exc_info=True)
        raise
