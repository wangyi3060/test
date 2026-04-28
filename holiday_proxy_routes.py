# 节假日API后端代理 - 解决前端CORS跨域问题
from flask import Blueprint, request, jsonify
import requests
from datetime import datetime
import logging
from app import app_logger

# 创建Blueprint
holiday_proxy_bp = Blueprint('holiday_proxy', __name__)

# 配置日志
logger = logging.getLogger(__name__)

# 配置请求头，模拟浏览器
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache'
}

# 缓存存储
holiday_cache = {}

def get_cache_key(year, api_url):
    """生成缓存键"""
    return f"{api_url}_{year}"

def save_to_cache(key, data):
    """保存到缓存"""
    holiday_cache[key] = {
        'data': data,
        'timestamp': datetime.now().timestamp()
    }
    app_logger.info(f"节假日数据已缓存: {key}")

def get_from_cache(key, expire_seconds=7*24*60*60):
    """从缓存获取数据"""
    if key in holiday_cache:
        cached = holiday_cache[key]
        age_seconds = datetime.now().timestamp() - cached['timestamp']
        if age_seconds < expire_seconds:
            app_logger.info(f"从缓存读取节假日数据: {key}, 缓存年龄: {age_seconds:.0f}秒")
            return cached['data']
        else:
            # 缓存过期
            del holiday_cache[key]
            app_logger.info(f"节假日缓存已过期: {key}")
    return None

@holiday_proxy_bp.route('/proxy/test-connection', methods=['POST'])
def test_connection():
    """测试API连接"""
    try:
        data = request.get_json()
        api_url = data.get('api_url', '').strip()
        year = data.get('year', datetime.now().year)
        
        if not api_url:
            return jsonify({
                'code': 400,
                'message': '请提供API地址'
            }), 400
        
        # 替换年份变量
        request_url = api_url.replace('{year}', str(year)).replace('{year}', str(year))
        
        app_logger.info(f"测试节假日API连接: {request_url}")
        
        # 发送请求
        response = requests.get(
            request_url,
            headers=HEADERS,
            timeout=10
        )
        
        if response.status_code == 200:
            try:
                result_data = response.json()
                return jsonify({
                    'code': 200,
                    'message': '连接测试成功',
                    'data': result_data
                })
            except Exception as e:
                return jsonify({
                    'code': 500,
                    'message': f'API响应解析失败: {str(e)}'
                }), 500
        else:
            return jsonify({
                'code': response.status_code,
                'message': f'连接失败，HTTP状态码: {response.status_code}'
            }), response.status_code
            
    except requests.Timeout:
        app_logger.error("节假日API连接超时")
        return jsonify({
            'code': 408,
            'message': '连接超时，请检查API地址是否正确或网络连接'
        }), 408
    except requests.RequestException as e:
        app_logger.error(f"节假日API连接失败: {str(e)}")
        return jsonify({
            'code': 500,
            'message': f'连接失败: {str(e)}'
        }), 500
    except Exception as e:
        app_logger.error(f"节假日API测试异常: {str(e)}")
        return jsonify({
            'code': 500,
            'message': f'服务器错误: {str(e)}'
        }), 500

@holiday_proxy_bp.route('/proxy/get-holidays', methods=['GET'])
def get_holidays():
    """获取节假日数据（带缓存）"""
    try:
        api_url = request.args.get('api_url', '').strip()
        year = request.args.get('year', datetime.now().year)
        
        if not api_url:
            return jsonify({
                'code': 400,
                'message': '请提供API地址'
            }), 400
        
        # 替换年份变量
        request_url = api_url.replace('{year}', str(year)).replace('{year}', str(year))
        
        # 检查缓存
        cache_key = get_cache_key(year, api_url)
        cached_data = get_from_cache(cache_key)
        
        if cached_data:
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': cached_data,
                'from_cache': True
            })
        
        # 缓存未命中，发起请求
        app_logger.info(f"从API获取节假日数据: {request_url}")
        
        response = requests.get(
            request_url,
            headers=HEADERS,
            timeout=30
        )
        
        if response.status_code == 200:
            try:
                result_data = response.json()
                
                # 保存到缓存
                save_to_cache(cache_key, result_data)
                
                return jsonify({
                    'code': 200,
                    'message': 'success',
                    'data': result_data,
                    'from_cache': False
                })
            except Exception as e:
                app_logger.error(f"解析节假日数据失败: {str(e)}")
                return jsonify({
                    'code': 500,
                    'message': f'API响应解析失败: {str(e)}'
                }), 500
        else:
            return jsonify({
                'code': response.status_code,
                'message': f'API请求失败，HTTP状态码: {response.status_code}'
            }), response.status_code
            
    except requests.Timeout:
        app_logger.error("节假日API请求超时")
        return jsonify({
            'code': 408,
            'message': '请求超时，请检查API地址是否正确或网络连接'
        }), 408
    except requests.RequestException as e:
        app_logger.error(f"节假日API请求失败: {str(e)}")
        return jsonify({
            'code': 500,
            'message': f'请求失败: {str(e)}'
        }), 500
    except Exception as e:
        app_logger.error(f"节假日API获取异常: {str(e)}")
        return jsonify({
            'code': 500,
            'message': f'服务器错误: {str(e)}'
        }), 500

@holiday_proxy_bp.route('/proxy/clear-cache', methods=['POST'])
def clear_cache():
    """清除缓存"""
    try:
        holiday_cache.clear()
        app_logger.info("节假日缓存已清除")
        return jsonify({
            'code': 200,
            'message': '缓存已清除'
        })
    except Exception as e:
        app_logger.error(f"清除缓存失败: {str(e)}")
        return jsonify({
            'code': 500,
            'message': f'清除缓存失败: {str(e)}'
        }), 500

@holiday_proxy_bp.route('/proxy/cache-info', methods=['GET'])
def cache_info():
    """获取缓存信息"""
    try:
        cache_stats = []
        for key, value in holiday_cache.items():
            age_seconds = datetime.now().timestamp() - value['timestamp']
            expire_seconds = 7 * 24 * 60 * 60
            remaining_seconds = expire_seconds - age_seconds
            cache_stats.append({
                'key': key,
                'age_seconds': age_seconds,
                'remaining_seconds': remaining_seconds if remaining_seconds > 0 else 0,
                'expired': remaining_seconds <= 0
            })
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': {
                'total_count': len(holiday_cache),
                'caches': cache_stats
            }
        })
    except Exception as e:
        app_logger.error(f"获取缓存信息失败: {str(e)}")
        return jsonify({
            'code': 500,
            'message': f'获取缓存信息失败: {str(e)}'
        }), 500
