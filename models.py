"""
数据库模型定义
"""

from sqlalchemy import Column, Integer, String, Text, Date, DateTime, TIMESTAMP, ForeignKey, BigInteger, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class WorkRecord(Base):
    """工作记录表"""
    __tablename__ = 'work_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    serial_no = Column(String(20), unique=True, nullable=False, comment='编号 YYYYMMDDNNN')
    work_date = Column(Date, nullable=False, comment='工作日期')
    content = Column(Text, nullable=False, comment='描述内容')
    operator = Column(String(50), comment='负责人')
    status = Column(Integer, default=1, comment='状态 1:进行中 2:已完成')
    contact_person = Column(String(50), comment='联系人')
    service_type = Column(String(50), comment='服务类型')
    dept_name = Column(String(100), comment='所属科室')
    remark = Column(Text, comment='备注')
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())

class RepairRecord(Base):
    """维修登记表"""
    __tablename__ = 'repair_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    repair_date = Column(Date, comment='报修日期')
    repair_dept = Column(String(100), comment='报修部门')
    equipment_name = Column(String(200), comment='故障设备')
    symptom = Column(Text, comment='故障现象')
    handler = Column(String(50), comment='经办人')
    sent_date = Column(Date, comment='送修日期')
    factory = Column(String(100), comment='送修厂家')
    return_date = Column(Date, comment='返修日期')
    result = Column(Text, comment='处理结果')
    remark = Column(Text, comment='备注')
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())

class StockMaster(Base):
    """物品库存总表"""
    __tablename__ = 'stock_master'
    
    item_id = Column(Integer, primary_key=True, autoincrement=True)
    item_name = Column(String(100), unique=True, nullable=False, comment='物品名称')
    initial_qty = Column(Integer, default=0, comment='期初数量')
    total_in = Column(Integer, default=0, comment='累计采购')
    total_out = Column(Integer, default=0, comment='累计领用')
    category = Column(String(50), comment='物品分类')
    unit = Column(String(20), comment='单位')
    min_stock = Column(Integer, default=10, comment='最低库存预警')
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())

class PurchaseRecord(Base):
    """采购记录表"""
    __tablename__ = 'purchase_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    purchase_date = Column(Date, nullable=False, comment='采购日期')
    item_id = Column(Integer, nullable=False, comment='物品ID')
    item_name = Column(String(100), comment='物品名称')
    quantity = Column(Integer, nullable=False, comment='采购数量')
    supplier = Column(String(100), comment='供应商')
    unit_price = Column(Integer, comment='单价')
    total_price = Column(Integer, comment='总价')
    operator = Column(String(50), comment='经办人')
    remark = Column(Text, comment='备注')
    created_at = Column(TIMESTAMP, default=func.now())

class UsageRecord(Base):
    """领用记录表"""
    __tablename__ = 'usage_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    usage_date = Column(Date, nullable=False, comment='领用日期')
    item_id = Column(Integer, nullable=False, comment='物品ID')
    item_name = Column(String(100), comment='物品名称')
    quantity = Column(Integer, nullable=False, comment='领用数量')
    usage_dept = Column(String(100), comment='领用部门')
    usage_person = Column(String(50), comment='领用人')
    operator = Column(String(50), comment='经办人')
    remark = Column(Text, comment='备注')
    created_at = Column(TIMESTAMP, default=func.now())

class FixedAsset(Base):
    """固定资产卡片表"""
    __tablename__ = 'fixed_assets'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_no = Column(String(50), unique=True, nullable=False, comment='资产编号')
    asset_name = Column(String(200), nullable=False, comment='资产名称')
    asset_category = Column(String(50), comment='资产类别')
    asset_owner = Column(String(100), comment='资产归属')
    responsible_person = Column(String(50), comment='责任人')
    location = Column(String(100), comment='位置')
    user = Column(String(50), comment='使用人')
    original_dept = Column(String(100), comment='原归属科室')
    purchase_date = Column(Date, comment='采购日期')
    price = Column(Integer, comment='价格')
    status = Column(Integer, default=1, comment='状态 1:在用 2:闲置 3:报废')
    remark = Column(Text, comment='备注')
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())

class SystemAuditLog(Base):
    """系统审计日志表"""
    __tablename__ = 'system_audit_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    log_category = Column(String(20), comment='日志类型 OPERATION/SECURITY/SYSTEM')
    operator = Column(String(50), comment='操作人')
    action_type = Column(String(50), comment='操作类型')
    detail = Column(Text, comment='详细信息')
    client_ip = Column(String(50), comment='客户端IP')
    created_at = Column(TIMESTAMP, default=func.now(), index=True)

