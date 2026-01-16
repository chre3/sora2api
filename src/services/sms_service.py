"""SMS 服务 - 使用 Hero SMS API"""
import asyncio
import logging
from typing import Optional, Dict
from curl_cffi.requests import AsyncSession

logger = logging.getLogger(__name__)

BASE_URL = "https://hero-sms.com/stubs/handler_api.php"

# 状态码常量（Hero SMS API 规范）
HERO_SMS_STATUS = {
    "READY": 1,  # 已发送短信（通知已准备好接收验证码）
    "RESEND": 3,  # 请求重新发送短信
    "COMPLETE": 6,  # 激活完成（已收到并确认激活码）
    "CANCEL": 8,  # 取消激活（退款）
}

# API 响应状态
HERO_SMS_RESPONSE_STATUS = {
    "WAIT_CODE": "STATUS_WAIT_CODE",  # 在等待短信
    "WAIT_RETRY": "STATUS_WAIT_RETRY",  # 等待着代码确认
    "WAIT_RESEND": "STATUS_WAIT_RESEND",  # 等待着短信重发
    "CANCEL": "STATUS_CANCEL",  # 接码被取消了
    "OK": "STATUS_OK",  # 收到了验证码
    "READY": "ACCESS_READY",  # 已确认电话可用性
    "RETRY_GET": "ACCESS_RETRY_GET",  # 等待着新短信
    "ACTIVATION": "ACCESS_ACTIVATION",  # 项目接码成功
    "CANCELED": "ACCESS_CANCEL",  # 已取消接码
}

