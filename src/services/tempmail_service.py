"""临时邮箱服务 - 使用 juheapi.com API"""
import asyncio
import logging
from typing import Optional
from curl_cffi.requests import AsyncSession

logger = logging.getLogger(__name__)

BASE_URL = 'https://hub.juheapi.com/temp-mail/v1'

class TempMailService:
    """临时邮箱服务"""
    
    # 不支持的邮箱后缀
    BLOCKED_SUFFIXES = ['.top']
    
    def __init__(self, api_key: str):
        """
        初始化临时邮箱服务
        
        Args:
            api_key: juheapi.com API Key
        """
        self.api_key = api_key
        self.email = None
    
    def is_email_supported(self, email: str) -> bool:
        """检查邮箱后缀是否被支持"""
        if not email:
            return False
        for suffix in self.BLOCKED_SUFFIXES:
            if email.lower().endswith(suffix):
                return False
        return True
    
    async def init(self):
        """初始化临时邮箱服务"""
        logger.info('正在初始化临时邮箱服务...')
        if not self.api_key or self.api_key == "YOUR_API_KEY":
            raise Exception("JUHE_API_KEY 未设置，请在配置中设置")
        logger.info('临时邮箱服务已就绪')
    
    async def get_email_address(self, max_retries: int = 10) -> str:
        """
        获取临时邮箱地址（自动过滤不支持的后缀）
        
        Args:
            max_retries: 最大重试次数
            
        Returns:
            邮箱地址
        """
        logger.info('正在获取临时邮箱地址...')
        
        for attempt in range(1, max_retries + 1):
            try:
                async with AsyncSession() as session:
                    response = await session.get(
                        f"{BASE_URL}/create?apikey={self.api_key}",
                        timeout=30
                    )
                    
                    if not response.ok:
                        logger.error(f"API 响应内容: {response.text}")
                        raise Exception(f"HTTP {response.status_code}: {response.reason}")
                    
                    data = response.json()
                    
                    if data.get("code") == "0" and data.get("data"):
                        email = data["data"]["email"]
                        
                        # 检查邮箱后缀是否支持
                        if not self.is_email_supported(email):
                            logger.warn(f"邮箱 {email} 后缀不支持，重新获取... ({attempt}/{max_retries})")
                            continue
                        
                        self.email = email
                        logger.info(f"获取到临时邮箱: {self.email}")
                        logger.info(f"邮箱有效期: {data['data'].get('expires_in', '未知')} 秒")
                        return self.email
                    else:
                        raise Exception(f"API 错误: {data.get('msg', str(data))}")
            except Exception as error:
                if attempt == max_retries:
                    logger.error(f"获取邮箱失败: {error}")
                    raise
                logger.warn(f"获取邮箱出错，重试... ({attempt}/{max_retries}): {error}")
                await asyncio.sleep(1)
        
        raise Exception('获取有效邮箱失败，已达最大重试次数')
    
    async def check_inbox(self) -> list:
        """
        检查收件箱
        
        Returns:
            邮件列表
        """
        if not self.email:
            raise Exception('邮箱未初始化，请先调用 get_email_address()')
        
        try:
            async with AsyncSession() as session:
                response = await session.get(
                    f"{BASE_URL}/get-emails?apikey={self.api_key}&email_address={self.email}",
                    timeout=30
                )
                
                if not response.ok:
                    raise Exception(f"HTTP {response.status_code}: {response.reason}")
                
                data = response.json()
                
                if data.get("code") == "0":
                    return data.get("data", [])
                else:
                    raise Exception(f"API 错误: {data.get('msg', str(data))}")
        except Exception as error:
            logger.warn(f"检查收件箱失败: {error}")
            return []
    
    def extract_code_from_content(self, content: str) -> Optional[str]:
        """从邮件内容中提取验证码"""
        if not content:
            return None
        
        import re
        code_patterns = [
            r'code is (\d{6})',
            r'code[:\s]+(\d{6})',
            r'verification code[:\s]+(\d{6})',
            r'verify[:\s]+(\d{6})',
            r'验证码[:\s]*(\d{6})',
            r'Your code is[:\s]*(\d{6})',
            r'Enter this code[:\s]*(\d{6})',
            r'>\s*(\d{6})\s*<',
            r'\b(\d{6})\b'
        ]
        
        for pattern in code_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    async def wait_for_verification_code(self, timeout: int = 120000, poll_interval: int = 5000) -> str:
        """
        等待并获取验证码邮件
        
        Args:
            timeout: 超时时间（毫秒）
            poll_interval: 轮询间隔（毫秒）
            
        Returns:
            验证码
        """
        logger.info('正在等待验证码邮件...')
        
        start_time = asyncio.get_event_loop().time() * 1000
        
        while (asyncio.get_event_loop().time() * 1000 - start_time) < timeout:
            try:
                messages = await self.check_inbox()
                
                if messages and len(messages) > 0:
                    logger.info(f"收到 {len(messages)} 封邮件")
                    
                    for msg in messages:
                        subject = msg.get("subject", "")
                        from_addr = msg.get("from", "")
                        body = msg.get("body", "")
                        
                        logger.info(f"邮件: 来自 {from_addr}, 主题: {subject}")
                        
                        # 尝试从邮件内容提取验证码
                        code = self.extract_code_from_content(body) or self.extract_code_from_content(subject)
                        if code:
                            logger.info(f"获取到验证码: {code}")
                            return code
                
                elapsed = int((asyncio.get_event_loop().time() * 1000 - start_time) / 1000)
                logger.info(f"暂未收到验证码，已等待 {elapsed} 秒，继续等待...")
                
                await asyncio.sleep(poll_interval / 1000)
            except Exception as error:
                logger.warn(f"检查邮件时出错: {error}")
                await asyncio.sleep(poll_interval / 1000)
        
        raise Exception('等待验证码超时')
    
    def get_email(self) -> Optional[str]:
        """获取当前邮箱地址"""
        return self.email
    
    async def close(self):
        """关闭服务（清理资源）"""
        self.email = None
