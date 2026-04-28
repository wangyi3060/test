"""
安全中间件
实现IP白名单检查和请求日志记录
"""

from flask import request, jsonify, g, current_app
import logging
import time
from functools import wraps
import ipaddress

logger = logging.getLogger(__name__)

def ip_in_network(ip, network):
    """检查IP是否在网络范围内"""
    try:
        if '/' in network:
            # CIDR格式: 192.168.1.0/24
            net = ipaddress.ip_network(network, strict=False)
            return ipaddress.ip_address(ip) in net
        else:
            # 单个IP
            return ip == network or ip == network.strip()
    except:
        return False

def ip_whitelist_middleware():
    """IP白名单中间件"""
    # 跳过静态资源和登录接口
    skip_paths = ['/', '/static', '/favicon.ico', '/api/auth/login', '/api/config/system']

    for path in skip_paths:
        if request.path == path or request.path.startswith(path):
            logger.debug(f"跳过IP白名单检查: {request.path}")
            return None

    # 获取客户端IP
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
    # 处理 X-Forwarded-For 可能包含多个IP的情况
    if client_ip and ',' in client_ip:
        client_ip = client_ip.split(',')[0].strip()

    logger.info(f"IP白名单检查: {client_ip} - {request.path}")

    # 检查IP是否在白名单中
    allowed_ips = current_app.config.get('ALLOW_IPS', [])

    # 如果白名单为空，允许所有IP
    if not allowed_ips:
        logger.debug(f"IP白名单为空,允许所有IP访问")
        return None

    # 检查IP是否在白名单中（支持单个IP和CIDR范围）
    is_allowed = False
    for allowed in allowed_ips:
        if ip_in_network(client_ip, allowed):
            is_allowed = True
            break

    if not is_allowed:
        # 记录拦截日志
        logger.warning(f"IP拦截: {client_ip} 尝试访问 {request.path}, 白名单: {allowed_ips}")

        # 异步记录到数据库
        from app.utils.logger import log_security_event
        try:
            log_security_event('IP_BLOCK', f'IP {client_ip} 访问被拦截: {request.path}', client_ip)
        except:
            pass  # 日志记录失败不影响主流程

        return jsonify({
            'error': 'Forbidden',
            'message': '您的IP地址不在白名单中',
            'ip': client_ip,
            'allowed_ips': allowed_ips
        }), 403

    logger.debug(f"IP白名单通过: {client_ip}")
    return None

def auth_required(f):
    """认证装饰器 - 需要登录"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        from flask import request
        from app.utils.jwt_helper import verify_token

        logger.debug(f"认证检查: {request.path}")

        # 支持两种方式传递token: Authorization头 或 URL参数
        token = request.headers.get('Authorization')
        if token and token.startswith('Bearer '):
            token = token.replace('Bearer ', '')
        else:
            # 尝试从URL参数获取token（用于导出等功能）
            token = request.args.get('token')

        if not token:
            logger.warning(f"缺少认证令牌: {request.path} - {request.remote_addr}")
            return jsonify({'error': 'Unauthorized', 'message': '需要提供认证令牌'}), 401

        try:
            payload = verify_token(token)
            if not payload:
                logger.warning(f"令牌验证失败: {request.path}")
                return jsonify({'error': 'Unauthorized', 'message': '令牌无效或已过期'}), 401

            username = payload.get('username', 'unknown')

            # 单点登录检查：验证token是否与数据库中存储的login_token一致
            from app import get_session_factory
            from sqlalchemy import text
            SessionFactory = get_session_factory()
            session = SessionFactory()
            check_sql = text("SELECT login_token FROM users WHERE username = :username")
            result = session.execute(check_sql, {'username': username}).fetchone()
            session.close()

            if result and result[0]:
                stored_token = result[0]
                if stored_token != token:
                    logger.warning(f"单点登录冲突: {username} - 令牌已被其他登录顶替")
                    return jsonify({'error': 'Unauthorized', 'message': '您的账号已在其他设备登录，请重新登录'}), 401

            request.user = payload

            duration = time.time() - start_time
            logger.debug(f"认证成功: {username} - {request.path} - {duration:.3f}s")

        except Exception as e:
            logger.warning(f"认证失败: {request.path} - {str(e)}")
            return jsonify({'error': 'Unauthorized', 'message': '令牌无效或已过期'}), 401

        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    """角色权限装饰器 - 需要特定角色"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import request
            
            if not hasattr(request, 'user'):
                logger.warning(f"未认证用户尝试访问: {request.path}")
                return jsonify({'error': 'Unauthorized', 'message': '需要先登录'}), 401
            
            user_roles = request.user.get('roles', [])
            username = request.user.get('username', 'unknown')
            
            # Everyone角色可以访问所有
            if 'Everyone' in user_roles:
                logger.debug(f"Everyone角色访问: {username} - {request.path}")
                return f(*args, **kwargs)
            
            # 检查是否有权限
            if not any(role in user_roles for role in roles):
                logger.warning(f"权限不足: {username} - 角色: {user_roles} - 需要: {roles} - 访问: {request.path}")
                return jsonify({'error': 'Forbidden', 'message': '权限不足'}), 403
            
            logger.debug(f"权限检查通过: {username} - {request.path}")
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import request
        from app.utils.jwt_helper import verify_token

        # 首先进行JWT认证
        token = request.headers.get('Authorization')
        if not token or not token.startswith('Bearer '):
            logger.warning(f"缺少认证令牌: {request.path}")
            return jsonify({'error': 'Unauthorized', 'message': '需要提供认证令牌'}), 401

        try:
            token = token.replace('Bearer ', '')
            payload = verify_token(token)
            if not payload:
                logger.warning(f"令牌验证失败: {request.path}")
                return jsonify({'error': 'Unauthorized', 'message': '令牌无效或已过期'}), 401

            request.user = payload
        except Exception as e:
            logger.warning(f"认证失败: {request.path} - {str(e)}")
            return jsonify({'error': 'Unauthorized', 'message': '令牌无效或已过期'}), 401

        # 检查管理员权限（包括Super_Admin和Asset_Admins）
        user_roles = request.user.get('roles', [])
        username = request.user.get('username', 'unknown')

        if 'Super_Admin' not in user_roles and 'Asset_Admins' not in user_roles:
            logger.warning(f"非管理员尝试管理员操作: {username} - 角色: {user_roles} - {request.path}")
            return jsonify({'error': 'Forbidden', 'message': '需要管理员权限'}), 403

        logger.info(f"管理员操作: {username} - {request.path}")
        return f(*args, **kwargs)
    return decorated_function

