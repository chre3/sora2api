"""完整的注册流程服务 - 整合所有注册相关服务"""
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
from playwright.async_api import async_playwright, Browser

from .register_service import OpenAIRegister
from .tempmail_service import TempMailService
from .sms_service import GrizzlySMSService
from .token_manager import TokenManager
from ..core.database import Database

logger = logging.getLogger(__name__)


class RegisterFlowService:
    """完整的注册流程服务"""
    
    def __init__(
        self,
        db: Database,
        token_manager: TokenManager,
        tempmail_api_key: str,
        sms_api_key: str,
        sms_service: str = None,
        sms_country: str = None,
        sms_max_price: float = None,
        proxy_url: Optional[str] = None,
        screenshot_dir: str = "screenshots"
    ):
        """
        初始化注册流程服务
        
        Args:
            db: 数据库实例
            token_manager: Token 管理器实例（用于导入账号）
            tempmail_api_key: 临时邮箱 API Key
            sms_api_key: SMS API Key
            sms_service: SMS 服务代码
            sms_country: SMS 国家代码
            sms_max_price: SMS 最高价格
            proxy_url: 代理 URL（可选）
            screenshot_dir: 截图保存目录
        """
        self.db = db
        self.token_manager = token_manager
        self.tempmail_api_key = tempmail_api_key
        self.sms_api_key = sms_api_key
        self.sms_service = sms_service
        self.sms_country = sms_country
        self.sms_max_price = sms_max_price
        self.proxy_url = proxy_url
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(exist_ok=True)
        
        # 从环境变量读取配置（如果未提供）
        self.sms_service = self.sms_service or os.getenv("HERO_SMS_SERVICE", "dr")
        self.sms_country = self.sms_country or os.getenv("HERO_SMS_COUNTRY", "151")
        if self.sms_max_price is None:
            max_price_str = os.getenv("HERO_SMS_MAX_PRICE")
            self.sms_max_price = float(max_price_str) if max_price_str else 0.025
    
    async def register_one(
        self,
        country_code: str = None,
        service_code: str = None,
        max_price: float = None,
        binding_rule: str = "1绑1",
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
        # 使用传入的参数或实例默认值
        final_country = country_code or self.sms_country
        final_service = service_code or self.sms_service
        final_max_price = max_price if max_price is not None else self.sms_max_price
        final_proxy = proxy_url or self.proxy_url
        
        browser = None
        temp_mail = None
        register = None
        sms_service = None
        
        try:
            # 启动浏览器
            async with async_playwright() as p:
                # 检测 Chrome 路径
                chrome_path = None
                if os.getenv("CHROME_PATH"):
                    chrome_path = os.getenv("CHROME_PATH")
                else:
                    # macOS 自动检测
                    mac_chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
                    if Path(mac_chrome_path).exists():
                        chrome_path = mac_chrome_path
                
                browser_options = {
                    "headless": True,  # 无头模式（Chrome 132+ 会自动使用新的 headless 模式）
                    "slow_mo": int(os.getenv("SLOW_MO", "50")),
                    "args": [
                        "--no-first-run",
                        "--window-size=1920,1080",
                        "--incognito",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-features=IsolateOrigins,site-per-process",
                        "--lang=en-US,en",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                        "--disable-gpu",
                        "--disable-software-rasterizer",
                        "--disable-extensions",
                        "--disable-background-networking",
                        "--disable-background-timer-throttling",
                        "--disable-backgrounding-occluded-windows",
                        "--disable-breakpad",
                        "--disable-component-extensions-with-background-pages",
                        "--disable-component-update",
                        "--disable-default-apps",
                        "--disable-hang-monitor",
                        "--disable-ipc-flooding-protection",
                        "--disable-popup-blocking",
                        "--disable-prompt-on-repost",
                        "--disable-renderer-backgrounding",
                        "--disable-sync",
                        "--disable-translate",
                        "--metrics-recording-only",
                        "--no-default-browser-check",
                        "--mute-audio",
                        "--disk-cache-size=1",
                        "--media-cache-size=1",
                        "--disable-application-cache",
                        "--aggressive-cache-discard",
                    ],
                    "ignore_default_args": [
                        "--enable-automation",
                        "--enable-blink-features=IdleDetection",
                    ],
                }
                
                # 如果指定了 Chrome 路径，使用 executable_path
                if chrome_path:
                    browser_options["executable_path"] = chrome_path
                    logger.info(f"使用指定的 Chrome 路径: {chrome_path}")
                else:
                    logger.info("使用 Playwright Chromium")
                
                browser = await p.chromium.launch(**browser_options)
                logger.info("浏览器已启动")
                
                # 记录代理配置信息
                if final_proxy:
                    # 隐藏密码部分用于日志
                    proxy_log = final_proxy
                    if "@" in proxy_log:
                        parts = proxy_log.split("@")
                        if len(parts) == 2:
                            auth_part = parts[0]
                            if "://" in auth_part and ":" in auth_part.split("://")[-1]:
                                username = auth_part.split("://")[-1].split(":")[0]
                                proxy_log = proxy_log.replace(auth_part.split("://")[-1], f"{username}:***")
                    logger.info(f"代理配置: {proxy_log}")
                else:
                    logger.info("代理配置: 无代理")
                
                # 初始化服务
                logger.info("正在初始化临时邮箱服务...")
                temp_mail = TempMailService(self.tempmail_api_key)
                await temp_mail.init()
                logger.info("临时邮箱服务初始化完成")
                
                logger.info("正在初始化注册服务...")
                logger.info(f"传递代理配置到注册服务: {'已配置' if final_proxy else '无代理'}")
                register = OpenAIRegister(
                    browser,
                    str(self.screenshot_dir),
                    proxy_url=final_proxy
                )
                await register.init()
                logger.info("注册服务初始化完成")
                
                sms_service = GrizzlySMSService(
                    self.sms_api_key,
                    service=final_service,
                    country=final_country,
                    max_price=final_max_price
                )
                
                # 1. 获取临时邮箱
                logger.info("步骤1: 正在获取临时邮箱...")
                email = await temp_mail.get_email_address()
                logger.info(f"步骤1完成: 获取到临时邮箱: {email}")
                
                # 2. 生成密码
                logger.info("步骤2: 正在生成密码...")
                password = register._generate_password()
                logger.info(f"步骤2完成: 密码已生成 (长度: {len(password)})")
                
                # 3. 执行注册
                logger.info("步骤3: 开始执行注册流程...")
                async def get_verification_code():
                    logger.info("等待邮箱验证码...")
                    code = await temp_mail.wait_for_verification_code(
                        timeout=int(os.getenv("WAIT_FOR_EMAIL_TIMEOUT", "120000"))
                    )
                    logger.info(f"收到验证码: {code}")
                    return code
                
                success = await register.register(email, password, get_verification_code)
                logger.info(f"步骤3完成: 注册{'成功' if success else '失败'}")
                
                if not success:
                    raise Exception("注册失败")
                
                logger.info(f"账户 {email} 注册成功！")
                
                # 4. 处理 Sora onboarding 用户名设置流程
                try:
                    await register._handle_sora_onboarding(email)
                    logger.info("Sora onboarding 完成")
                except Exception as error:
                    logger.error(f"Sora onboarding 失败: {error}")
                    # 即使 onboarding 失败，也继续获取 token
                
                # 5. 处理手机号验证流程
                # 在"1绑3"模式下，第一个账号不设置为完成状态，以便复用手机号
                set_complete = binding_rule == "1绑1"  # "1绑1"模式立即完成，"1绑3"模式最后一个才完成
                
                phone_result = await register._handle_phone_verification(
                    email, 
                    sms_service,
                    reuse_phone=False,  # 第一个账号申请新号码
                    set_complete=set_complete
                )
                
                access_token = phone_result.get("accessToken")
                session_token = phone_result.get("sessionToken")
                
                if not access_token:
                    raise Exception("无法获取 accessToken")
                
                # 6. 保存账号到数据库（使用 token_manager.add_token，会自动更新账号状态）
                accounts = []
                
                # 使用 token_manager.add_token 导入账号（会自动获取订阅信息、Sora2信息等）
                try:
                    token_obj = await self.token_manager.add_token(
                        token_value=access_token,
                        st=session_token,
                        rt=None,
                        client_id=None,
                        proxy_url=final_proxy,
                        remark=f"自动注册 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        update_if_exists=False,
                        image_enabled=True,
                        video_enabled=True,
                        image_concurrency=-1,
                        video_concurrency=3,
                        skip_status_update=False,  # 更新账号状态
                        email=email  # 提供邮箱以便离线模式使用
                    )
                    logger.info(f"账号已保存到数据库，Token ID: {token_obj.id}")
                    logger.info(f"账号状态已更新：订阅={token_obj.plan_title}, Sora2支持={token_obj.sora2_supported}")
                except ValueError as e:
                    # 如果账号已存在，尝试更新
                    if "已存在" in str(e):
                        logger.warn(f"账号已存在，尝试更新: {email}")
                        existing_token = await self.db.get_token_by_email(email)
                        if existing_token:
                            await self.token_manager.update_token(
                                token_id=existing_token.id,
                                token=access_token,
                                st=session_token,
                                proxy_url=final_proxy,
                                remark=f"自动注册更新 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                            )
                            token_obj = await self.db.get_token(existing_token.id)
                            logger.info(f"账号已更新，Token ID: {token_obj.id}")
                        else:
                            raise
                    else:
                        raise
                
                # 构建账号信息（使用 token_obj 的完整信息）
                account_info = {
                    "email": token_obj.email,
                    "session_token": token_obj.st,
                    "access_token": token_obj.token,
                    "refresh_token": token_obj.rt,
                    "client_id": token_obj.client_id,
                    "proxy_url": token_obj.proxy_url,
                    "remark": token_obj.remark,
                    "is_active": token_obj.is_active,
                    "image_enabled": token_obj.image_enabled,
                    "video_enabled": token_obj.video_enabled,
                    "image_concurrency": token_obj.image_concurrency,
                    "video_concurrency": token_obj.video_concurrency,
                }
                accounts.append(account_info)
                
                # 处理绑定规则
                result_accounts = accounts
                if binding_rule == "1绑3":
                    # 需要注册3个账号，复用同一个手机号
                    logger.info("1绑3模式：将复用第一个账号的手机号注册后续账号")
                    
                    # 保存第一个账号的 SMS 服务实例，以便复用手机号
                    # 注意：不要关闭这个 SMS 服务，以便后续账号复用
                    shared_sms_service = sms_service
                    sms_service = None  # 设置为 None，避免在 finally 中被关闭
                    
                    if len(accounts) < 3:
                        remaining = 3 - len(accounts)
                        for i in range(remaining):
                            # 再次注册
                            try:
                                # 关闭当前浏览器和临时邮箱（但保留 SMS 服务）
                                await register.close()
                                await browser.close()
                                await temp_mail.close()
                                # 注意：不关闭 sms_service，以便复用手机号
                                
                                # 重新启动浏览器和服务
                                browser = await p.chromium.launch(**browser_options)
                                
                                temp_mail = TempMailService(self.tempmail_api_key)
                                await temp_mail.init()
                                
                                register = OpenAIRegister(
                                    browser,
                                    str(self.screenshot_dir),
                                    proxy_url=final_proxy
                                )
                                await register.init()
                                
                                # 复用第一个账号的 SMS 服务（包含手机号和激活ID）
                                # 不需要创建新的 SMS 服务实例
                                
                                # 注册新账号
                                email = await temp_mail.get_email_address()
                                password = register._generate_password()
                                
                                async def get_verification_code_inner():
                                    code = await temp_mail.wait_for_verification_code(
                                        timeout=int(os.getenv("WAIT_FOR_EMAIL_TIMEOUT", "120000"))
                                    )
                                    return code
                                
                                success = await register.register(email, password, get_verification_code_inner)
                                if not success:
                                    raise Exception("注册失败")
                                
                                await register._handle_sora_onboarding(email)
                                
                                # 复用手机号，请求重新发送短信
                                # 最后一个账号（第3个）才设置为完成状态
                                is_last_account = (i + 1) == remaining
                                phone_result = await register._handle_phone_verification(
                                    email,
                                    shared_sms_service,  # 复用第一个账号的 SMS 服务
                                    reuse_phone=True,  # 复用已有手机号
                                    set_complete=is_last_account  # 只有最后一个账号设置为完成状态
                                )
                                
                                access_token = phone_result.get("accessToken")
                                session_token = phone_result.get("sessionToken")
                                
                                if not access_token:
                                    raise Exception("无法获取 accessToken")
                                
                                # 保存到数据库（使用 token_manager.add_token）
                                try:
                                    token_obj = await self.token_manager.add_token(
                                        token_value=access_token,
                                        st=session_token,
                                        rt=None,
                                        client_id=None,
                                        proxy_url=final_proxy,
                                        remark=f"自动注册 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                                        update_if_exists=False,
                                        image_enabled=True,
                                        video_enabled=True,
                                        image_concurrency=-1,
                                        video_concurrency=3,
                                        skip_status_update=False,
                                        email=email
                                    )
                                    logger.info(f"第 {i+2} 个账号已保存，Token ID: {token_obj.id}")
                                except ValueError as e:
                                    # 如果账号已存在，尝试更新
                                    if "已存在" in str(e):
                                        logger.warn(f"账号已存在，尝试更新: {email}")
                                        existing_token = await self.db.get_token_by_email(email)
                                        if existing_token:
                                            await self.token_manager.update_token(
                                                token_id=existing_token.id,
                                                token=access_token,
                                                st=session_token,
                                                proxy_url=final_proxy,
                                                remark=f"自动注册更新 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                                            )
                                            token_obj = await self.db.get_token(existing_token.id)
                                        else:
                                            raise
                                    else:
                                        raise
                                
                                accounts.append({
                                    "email": token_obj.email,
                                    "session_token": token_obj.st,
                                    "access_token": token_obj.token,
                                    "refresh_token": token_obj.rt,
                                    "client_id": token_obj.client_id,
                                    "proxy_url": token_obj.proxy_url,
                                    "remark": token_obj.remark,
                                    "is_active": token_obj.is_active,
                                    "image_enabled": token_obj.image_enabled,
                                    "video_enabled": token_obj.video_enabled,
                                    "image_concurrency": token_obj.image_concurrency,
                                    "video_concurrency": token_obj.video_concurrency,
                                })
                                
                                logger.info(f"第 {i+2} 个账号注册成功（复用手机号: {shared_sms_service.get_phone_number()}）")
                            except Exception as e:
                                logger.error(f"注册第 {i+2} 个账号失败: {e}")
                                # 如果失败，确保关闭 SMS 服务
                                if shared_sms_service:
                                    try:
                                        await shared_sms_service.close()
                                    except:
                                        pass
                                break
                        
                        # 如果所有账号都注册成功，关闭共享的 SMS 服务
                        if len(accounts) == 3 and shared_sms_service:
                            try:
                                await shared_sms_service.close()
                            except:
                                pass
                            shared_sms_service = None
                        
                        # 如果注册失败（账号数不足3个），也需要关闭 SMS 服务
                        if len(accounts) < 3 and shared_sms_service:
                            try:
                                await shared_sms_service.close()
                            except:
                                pass
                            shared_sms_service = None
                    
                    result_accounts = accounts[-3:] if len(accounts) >= 3 else accounts
                
                return {
                    "success": True,
                    "accounts": result_accounts,
                    "count": len(result_accounts)
                }
                
        except Exception as e:
            logger.error(f"注册失败: {e}")
            # 如果失败，确保关闭所有资源
            try:
                if register:
                    await register.close()
            except:
                pass
            try:
                if browser:
                    await browser.close()
            except:
                pass
            try:
                if temp_mail:
                    await temp_mail.close()
            except:
                pass
            try:
                if sms_service:
                    await sms_service.close()
            except:
                pass
            raise
        finally:
            # 清理资源（在"1绑3"模式下，SMS 服务可能已经在循环中被关闭）
            try:
                if register:
                    await register.close()
            except:
                pass
            try:
                if browser:
                    await browser.close()
            except:
                pass
            try:
                if temp_mail:
                    await temp_mail.close()
            except:
                pass
            try:
                # 注意：在"1绑3"模式下，sms_service 可能已经在循环中被关闭
                # 这里只关闭如果还存在的话
                if sms_service and hasattr(sms_service, 'activation_id') and sms_service.activation_id:
                    await sms_service.close()
            except:
                pass
