"""自动注册服务 - 使用 Python 注册流程进行定时补号"""
import os
from typing import Optional, Dict, List
from datetime import datetime
import logging

from .register_flow import RegisterFlowService
from .token_manager import TokenManager
from ..core.database import Database

logger = logging.getLogger(__name__)

class AutoRegisterService:
    """自动注册服务，使用 Python 注册流程"""
    
    def __init__(self, db: Database = None, token_manager: TokenManager = None):
        """
        初始化自动注册服务
        
        Args:
            db: 数据库实例（如果为 None，会创建新实例）
            token_manager: Token 管理器实例（如果为 None，会创建新实例）
        """
        self.db = db or Database()
        self.token_manager = token_manager or TokenManager(self.db)
        
        # 从环境变量读取 API keys
        self.tempmail_api_key = os.getenv("JUHE_API_KEY", "")
        self.sms_api_key = os.getenv("HERO_SMS_API_KEY", "")
        
        if not self.tempmail_api_key:
            logger.warn("JUHE_API_KEY 未设置，临时邮箱服务可能无法使用")
        if not self.sms_api_key:
            logger.warn("HERO_SMS_API_KEY 未设置，SMS 服务可能无法使用")
    
    async def register_one(
        self,
        country_code: str,
        service_code: str,
        max_price: float,
        binding_rule: str = "1绑1",  # "1绑1" or "1绑3"
        proxy_url: Optional[str] = None
    ) -> Dict:
        """
        注册一个账号
        
        Args:
            country_code: 国家代码（如 "151"）
            service_code: 服务代码（如 "dr"）
            max_price: 出价金额
            binding_rule: 绑定规则（"1绑1" 或 "1绑3"）
            proxy_url: 代理配置（可选）
            
        Returns:
            包含注册结果的字典
        """
        if not self.tempmail_api_key:
            raise Exception("JUHE_API_KEY 未设置，无法使用临时邮箱服务")
        if not self.sms_api_key:
            raise Exception("HERO_SMS_API_KEY 未设置，无法使用 SMS 服务")
        
        # 创建注册流程服务
        register_flow = RegisterFlowService(
            db=self.db,
            token_manager=self.token_manager,
            tempmail_api_key=self.tempmail_api_key,
            sms_api_key=self.sms_api_key,
            sms_service=service_code,
            sms_country=country_code,
            sms_max_price=max_price,
            proxy_url=proxy_url
        )
        
        # 执行注册
        result = await register_flow.register_one(
            country_code=country_code,
            service_code=service_code,
            max_price=max_price,
            binding_rule=binding_rule,
            proxy_url=proxy_url
        )
        
        return result
    
    async def get_latest_accounts(self, count: int = 1) -> List[Dict]:
        """获取最新的账号列表（从数据库）"""
        try:
            tokens = await self.db.get_all_tokens()
            # 按创建时间倒序排列，取最新的 count 个
            tokens.sort(key=lambda x: x.created_at or datetime.min, reverse=True)
            
            accounts = []
            for token in tokens[:count]:
                accounts.append({
                    "email": token.email,
                    "session_token": token.st,
                    "access_token": token.token,
                    "refresh_token": token.rt,
                    "client_id": token.client_id,
                    "proxy_url": token.proxy_url,
                    "remark": token.remark,
                    "is_active": token.is_active,
                    "image_enabled": token.image_enabled,
                    "video_enabled": token.video_enabled,
                    "image_concurrency": token.image_concurrency,
                    "video_concurrency": token.video_concurrency,
                })
            
            return accounts
        except Exception as e:
            logger.error(f"读取账号列表失败: {e}")
            return []