class Department(Base):
    """科室维护表"""
    __tablename__ = 'departments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    dept_name = Column(String(100), unique=True, nullable=False, comment='科室名称')
    dept_code = Column(String(20), unique=True, comment='科室代码')
    parent_id = Column(Integer, ForeignKey('departments.id'), comment='上级科室ID')
    description = Column(Text, comment='科室描述')
    contact_person = Column(String(50), comment='联系人')
    contact_phone = Column(String(20), comment='联系电话')
    status = Column(Integer, default=1, comment='状态 1:启用 0:禁用')
    sort_order = Column(Integer, default=0, comment='排序顺序')
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())

class SystemConfig(Base):
    """系统配置表"""
    __tablename__ = 'system_config'

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(50), unique=True, nullable=False, comment='配置键')
    config_value = Column(Text, comment='配置值')
    config_type = Column(String(20), comment='配置类型 string/number/boolean/image')
    description = Column(String(200), comment='配置描述')
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())

class ItemCategory(Base):
    """物品分类表"""
    __tablename__ = 'item_categories'

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_name = Column(String(100), unique=True, nullable=False, comment='分类名称')
    category_code = Column(String(20), unique=True, comment='分类代码')
    parent_id = Column(Integer, ForeignKey('item_categories.id'), comment='上级分类ID')
    description = Column(Text, comment='分类描述')
    status = Column(Integer, default=1, comment='状态 1:启用 0:禁用')
    sort_order = Column(Integer, default=0, comment='排序顺序')
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())

class ServiceType(Base):
    """服务类型表"""
    __tablename__ = 'service_types'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    service_name = Column(String(100), unique=True, nullable=False, comment='服务类型名称')
    service_code = Column(String(20), unique=True, comment='服务类型代码')
    description = Column(Text, comment='服务类型描述')
    status = Column(Integer, default=1, comment='状态 1:启用 0:禁用')
    sort_order = Column(Integer, default=0, comment='排序顺序')
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())

class Holiday(Base):
    """节假日表"""
    __tablename__ = 'holidays'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, unique=True, nullable=False, comment='日期')
    name = Column(String(50), comment='节假日名称')
    is_holiday = Column(Integer, default=1, comment='是否为节假日 1:是 0:否（调休工作日）')
    year = Column(Integer, comment='年份')
    created_at = Column(TIMESTAMP, default=func.now())

class NotificationLog(Base):
    """通知记录表"""
    __tablename__ = 'notification_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    notification_type = Column(String(10), nullable=False, comment='通知类型 sms/email')
    recipient = Column(String(200), nullable=False, comment='收件人（手机号或邮箱）')
    recipient_name = Column(String(50), comment='收件人姓名')
    subject = Column(String(200), comment='主题（邮件用）')
    content_summary = Column(Text, comment='内容摘要')
    schedule_date = Column(Date, comment='关联值班日期')
    shift_type = Column(String(20), comment='班次类型')
    campus = Column(String(50), comment='院区')
    remind_type = Column(String(50), comment='提醒类型')
    status = Column(String(10), nullable=False, default='pending', comment='发送状态 pending/success/failed')
    error_message = Column(Text, comment='错误信息')
    request_id = Column(String(100), comment='API请求ID')
    created_at = Column(TIMESTAMP, default=func.now())

class SystemNotification(Base):
    """系统通知表"""
    __tablename__ = 'system_notifications'

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False, comment='通知标题')
    content = Column(Text, nullable=False, comment='通知内容')
    notification_type = Column(String(20), default='info', comment='通知类型 info/warning/error/success')
    priority = Column(Integer, default=0, comment='优先级')
    created_by = Column(String(50), comment='发布人')
    expires_at = Column(TIMESTAMP, comment='过期时间，为空则永不过期')
    created_at = Column(TIMESTAMP, default=func.now())

class SystemNotificationRead(Base):
    """系统通知阅读记录表"""
    __tablename__ = 'system_notification_reads'

    id = Column(Integer, primary_key=True, autoincrement=True)
    notification_id = Column(BigInteger, nullable=False, comment='通知ID')
    username = Column(String(50), nullable=False, comment='用户名')
    read_at = Column(TIMESTAMP, default=func.now())

class LoginAttempt(Base):
    """登录尝试记录表 - 用于限制IP登录失败次数"""
    __tablename__ = 'login_attempts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip_address = Column(String(50), nullable=False, comment='IP地址')
    username = Column(String(50), comment='尝试登录的用户名')
    attempt_count = Column(Integer, default=1, comment='尝试次数')
    first_attempt_at = Column(TIMESTAMP, default=func.now(), comment='首次尝试时间')
    last_attempt_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now(), comment='最后尝试时间')
    is_locked = Column(Integer, default=0, comment='是否被锁定 0:否 1:是')

class IpBlacklist(Base):
    """IP黑名单表"""
    __tablename__ = 'ip_blacklist'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip_address = Column(String(50), nullable=False, unique=True, comment='IP地址或网段')
    reason = Column(String(255), comment='加入黑名单原因')
    created_by = Column(String(50), comment='添加人')
    created_at = Column(TIMESTAMP, default=func.now())
    expires_at = Column(TIMESTAMP, comment='过期时间，NULL表示永久')