def admin_or_self_required(f):
    """管理员或本人权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import request
        
        if not hasattr(request, 'user'):
            logger.warning(f"未认证用户尝试访问: {request.path}")
            return jsonify({'error': 'Unauthorized', 'message': '需要先登录'}), 401
        
        user_roles = request.user.get('roles', [])
        username = request.user.get('username', 'unknown')
        
        # 检查是否是管理员
        is_admin = 'Super_Admin' in user_roles or 'Asset_Admins' in user_roles
        
        # 如果不是管理员，在请求中标记为非管理员
        request.is_admin = is_admin
        request.is_self = not is_admin  # 非管理员只能操作自己的记录
        
        logger.debug(f"权限检查: {username} - 管理员={is_admin} - {request.path}")
        return f(*args, **kwargs)
    return decorated_function

def attendance_required(f):
    """考勤员权限装饰器 - 管理员和考勤员可访问"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import request
        from app.utils.jwt_helper import verify_token

        # 首先进行JWT认证
        token = request.headers.get('Authorization')
        if not token or not token.startswith('Bearer '):
            logger.warning(f"缺少认证令牌: {request.path}")
            return jsonify({'error': 'Unauthorized', 'message': '需要提供认证令牌'}), 401

        try:
            token = token.replace('Bearer ', '')
            payload = verify_token(token)
            if not payload:
                logger.warning(f"令牌验证失败: {request.path}")
                return jsonify({'error': 'Unauthorized', 'message': '令牌无效或已过期'}), 401

            request.user = payload
        except Exception as e:
            logger.warning(f"认证失败: {request.path} - {str(e)}")
            return jsonify({'error': 'Unauthorized', 'message': '令牌无效或已过期'}), 401

        # 检查考勤员权限（Super_Admin、Asset_Admins、Attendance_Officer）
        user_roles = request.user.get('roles', [])
        username = request.user.get('username', 'unknown')

        allowed_roles = ['Super_Admin', 'Asset_Admins', 'Attendance_Officer']
        if not any(role in user_roles for role in allowed_roles):
            logger.warning(f"非考勤员尝试考勤操作: {username} - 角色: {user_roles} - {request.path}")
            return jsonify({'error': 'Forbidden', 'message': '需要考勤员权限'}), 403

        logger.info(f"考勤操作: {username} - {request.path}")
        return f(*args, **kwargs)
    return decorated_function

def log_request_response(f):
    """请求响应日志装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        
        # 获取用户信息
        username = getattr(request, 'user', {}).get('username', 'anonymous')
        
        # 记录请求开始
        logger.info(f"请求开始: {request.method} {request.path} - 用户: {username}")
        
        try:
            # 执行原函数
            response = f(*args, **kwargs)
            
            # 计算执行时间
            duration = time.time() - start_time
            
            # 获取状态码
            if isinstance(response, tuple) and len(response) > 1:
                status_code = response[1]
                data = response[0]
            else:
                status_code = 200
                data = response
            
            # 记录API请求
            from app.utils.logger import log_api_request
            try:
                params = request.args.to_dict() if request.method == 'GET' else request.get_json(silent=True) or {}
                log_api_request(
                    endpoint=request.path,
                    method=request.method,
                    user=username,
                    params=params,
                    response_status=status_code
                )
            except:
                pass  # 日志记录失败不影响主流程
            
            # 性能警告（超过5秒）
            if duration > 5.0:
                from app.utils.logger import log_performance_warning
                log_performance_warning(request.path, duration, 5.0)
            
            # 记录请求完成
            logger.info(f"请求完成: {request.method} {request.path} - 状态: {status_code} - 耗时: {duration:.3f}s")
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"请求异常: {request.method} {request.path} - 用户: {username} - 错误: {str(e)}", exc_info=True)
            raise
    
    return decorated_function