class GrizzlySMSService:
    """Hero SMS 服务"""
    
    def __init__(self, api_key: str, service: str = None, country: str = None, max_price: float = None):
        """
        初始化 SMS 服务
        
        Args:
            api_key: Hero SMS API Key
            service: 服务代码（默认从环境变量读取）
            country: 国家代码（默认从环境变量读取）
            max_price: 最高价格（默认从环境变量读取）
        """
        self.api_key = api_key
        self.service = service
        self.country = country
        self.max_price = max_price
        self.activation_id = None
        self.phone_number = None
    
    async def init(self):
        """初始化服务"""
        if not self.api_key or self.api_key == "":
            raise Exception("HERO_SMS_API_KEY 未设置，请在配置中设置")
        logger.info("正在初始化 Hero SMS 服务...")
        logger.info("Hero SMS 服务已就绪")
        logger.info(f"API Key: {self.api_key[:8]}...")
        logger.info(f"服务: {self.service}, 国家ID: {self.country}, 出价: {self.max_price}")
    
    async def _api_request(self, params: Dict, retries: int = 3, timeout: int = 30000) -> str:
        """发送 API 请求（带超时和重试）"""
        url = BASE_URL
        request_params = {"api_key": self.api_key}
        request_params.update(params)
        
        last_error = None
        
        for attempt in range(1, retries + 1):
            try:
                async with AsyncSession() as session:
                    response = await session.get(
                        url,
                        params=request_params,
                        timeout=timeout / 1000,
                        headers={
                            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                            "Accept": "*/*",
                        }
                    )
                    
                    if not response.ok:
                        raise Exception(f"HTTP {response.status_code}: {response.text}")
                    
                    return response.text
            except Exception as error:
                last_error = error
                is_last_attempt = attempt == retries
                is_network_error = any(keyword in str(error).lower() for keyword in 
                                     ["network", "connection", "timeout", "econnrefused", "etimedout"])
                
                if is_last_attempt:
                    logger.error(f"API 请求失败 (已重试 {retries} 次): {error}")
                    raise
                
                if is_network_error:
                    wait_time = attempt * 1000
                    logger.warn(f"API 请求失败 (尝试 {attempt}/{retries}): {error}，{wait_time}ms 后重试...")
                    await asyncio.sleep(wait_time / 1000)
                    continue
                
                raise
        
        raise last_error or Exception("API 请求失败")
    
    async def get_balance(self) -> float:
        """查询余额"""
        try:
            response = await self._api_request({"action": "getBalance"})
            
            if response.startswith("ACCESS_BALANCE:"):
                balance = float(response.split(":")[1])
                logger.info(f"账户余额: {balance}")
                return balance
            elif response == "BAD_KEY":
                raise Exception("API 密钥不正确")
            else:
                raise Exception(f"查询余额失败: {response}")
        except Exception as error:
            logger.error(f"查询余额失败: {error}")
            raise
    
    async def get_number(
        self,
        service: str = None,
        country: str = None,
        max_price: float = None,
        provider_ids: str = None,
        except_provider_ids: str = None
    ) -> Dict:
        """
        申请号码
        
        Args:
            service: 服务代码
            country: 国家代码
            max_price: 最高价格
            provider_ids: 供应商ID列表，逗号分隔
            except_provider_ids: 排除的供应商ID列表，逗号分隔
            
        Returns:
            包含 activationId 和 phoneNumber 的字典
        """
        final_service = service or self.service
        final_country = country or self.country
        final_max_price = max_price if max_price is not None else self.max_price
        
        logger.info(f"正在申请号码 (服务: {final_service}, 国家ID: {final_country}, 出价: {final_max_price})...")
        
        params = {
            "action": "getNumberV2",
            "service": final_service,
            "country": final_country,
        }
        
        if final_max_price is not None:
            params["maxPrice"] = str(final_max_price)
        if provider_ids:
            params["providerIds"] = provider_ids
        if except_provider_ids:
            params["exceptProviderIds"] = except_provider_ids
        
        try:
            response = await self._api_request(params)
            
            # 检查错误响应
            if response == "BAD_KEY":
                raise Exception("API 密钥不正确")
            elif response == "NO_NUMBERS":
                raise Exception("没有可用号码，请稍后重试或更换国家")
            elif "prohibited for sale" in response:
                raise Exception("该服务被禁止销售，请选择其他服务")
            elif response == "SERVICE_UNAVAILABLE_REGION":
                raise Exception("您所在地区的访问受限，请使用其他地区的 IP 地址")
            elif response.startswith("WRONG_MAX_PRICE:"):
                actual_price = float(response.split(":")[1])
                raise Exception(f"最高价格设置过低，实际价格为 {actual_price}，请提高 maxPrice 参数或设置为 null")
            
            # 解析 JSON 响应
            try:
                data = response.json() if hasattr(response, 'json') else eval(response)
                if isinstance(data, str):
                    import json
                    data = json.loads(data)
            except:
                import json
                data = json.loads(response)
            
            self.activation_id = data["activationId"]
            self.phone_number = data["phoneNumber"]
            self.service = final_service
            self.country = final_country
            
            logger.info(f"获取到号码: {self.phone_number}")
            logger.info(f"激活ID: {self.activation_id}")
            logger.info(f"激活费用: {data.get('activationCost')} {data.get('currency')}")
            
            return {
                "activationId": self.activation_id,
                "phoneNumber": self.phone_number,
                "activationCost": data.get("activationCost"),
                "currency": data.get("currency"),
                "countryCode": data.get("countryCode"),
                "canGetAnotherSms": data.get("canGetAnotherSms") == "1",
                "activationTime": data.get("activationTime"),
            }
        except Exception as error:
            logger.error(f"申请号码失败: {error}")
            raise
    
    async def set_status(self, status: int, activation_id: int = None, forward: bool = None) -> str:
        """
        设置激活状态
        
        Args:
            status: 状态码（-1: 取消, 1: 可用, 6: 完成, 8: 取消）
            activation_id: 激活ID（可选，默认使用当前激活ID）
            forward: 是否转发（可选）
            
        Returns:
            响应状态
        """
        id = activation_id or self.activation_id
        if not id:
            raise Exception("激活ID不存在，请先申请号码")
        
        params = {
            "action": "setStatus",
            "status": str(status),
            "id": str(id),
        }
        
        if forward is not None:
            params["forward"] = str(forward)
        
        try:
            response = await self._api_request(params)
            
            if response == "BAD_KEY":
                raise Exception("API 密钥不正确")
            elif response == "NO_ACTIVATION":
                raise Exception("激活ID不存在")
            elif response == "BAD_STATUS":
                raise Exception("状态不正确")
            
            return response
        except Exception as error:
            logger.error(f"设置状态失败: {error}")
            raise
    
    async def get_status(self, activation_id: int = None) -> Dict:
        """
        获取激活状态
        
        Args:
            activation_id: 激活ID（可选，默认使用当前激活ID）
            
        Returns:
            状态信息
        """
        id = activation_id or self.activation_id
        if not id:
            raise Exception("激活ID不存在，请先申请号码")
        
        try:
            response = await self._api_request({
                "action": "getStatus",
                "id": str(id),
            })
            
            if response == "BAD_KEY":
                raise Exception("API 密钥不正确")
            elif response == "NO_ACTIVATION":
                raise Exception("激活ID不存在")
            elif response == "BAD_ACTION":
                raise Exception("操作不正确")
            elif response == "SERVICE_UNAVAILABLE_REGION":
                raise Exception("您所在地区的访问受限")
            
            # 解析响应
            if response == HERO_SMS_RESPONSE_STATUS["WAIT_CODE"]:
                return {"status": "WAIT_CODE", "message": "在等待短信"}
            elif response.startswith(HERO_SMS_RESPONSE_STATUS["WAIT_RETRY"]):
                parts = response.split(":")
                return {
                    "status": "WAIT_RETRY",
                    "lastCode": parts[1] if len(parts) > 1 else None,
                    "message": "等待着代码确认",
                }
            elif response == HERO_SMS_RESPONSE_STATUS["WAIT_RESEND"]:
                return {"status": "WAIT_RESEND", "message": "等待着短信重发"}
            elif response == HERO_SMS_RESPONSE_STATUS["CANCEL"]:
                return {"status": "CANCEL", "message": "接码被取消了"}
            elif response.startswith(HERO_SMS_RESPONSE_STATUS["OK"]):
                parts = response.split(":")
                code = parts[1] if len(parts) > 1 else None
                return {"status": "OK", "code": code, "message": "收到了验证码"}
            
            return {"status": "UNKNOWN", "message": response}
        except Exception as error:
            logger.error(f"获取状态失败: {error}")
            raise
    
    async def set_ready(self) -> str:
        """告知号码可用（已发送短信）- 使用状态 1"""
        logger.info("告知号码可用（已发送短信）...")
        response = await self.set_status(HERO_SMS_STATUS["READY"])
        if response == HERO_SMS_RESPONSE_STATUS["READY"]:
            logger.info("已确认电话可用性")
        else:
            logger.info(f"设置就绪状态响应: {response}")
        return response
    
    async def resend_sms(self) -> str:
        """请求重新发送短信 - 使用状态 3"""
        logger.info("请求重新发送短信...")
        try:
            response = await self.set_status(HERO_SMS_STATUS["RESEND"])
            logger.info("已请求重新发送短信")
            return response
        except Exception as error:
            logger.error(f"请求重新发送短信失败: {error}")
            raise
    
    async def set_complete(self) -> str:
        """完成接码"""
        logger.info("完成接码...")
        try:
            response = await self.set_status(HERO_SMS_STATUS["COMPLETE"])
            if response == HERO_SMS_RESPONSE_STATUS["ACTIVATION"]:
                logger.info("接码成功")
            else:
                logger.info(f"完成接码响应: {response}")
            return response
        except Exception as error:
            logger.warn(f"设置完成状态失败: {error}，但接码流程已成功完成")
            return None
    
    async def cancel(self) -> str:
        """取消接码（使用状态 8）"""
        logger.info("取消接码...")
        try:
            response = await self.set_status(HERO_SMS_STATUS["CANCEL"])
            if response == HERO_SMS_RESPONSE_STATUS["CANCELED"]:
                logger.info("已取消接码")
                return response
            else:
                logger.info(f"取消接码响应: {response}")
                return response
        except Exception as error:
            logger.warn(f"取消接码失败: {error}")
            return None
    
    async def wait_for_verification_code(self, timeout: int = 120000, poll_interval: int = 3000) -> str:
        """
        等待并获取验证码
        
        Args:
            timeout: 超时时间（毫秒），默认120秒
            poll_interval: 轮询间隔（毫秒），默认3秒
            
        Returns:
            验证码
        """
        if not self.activation_id:
            raise Exception("激活ID不存在，请先申请号码")
        
        logger.info("正在等待验证码...")
        logger.info(f"电话号码: {self.phone_number}")
        
        start_time = asyncio.get_event_loop().time() * 1000
        last_status = None
        
        while (asyncio.get_event_loop().time() * 1000 - start_time) < timeout:
            try:
                status_info = await self.get_status()
                
                # 如果状态改变，记录日志
                if status_info["status"] != last_status:
                    logger.info(f"状态: {status_info.get('message', status_info['status'])}")
                    last_status = status_info["status"]
                
                # 如果收到验证码
                if status_info["status"] == "OK" and status_info.get("code"):
                    logger.info(f"获取到验证码: {status_info['code']}")
                    return status_info["code"]
                
                # 如果需要重发短信
                if status_info["status"] == "WAIT_RESEND":
                    logger.warn("需要重发短信，使用状态 3 请求重新发送...")
                    try:
                        await self.set_status(HERO_SMS_STATUS["RESEND"])
                        logger.info("已请求重新发送短信")
                    except Exception as resend_error:
                        logger.warn(f"请求重新发送短信失败: {resend_error}")
                
                # 如果被取消
                if status_info["status"] == "CANCEL":
                    raise Exception("接码已被取消")
                
                elapsed = int((asyncio.get_event_loop().time() * 1000 - start_time) / 1000)
                remaining = int((timeout - (asyncio.get_event_loop().time() * 1000 - start_time)) / 1000)
                logger.info(f"等待验证码中... (已等待 {elapsed} 秒，剩余 {remaining} 秒)")
                
                await asyncio.sleep(poll_interval / 1000)
            except Exception as error:
                # 如果是超时错误，继续重试
                if "超时" in str(error) or "timeout" in str(error).lower():
                    elapsed = int((asyncio.get_event_loop().time() * 1000 - start_time) / 1000)
                    logger.warn(f"检查状态时出错: {error}，继续等待... (已等待 {elapsed} 秒)")
                    await asyncio.sleep(poll_interval / 1000)
                    continue
                raise
        
        raise Exception(f"等待验证码超时 ({timeout / 1000} 秒)")
    
    def get_phone_number(self) -> Optional[str]:
        """获取电话号码"""
        return self.phone_number
    
    def get_activation_id(self) -> Optional[int]:
        """获取激活ID"""
        return self.activation_id
    
    async def close(self):
        """关闭服务（清理资源）"""
        # 如果还有激活的号码，尝试取消
        if self.activation_id:
            try:
                await self.cancel()
            except:
                pass
        self.activation_id = None
        self.phone_number = None
        self.service = None
        self.country = None
