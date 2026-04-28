# holiday_api_routes.py - 节假日API路由

from flask import Blueprint, request, jsonify, current_app
import requests
from functools import wraps

holiday_api_bp = Blueprint('holiday_api', __name__)

# 缓存节假日数据
holiday_cache = {}


def cache_holidays(year, data):
    """缓存节假日数据"""
    holiday_cache[year] = {
        'data': data,
        'timestamp': int(__import__('time').time())
    }


def get_cached_holidays(year):
    """获取缓存的节假日数据"""
    cached = holiday_cache.get(year)
    if cached:
        return cached['data']
    return None


@holiday_api_bp.route('/proxy/holidays', methods=['GET'])
def proxy_holidays():
    """
    节假日API代理
    用于解决浏览器的CORS跨域问题
    """
    try:
        year = request.args.get('year', __import__('datetime').datetime.now().year)
        api_url = request.args.get('api_url', '')

        if not api_url:
            return jsonify({
                'code': 400,
                'message': '请提供API地址'
            }), 400

        # 检查缓存
        cached_data = get_cached_holidays(year)
        if cached_data:
            current_app.logger.info(f'从缓存返回 {year} 年节假日数据')
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': cached_data,
                'from_cache': True
            })

        # 替换API地址中的年份变量
        request_url = api_url.replace('{year}', str(year))

        # 发起请求
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        current_app.logger.info(f'请求节假日API: {request_url}')

        response = requests.get(request_url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()

            # 缓存数据
            if isinstance(data, dict) and 'data' in data:
                cache_holidays(year, data['data'])

            return jsonify({
                'code': 200,
                'message': 'success',
                'data': data,
                'from_cache': False
            })
        else:
            return jsonify({
                'code': response.status_code,
                'message': f'API请求失败，状态码: {response.status_code}'
            }), response.status_code

    except requests.Timeout:
        current_app.logger.error('节假日API请求超时')
        return jsonify({
            'code': 408,
            'message': 'API请求超时，请检查网络连接或API地址是否正确'
        }), 408

    except requests.RequestException as e:
        current_app.logger.error(f'节假日API请求异常: {str(e)}')
        return jsonify({
            'code': 500,
            'message': f'API请求失败: {str(e)}'
        }), 500

    except Exception as e:
        current_app.logger.error(f'节假日API路由异常: {str(e)}', exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'服务器错误: {str(e)}'
        }), 500


@holiday_api_bp.route('/test-connection', methods=['POST'])
def test_connection():
    """测试API连接"""
    try:
        data = request.get_json()
        api_url = data.get('api_url', '')

        if not api_url:
            return jsonify({
                'code': 400,
                'message': '请提供API地址'
            }), 400

        # 替换年份变量
        year = __import__('datetime').datetime.now().year
        request_url = api_url.replace('{year}', str(year))

        # 发起测试请求
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(request_url, headers=headers, timeout=10)

        if response.status_code == 200:
            return jsonify({
                'code': 200,
                'message': '连接测试成功',
                'data': response.json()
            })
        else:
            return jsonify({
                'code': response.status_code,
                'message': f'连接测试失败，状态码: {response.status_code}'
            }), response.status_code

    except requests.Timeout:
        return jsonify({
            'code': 408,
            'message': '连接超时，请检查API地址是否正确'
        }), 408

    except requests.RequestException as e:
        return jsonify({
            'code': 500,
            'message': f'连接失败: {str(e)}'
        }), 500

    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'服务器错误: {str(e)}'
        }), 500


@holiday_api_bp.route('/cache/clear', methods=['POST'])
def clear_cache():
    """清除节假日缓存"""
    try:
        holiday_cache.clear()
        current_app.logger.info('节假日缓存已清除')
        return jsonify({
            'code': 200,
            'message': '缓存已清除'
        })
    except Exception as e:
        current_app.logger.error(f'清除缓存失败: {str(e)}')
        return jsonify({
            'code': 500,
            'message': f'清除缓存失败: {str(e)}'
        }), 500
