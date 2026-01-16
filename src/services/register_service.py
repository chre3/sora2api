"""OpenAI/Sora 注册服务 - 使用 Playwright 进行浏览器自动化"""
import asyncio
import random
import string
import logging
import json
from pathlib import Path
from typing import Optional, Dict, Callable
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from .tempmail_service import TempMailService
from .sms_service import GrizzlySMSService

logger = logging.getLogger(__name__)

class OpenAIRegister:
    """OpenAI/Sora 注册服务"""
    
    def __init__(self, browser: Browser, screenshot_dir: str = ".", proxy_url: Optional[str] = None):
        """
        初始化注册服务
        
        Args:
            browser: Playwright Browser 实例
            screenshot_dir: 截图保存目录
            proxy_url: 代理 URL（可选）
        """
        self.browser = browser
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(exist_ok=True)
        self.proxy_url = proxy_url
        self.names = self._load_names()
    
    def _load_names(self) -> list:
        """加载名字列表"""
        try:
            name_file = Path("name.txt")
            if name_file.exists():
                content = name_file.read_text(encoding='utf-8')
                names = [n.strip() for n in content.split('\n') if n.strip()]
                logger.info(f"已加载 {len(names)} 个名字")
                return names
        except Exception as e:
            logger.warn(f'无法加载 name.txt: {e}，将使用默认名字')
        return ['John', 'Jane', 'Alex', 'Sam', 'Chris']
    
    def _get_screenshot_path(self, filename: str) -> str:
        """获取截图路径"""
        return str(self.screenshot_dir / filename)
    
    def _get_random_full_name(self) -> str:
        """获取随机全名 (2个随机字母 + name.txt中的名字)"""
        letters = string.ascii_lowercase
        prefix = random.choice(letters) + random.choice(letters)
        name = random.choice(self.names)
        return f"{prefix.capitalize()}{name.capitalize()}"
    
    def _generate_birthday(self, is_chinese_page: bool = False) -> tuple:
        """生成随机生日 (18-40岁)"""
        current_year = 2025
        year = current_year - random.randint(18, 40)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        return (year, month, day)
    
    def _generate_password(self) -> str:
        """生成随机密码 (至少12位)"""
        upper = "ABCDEFGHJKLMNPQRSTUVWXYZ"
        lower = "abcdefghjkmnpqrstuvwxyz"
        digits = "23456789"
        specials = "!@#$%^&*"
        all_chars = upper + lower + digits
        
        password = (
            random.choice(upper) +
            random.choice(lower) +
            random.choice(digits) +
            random.choice(specials)
        )
        
        # 填充到14位
        for _ in range(10):
            password += random.choice(all_chars)
        
        # 打乱顺序
        password_list = list(password)
        random.shuffle(password_list)
        return ''.join(password_list)
    
    def _generate_sora_username(self) -> str:
        """生成随机用户名（用于 Sora onboarding）"""
        adjectives = ["cool", "smart", "fast", "bright", "quick", "sharp", "bold", "calm", "wise", "brave"]
        nouns = ["tiger", "eagle", "wolf", "lion", "hawk", "fox", "bear", "deer", "bird", "fish"]
        numbers = random.randint(0, 99999)
        adjective = random.choice(adjectives)
        noun = random.choice(nouns)
        return f"{adjective}{noun}{numbers}"
    
    async def _sleep(self, ms: int):
        """睡眠函数"""
        await asyncio.sleep(ms / 1000)
    
    async def _apply_fingerprint(self, page: Page):
        """应用随机指纹到页面"""
        resolutions = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1536, "height": 864},
            {"width": 1440, "height": 900},
            {"width": 1280, "height": 720},
            {"width": 2560, "height": 1440},
        ]
        
        webgl_vendors = [
            "Google Inc. (NVIDIA)",
            "Google Inc. (Intel)",
            "Google Inc. (AMD)",
        ]
        webgl_renderers = [
            "ANGLE (NVIDIA GeForce GTX 1060 Direct3D11 vs_5_0 ps_5_0)",
            "ANGLE (NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0)",
            "ANGLE (Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0)",
            "ANGLE (AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0)",
        ]
        
        fingerprint = {
            "resolution": random.choice(resolutions),
            "webglVendor": random.choice(webgl_vendors),
            "webglRenderer": random.choice(webgl_renderers),
            "hardwareConcurrency": random.choice([4, 6, 8, 12, 16]),
            "deviceMemory": random.choice([4, 8, 16, 32]),
        }
        
        # 注入指纹脚本
        await page.add_init_script(f"""
        (() => {{
            const fp = {json.dumps(fingerprint)};
            
            // 修改 hardwareConcurrency
            Object.defineProperty(navigator, "hardwareConcurrency", {{
                get: () => fp.hardwareConcurrency,
            }});
            
            // 修改 deviceMemory
            Object.defineProperty(navigator, "deviceMemory", {{
                get: () => fp.deviceMemory,
            }});
            
            // 修改 WebGL 指纹
            const getParameterProxyHandler = {{
                apply: function (target, thisArg, args) {{
                    const param = args[0];
                    // UNMASKED_VENDOR_WEBGL
                    if (param === 37445) return fp.webglVendor;
                    // UNMASKED_RENDERER_WEBGL
                    if (param === 37446) return fp.webglRenderer;
                    return Reflect.apply(target, thisArg, args);
                }},
            }};
            
            const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = new Proxy(
                originalGetParameter,
                getParameterProxyHandler
            );
            
            if (typeof WebGL2RenderingContext !== "undefined") {{
                const originalGetParameter2 = WebGL2RenderingContext.prototype.getParameter;
                WebGL2RenderingContext.prototype.getParameter = new Proxy(
                    originalGetParameter2,
                    getParameterProxyHandler
                );
            }}
            
            // 修改屏幕分辨率
            Object.defineProperty(screen, "width", {{
                get: () => fp.resolution.width,
            }});
            Object.defineProperty(screen, "height", {{
                get: () => fp.resolution.height,
            }});
            Object.defineProperty(screen, "availWidth", {{
                get: () => fp.resolution.width,
            }});
            Object.defineProperty(screen, "availHeight", {{
                get: () => fp.resolution.height - 40,
            }});
        }})();
        """)
    
    async def init(self):
        """初始化注册页面"""
        logger.info('=' * 80)
        logger.info('正在初始化注册服务...')
        logger.info(f'代理配置: {self.proxy_url if self.proxy_url else "无代理"}')
        
        # 创建浏览器上下文
        context_options = {
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "locale": "en-US",
        }
        
        if self.proxy_url:
            # 解析代理 URL
            if self.proxy_url.startswith("http://") or self.proxy_url.startswith("https://"):
                context_options["proxy"] = {"server": self.proxy_url}
            elif self.proxy_url.startswith("socks5://"):
                context_options["proxy"] = {"server": self.proxy_url}
            logger.info(f'使用代理: {self.proxy_url}')
        
        logger.info('正在创建浏览器上下文...')
        self.context = await self.browser.new_context(**context_options)
        logger.info('浏览器上下文创建完成')
        
        # 创建页面
        logger.info('正在创建新页面...')
        self.page = await self.context.new_page()
        logger.info('页面创建完成')
        
        # 应用指纹
        logger.info('正在应用浏览器指纹...')
        await self._apply_fingerprint(self.page)
        logger.info('浏览器指纹应用完成')
        
        # 设置超时
        self.page.set_default_timeout(45000)
        self.page.set_default_navigation_timeout(90000)
        logger.info('页面超时设置: 默认45000ms, 导航90000ms')
        
        # 启用请求拦截，阻止不必要的资源加载
        async def route_handler(route):
            resource_type = route.request.resource_type
            url = route.request.url.lower()
            
            # 阻止媒体资源
            if resource_type == "media":
                await route.abort()
                return
            
            # 阻止分析/追踪
            blocked_patterns = [
                'google-analytics.com',
                'googletagmanager.com',
                'facebook.com/tr',
                'doubleclick.net',
            ]
            
            if any(pattern in url for pattern in blocked_patterns):
                await route.abort()
                return
            
            await route.continue_()
        
        await self.page.route("**/*", route_handler)
        logger.info('请求拦截器已设置')
        
        # 访问登录页面
        login_url = 'https://chatgpt.com/auth/login?next=%2Fsora%2F'
        logger.info(f'正在访问登录页面: {login_url}')
        await self.page.goto(login_url, wait_until="networkidle", timeout=90000)
        
        # 等待页面加载
        logger.info('等待页面DOM加载...')
        await self.page.wait_for_load_state("domcontentloaded", timeout=45000)
        
        current_url = self.page.url
        logger.info(f'当前URL: {current_url}')
        logger.info('等待页面渲染完成...')
        await self._sleep(800)
        logger.info('ChatGPT 登录页面已打开')
        logger.info('=' * 80)
    
    async def _click_sign_up(self):
        """点击免费注册按钮"""
        current_url = self.page.url
        logger.info(f'正在点击免费注册按钮..., 当前URL: {current_url}')
        
        # 检查是否已经在注册页面
        email_input = await self.page.query_selector('input[type="email"], input[name="email"]')
        if email_input:
            logger.info('已经在注册页面，跳过点击注册按钮')
            return
        
        # 等待注册按钮出现
        try:
            logger.info('等待注册按钮出现 (timeout=15000ms)...')
            signup_btn = await self.page.wait_for_selector(
                'button[data-testid="signup-button"]',
                timeout=15000
            )
            if signup_btn:
                await signup_btn.click()
                logger.info('已点击免费注册按钮 (data-testid)')
            else:
                # 备用：通过文本查找
                logger.info('未找到 data-testid 按钮，尝试通过文本查找...')
                buttons = await self.page.query_selector_all('button, a')
                clicked = False
                for btn in buttons:
                    text = await btn.text_content()
                    if text and ('免费注册' in text or 'Sign up' in text or '注册' in text):
                        await btn.click()
                        logger.info(f'已点击免费注册按钮 (文本: {text.strip()})')
                        clicked = True
                        break
                if not clicked:
                    logger.warn('未找到注册按钮')
        except Exception as e:
            logger.error(f'点击注册按钮时出错: {e}')
            current_url = self.page.url
            logger.error(f'错误发生时的URL: {current_url}')
            raise
        
        # 等待跳转
        logger.info('等待页面跳转...')
        await self._sleep(2000)
        current_url = self.page.url
        logger.info(f'跳转后URL: {current_url}')
        
        # 等待邮箱输入框出现
        logger.info('等待邮箱输入框出现...')
        for i in range(10):
            email_input = await self.page.query_selector('input[type="email"], input[name="email"]')
            if email_input:
                logger.info(f'邮箱输入框已出现 (尝试 {i+1}/10)')
                break
            await self._sleep(1000)
        else:
            logger.warn('等待10秒后仍未找到邮箱输入框')
    
    async def _enter_email(self, email: str):
        """输入邮箱地址"""
        current_url = self.page.url
        logger.info(f'正在输入邮箱: {email}, 当前URL: {current_url}')
        
        # 先点击 "more options" 按钮（如果存在）
        try:
            logger.info('检查是否存在 "more options" 按钮...')
            more_options_xpath = '/html/body/div/div/div/div/div[1]/div/div/form/div[1]/div/button'
            more_options_btn = await self.page.query_selector(f'xpath={more_options_xpath}')
            if more_options_btn:
                is_visible = await more_options_btn.is_visible()
                if is_visible:
                    await more_options_btn.click()
                    logger.info('已点击 "more options" 按钮')
                    await self._sleep(1000)
                else:
                    logger.info('"more options" 按钮存在但不可见')
            else:
                logger.info('未找到 "more options" 按钮')
        except Exception as e:
            logger.warn(f'点击 "more options" 按钮失败: {e}')
        
        # 等待邮箱输入框
        logger.info('等待邮箱输入框出现 (timeout=20000ms)...')
        try:
            email_input = await self.page.wait_for_selector(
                'input[type="email"], input[name="email"], input[autocomplete="email"]',
                timeout=20000
            )
            
            if email_input:
                logger.info('邮箱输入框已找到')
                await email_input.click(click_count=3)
                await email_input.fill(email)
                await self._sleep(500)
                logger.info('邮箱已输入')
            else:
                raise Exception('找不到邮箱输入框')
        except Exception as e:
            current_url = self.page.url
            logger.error(f'输入邮箱失败: {e}, 当前URL: {current_url}')
            try:
                page_text = await self.page.evaluate("() => document.body.innerText || ''")
                logger.error(f'页面文本前500字符: {page_text[:500]}')
                await self.page.screenshot(path=self._get_screenshot_path('email-input-error.png'))
            except:
                pass
            raise
        
        await self._click_continue()
        await self._sleep(1500)
        current_url = self.page.url
        logger.info(f'邮箱输入完成，当前URL: {current_url}')
    
    async def _enter_password(self, password: str):
        """输入密码"""
        current_url = self.page.url
        logger.info(f'正在输入密码... 当前URL: {current_url}')
        
        try:
            # 等待密码输入框，添加详细日志
            logger.info('等待密码输入框出现 (timeout=20000ms)...')
            password_input = await self.page.wait_for_selector('input[type="password"]', timeout=20000)
            
            if password_input:
                logger.info('密码输入框已找到')
                await password_input.click()
                await password_input.fill(password)
                await self._sleep(500)
                logger.info('密码已输入')
                await self._click_continue()
                await self._sleep(1500)
            else:
                # 如果找不到，尝试截图并记录页面信息
                try:
                    page_text = await self.page.evaluate("() => document.body.innerText || ''")
                    logger.error(f'找不到密码输入框。页面文本前500字符: {page_text[:500]}')
                    await self.page.screenshot(path=self._get_screenshot_path('password-input-error.png'))
                except:
                    pass
                raise Exception('找不到密码输入框')
        except Exception as e:
            current_url = self.page.url
            logger.error(f'输入密码失败: {e}, 当前URL: {current_url}')
            try:
                await self.page.screenshot(path=self._get_screenshot_path('password-error.png'))
            except:
                pass
            raise
    
    async def _enter_verification_code(self, code: str):
        """输入验证码"""
        logger.info(f'正在输入验证码: {code}')
        
        await self.page.bring_to_front()
        await self._sleep(500)
        
        # 等待验证码输入框
        code_input = await self.page.wait_for_selector(
            'input:not([type="password"]):not([type="hidden"])',
            timeout=20000
        )
        
        if code_input:
            await code_input.click(click_count=3)
            await code_input.fill(code)
            await self._sleep(500)
            logger.info('验证码已输入')
            await self._click_continue()
            await self._sleep(2000)
        else:
            raise Exception('找不到验证码输入框')
    
    async def _enter_name_and_birthday(self):
        """输入全名和生日"""
        logger.info('正在输入全名和生日...')
        
        await self.page.wait_for_load_state("networkidle", timeout=10000)
        await self._sleep(1000)
        
        # 检测页面是否是中文
        body_text = await self.page.evaluate("() => document.body.innerText || ''")
        is_chinese_page = '确认' in body_text or '年龄' in body_text or '生日日期' in body_text
        
        full_name = self._get_random_full_name()
        year, month, day = self._generate_birthday(is_chinese_page)
        
        logger.info(f'使用名字: {full_name}, 生日: {month}/{day}/{year} ({'中文页面' if is_chinese_page else '英文页面'})')
        
        # 输入名字
        name_input = await self.page.query_selector('input[name="name"], input[autocomplete="name"]')
        if name_input:
            await name_input.click(click_count=3)
            await name_input.fill(full_name)
            logger.info('全名已输入')
        else:
            inputs = await self.page.query_selector_all('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"])')
            if inputs:
                await inputs[0].click(click_count=3)
                await inputs[0].fill(full_name)
                logger.info('全名已输入 (备用方案)')
        
        await self._sleep(500)
        
        # 处理日期输入
        # 检查是否有 React Aria DateField
        date_spinner = await self.page.query_selector('div[role="spinbutton"]')
        
        if date_spinner:
            logger.info('检测到 React Aria DateField 组件')
            if is_chinese_page:
                # 中文: 年、月、日
                year_spinner = await self.page.query_selector('div[role="spinbutton"][aria-label*="年"]')
                if year_spinner:
                    await year_spinner.click()
                    await self.page.keyboard.type(str(year), delay=50)
                
                month_spinner = await self.page.query_selector('div[role="spinbutton"][aria-label*="月"]')
                if month_spinner:
                    await month_spinner.click()
                    await self.page.keyboard.type(str(month), delay=50)
                
                day_spinner = await self.page.query_selector('div[role="spinbutton"][aria-label*="日"]')
                if day_spinner:
                    await day_spinner.click()
                    await self.page.keyboard.type(str(day), delay=50)
            else:
                # 英文: Month, Day, Year
                month_spinner = await self.page.query_selector('div[role="spinbutton"][aria-label*="month" i]')
                if month_spinner:
                    await month_spinner.click()
                    await self.page.keyboard.type(str(month), delay=50)
                
                day_spinner = await self.page.query_selector('div[role="spinbutton"][aria-label*="day" i]')
                if day_spinner:
                    await day_spinner.click()
                    await self.page.keyboard.type(str(day), delay=50)
                
                year_spinner = await self.page.query_selector('div[role="spinbutton"][aria-label*="year" i]')
                if year_spinner:
                    await year_spinner.click()
                    await self.page.keyboard.type(str(year), delay=50)
            
            logger.info('生日已输入 (React Aria DateField)')
        else:
            # 备用方案
            birthday_input = await self.page.query_selector('input[name*="birth"], input[type="date"]')
            if birthday_input:
                await birthday_input.click()
                month_str = str(month).zfill(2)
                day_str = str(day).zfill(2)
                await self.page.keyboard.type(f"{month_str}{day_str}{year}", delay=30)
                logger.info('生日已输入')
        
        await self._click_continue()
    
    async def _click_continue(self):
        """点击继续按钮"""
        logger.info('正在点击继续按钮...')
        
        try:
            # 查找包含 "继续" 或 "Continue" 的按钮
            buttons = await self.page.query_selector_all('button')
            clicked = False
            
            for btn in buttons:
                text = await btn.text_content()
                if text and text.strip().lower() in ['继续', 'continue', 'next', '下一步']:
                    await btn.click()
                    clicked = True
                    logger.info('已点击继续按钮')
                    break
            
            if not clicked:
                submit_btn = await self.page.query_selector('button[type="submit"]')
                if submit_btn:
                    await submit_btn.click()
                    logger.info('已点击提交按钮')
            
            await self._sleep(1000)
        except Exception as e:
            logger.warn(f'点击继续按钮时出错: {e}')
    
    async def _check_for_sign_in_issue(self) -> bool:
        """检测页面是否显示 "We ran into an issue" 错误"""
        try:
            body_text = await self.page.evaluate("() => document.body.innerText || ''")
            if 'We ran into an issue' in body_text or 'please take a break' in body_text or 'try again soon' in body_text:
                return True
            
            # 检查错误元素
            error_elements = await self.page.query_selector_all('[class*="error"], [class*="Error"], [role="alert"]')
            for el in error_elements:
                text = await el.text_content()
                if text and ('We ran into an issue' in text or 'try again' in text):
                    return True
            
            return False
        except:
            return False
    
    async def register(self, email: str, password: str, get_verification_code: Callable) -> bool:
        """
        完成注册流程
        
        Args:
            email: 邮箱地址
            password: 密码
            get_verification_code: 获取验证码的回调函数
            
        Returns:
            是否注册成功
        """
        logger.info('=' * 80)
        logger.info('开始注册流程')
        logger.info(f'邮箱: {email}')
        current_url = self.page.url
        logger.info(f'起始URL: {current_url}')
        logger.info('=' * 80)
        
        try:
            # 1. 点击免费注册按钮
            logger.info('步骤1: 点击免费注册按钮')
            await self._click_sign_up()
            current_url = self.page.url
            logger.info(f'步骤1完成，当前URL: {current_url}')
            
            # 2. 输入邮箱
            logger.info('步骤2: 输入邮箱')
            await self._enter_email(email)
            current_url = self.page.url
            logger.info(f'步骤2完成，当前URL: {current_url}')
            
            # 检查限流
            if await self._check_for_sign_in_issue():
                logger.error('检测到限流错误')
                raise Exception('We ran into an issue while signing you in, please take a break and try again soon.')
            
            # 3. 输入密码
            logger.info('步骤3: 输入密码')
            await self._enter_password(password)
            current_url = self.page.url
            logger.info(f'步骤3完成，当前URL: {current_url}')
            
            # 检查限流
            if await self._check_for_sign_in_issue():
                logger.error('检测到限流错误')
                raise Exception('We ran into an issue while signing you in, please take a break and try again soon.')
            
            # 4. 等待并输入验证码
            logger.info('步骤4: 等待并输入邮箱验证码')
            code = await get_verification_code()
            await self._enter_verification_code(code)
            current_url = self.page.url
            logger.info(f'步骤4完成，当前URL: {current_url}')
            
            # 检查限流
            if await self._check_for_sign_in_issue():
                logger.error('检测到限流错误')
                raise Exception('We ran into an issue while signing you in, please take a break and try again soon.')
            
            # 5. 输入全名和生日
            logger.info('步骤5: 输入全名和生日')
            await self._enter_name_and_birthday()
            current_url = self.page.url
            logger.info(f'步骤5完成，当前URL: {current_url}')
            
            # 检查限流
            await self._sleep(1500)
            if await self._check_for_sign_in_issue():
                logger.error('检测到限流错误')
                raise Exception('We ran into an issue while signing you in, please take a break and try again soon.')
            
            # 6. 等待页面跳转
            logger.info('步骤6: 等待页面跳转...')
            await self._sleep(4000)
            
            # 检查是否注册成功
            current_url = self.page.url
            logger.info(f'最终URL: {current_url}')
            
            if 'auth.openai.com' in current_url:
                # 检查是否有错误
                has_error = await self.page.evaluate("""
                    () => {
                        const errorElements = document.querySelectorAll('[class*="error"], [class*="Error"], [role="alert"]');
                        for (const el of errorElements) {
                            if (el.textContent.trim().length > 0) {
                                return el.textContent.trim();
                            }
                        }
                        return null;
                    }
                """)
                
                if has_error:
                    logger.error(f'注册失败，页面显示错误: {has_error}')
                    logger.error(f'当前URL: {current_url}')
                    return False
                
                logger.warn(f'注册可能未完成，当前仍在认证页面: {current_url}')
                return False
            
            # 成功跳转到 sora 或 chat 页面
            if 'sora.com' in current_url or 'chat.openai.com' in current_url or 'chatgpt.com' in current_url:
                logger.info('=' * 80)
                logger.info('注册成功！已跳转到主页面')
                logger.info(f'最终URL: {current_url}')
                logger.info('=' * 80)
                return True
            
            logger.warn(f'注册状态不确定，当前页面: {current_url}')
            return False
        except Exception as error:
            current_url = self.page.url if self.page else "页面已关闭"
            logger.error('=' * 80)
            logger.error(f'注册过程出错: {error}')
            logger.error(f'错误发生时的URL: {current_url}')
            logger.error('=' * 80)
            try:
                if self.page:
                    await self.page.screenshot(path=self._get_screenshot_path('debug-register-error.png'))
                    logger.info('已保存错误截图: debug-register-error.png')
            except Exception as e:
                logger.warn(f'保存截图失败: {e}')
            raise
    
    async def _handle_sora_onboarding(self, email: str):
        """处理 Sora onboarding 用户名设置流程"""
        logger.info('开始处理 Sora onboarding 流程...')
        
        try:
            # 1. 等待跳转到 onboarding 页面
            logger.info('等待跳转到 onboarding 页面...')
            try:
                await self.page.wait_for_function(
                    "() => window.location.href.includes('/onboarding')",
                    timeout=30000
                )
            except:
                current_url = self.page.url
                if '/onboarding' in current_url:
                    logger.info('已在 onboarding 页面')
                else:
                    logger.warn(f'未检测到 onboarding 页面，当前 URL: {current_url}')
            
            await self.page.wait_for_load_state("networkidle", timeout=10000)
            await self._sleep(2000)
            
            # 2. 等待用户名输入框出现
            logger.info('等待用户名输入框出现...')
            username_input = None
            for _ in range(30):
                try:
                    element = await self.page.query_selector('xpath=/html/body/div/div[2]/div/div/div/input')
                    if element:
                        is_visible = await element.is_visible()
                        if is_visible:
                            username_input = element
                            break
                except:
                    pass
                await self._sleep(1000)
            
            if not username_input:
                raise Exception('找不到用户名输入框')
            
            # 3. 生成随机用户名并输入
            username = self._generate_sora_username()
            logger.info(f'生成用户名: {username}')
            
            await username_input.click(click_count=3)
            await username_input.fill(username)
            await self._sleep(800)
            logger.info(f'用户名已输入: {username}')
            
            # 等待验证
            await self._sleep(1500)
            
            # 4. 等待按钮可点击
            logger.info('等待按钮可点击...')
            button = None
            for _ in range(30):
                try:
                    btn = await self.page.query_selector('xpath=/html/body/div/div[2]/button')
                    if btn:
                        is_visible = await btn.is_visible()
                        if is_visible:
                            is_disabled = await btn.get_attribute('disabled')
                            if not is_disabled:
                                button = btn
                                break
                except:
                    pass
                await self._sleep(1000)
            
            if not button:
                raise Exception('找不到提交按钮')
            
            # 5. 点击按钮
            logger.info('点击提交按钮...')
            await button.click()
            logger.info('已点击提交按钮')
            
            await self._sleep(2000)
            
            logger.info('Sora onboarding 流程完成')
            return True
        except Exception as error:
            logger.error(f'Sora onboarding 流程失败: {error}')
            try:
                await self.page.screenshot(path=self._get_screenshot_path('debug-onboarding-error.png'))
            except:
                pass
            raise
    
    async def _handle_phone_verification(
        self, 
        email: str, 
        sms_service: GrizzlySMSService,
        reuse_phone: bool = False,
        set_complete: bool = True
    ):
        """
        处理手机号验证流程
        
        Args:
            email: 邮箱地址
            sms_service: SMS 服务实例
            reuse_phone: 是否复用已有手机号（如果为 True，不会申请新号码，而是复用 sms_service 中已有的）
            set_complete: 是否设置为完成状态（状态6），在"1绑3"模式下，前两个账号设为 False
        """
        logger.info('等待10秒后开始手机号验证...')
        await self._sleep(10000)
        
        # 确保页面在 sora.chatgpt.com
        current_url = self.page.url
        logger.info(f'当前页面 URL: {current_url}')
        
        if 'sora.chatgpt.com' not in current_url:
            logger.warn('当前不在 sora.chatgpt.com 页面，等待跳转...')
            try:
                await self.page.wait_for_function(
                    "() => window.location.href.includes('sora.chatgpt.com')",
                    timeout=10000
                )
            except:
                pass
        
        await self.page.wait_for_load_state("networkidle", timeout=5000)
        
        # 1. 初始化 SMS 服务
        await sms_service.init()
        
        # 2. 申请手机号或复用已有手机号
        if reuse_phone:
            # 复用已有手机号
            phone_number = sms_service.get_phone_number()
            if not phone_number:
                raise Exception("复用手机号失败：SMS 服务中没有已激活的手机号")
            logger.info(f'复用已有手机号: {phone_number}')
            
            # 请求重新发送短信（状态3）
            logger.info('请求重新发送短信...')
            await sms_service.resend_sms()
            
            # 等待一下，让短信发送
            logger.info('等待短信发送...')
            await self._sleep(3000)  # 等待3秒
        else:
            # 申请新手机号
            logger.info('正在申请手机号...')
            try:
                number_info = await sms_service.getNumber()
            except Exception as error:
                if '最高价格设置过低' in str(error):
                    logger.warn('价格过低，尝试不设置最高价格限制...')
                    number_info = await sms_service.getNumber(max_price=None)
                else:
                    raise
            
            phone_number = number_info["phoneNumber"]
            logger.info(f'获取到手机号: {phone_number}')
            
            # 告知号码可用
            await sms_service.set_ready()
        
        # 格式化手机号（添加 + 号）
        formatted_phone = f"+{phone_number}"
        
        # 4. 获取 accessToken
        logger.info('正在获取 accessToken...')
        token_result = await self.get_session_token()
        if not token_result.get("sessionToken"):
            raise Exception("无法获取 Session Token")
        
        access_token_result = await self.session_to_access_token(token_result["sessionToken"])
        if not access_token_result.get("accessToken"):
            raise Exception("无法获取 Access Token")
        
        access_token = access_token_result["accessToken"]
        logger.info('已获取 accessToken')
        
        # 5. 发起 start 请求
        logger.info('在页面上下文中发起手机号验证请求...')
        start_response = await self.page.evaluate(f"""
            async (phone, token) => {{
                try {{
                    const deviceId = document.cookie
                        .split('; ')
                        .find(row => row.startsWith('oai-did='))
                        ?.split('=')[1] || 
                        localStorage.getItem('oai-did') ||
                        localStorage.getItem('oai-device-id') ||
                        'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {{
                            const r = (Math.random() * 16) | 0;
                            const v = c === 'x' ? r : (r & 0x3) | 0x8;
                            return v.toString(16);
                        }});
                    
                    const response = await fetch(
                        'https://sora.chatgpt.com/backend/project_y/phone_number/enroll/start',
                        {{
                            method: 'POST',
                            headers: {{
                                accept: '*/*',
                                'accept-language': 'en-US,en;q=0.9',
                                authorization: `Bearer ${{token}}`,
                                'cache-control': 'no-cache',
                                'content-type': 'application/json',
                                'oai-device-id': deviceId,
                                'oai-language': 'en-US',
                                pragma: 'no-cache',
                                priority: 'u=1, i',
                                'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
                                'sec-ch-ua-mobile': '?0',
                                'sec-ch-ua-platform': '"macOS"',
                                'sec-fetch-dest': 'empty',
                                'sec-fetch-mode': 'cors',
                                'sec-fetch-site': 'same-origin',
                            }},
                            referrer: 'https://sora.chatgpt.com/explore',
                            credentials: 'include',
                            body: JSON.stringify({{
                                phone_number: phone,
                                verification_expiry_window_ms: null,
                            }}),
                        }}
                    );
                    
                    const contentType = response.headers.get('content-type');
                    let data;
                    
                    if (contentType && contentType.includes('application/json')) {{
                        data = await response.json();
                    }} else {{
                        const text = await response.text();
                        return {{
                            ok: false,
                            status: response.status,
                            statusText: response.statusText,
                            contentType: contentType,
                            text: text.substring(0, 500),
                            error: `响应不是 JSON 格式，状态码: ${{response.status}}`,
                        }};
                    }}
                    
                    return {{
                        ok: response.ok,
                        status: response.status,
                        statusText: response.statusText,
                        data: data,
                    }};
                }} catch (error) {{
                    return {{
                        ok: false,
                        error: error.message,
                    }};
                }}
            }}
        """, formatted_phone, access_token)
        
        if not start_response.get("ok"):
            error_msg = start_response.get("error") or f"HTTP {start_response.get('status')} {start_response.get('statusText', '')}"
            logger.error(f'Start 请求失败详情: {error_msg}')
            raise Exception(f'Start 请求失败: {error_msg}')
        
        logger.info(f'Start 请求成功')
        logger.info(f'响应: {json.dumps(start_response.get("data"))}')
        
        # 6. 等待验证码
        logger.info('等待验证码（最多60秒）...')
        verification_code = None
        max_retries = 3
        retry_count = 0
        
        while not verification_code and retry_count < max_retries:
            try:
                verification_code = await sms_service.wait_for_verification_code(60000, 3000)
                logger.info(f'收到验证码: {verification_code}')
                break
            except Exception as error:
                if '超时' in str(error) or 'timeout' in str(error).lower():
                    retry_count += 1
                    logger.warn(f'等待验证码超时（60秒），尝试 {retry_count}/{max_retries}')
                    
                    if retry_count < max_retries:
                        # 取消当前号码
                        logger.info('取消当前号码...')
                        try:
                            await sms_service.cancel()
                        except:
                            pass
                        
                        # 重新申请号码
                        logger.info('重新申请手机号...')
                        try:
                            number_info = await sms_service.getNumber(max_price=None)
                            phone_number = number_info["phoneNumber"]
                            formatted_phone = f"+{phone_number}"
                            logger.info(f'获取到新手机号: {phone_number}')
                            
                            await sms_service.set_ready()
                            
                            # 刷新页面
                            await self.page.reload(wait_until="networkidle", timeout=30000)
                            await self._sleep(2000)
                            
                            # 重新发起 start 请求
                            start_response = await self.page.evaluate(f"""
                                async (phone, token) => {{
                                    const deviceId = document.cookie
                                        .split('; ')
                                        .find(row => row.startsWith('oai-did='))
                                        ?.split('=')[1] || 
                                        localStorage.getItem('oai-did') ||
                                        localStorage.getItem('oai-device-id') ||
                                        'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {{
                                            const r = (Math.random() * 16) | 0;
                                            const v = c === 'x' ? r : (r & 0x3) | 0x8;
                                            return v.toString(16);
                                        }});
                                    
                                    const response = await fetch(
                                        'https://sora.chatgpt.com/backend/project_y/phone_number/enroll/start',
                                        {{
                                            method: 'POST',
                                            headers: {{
                                                accept: '*/*',
                                                'accept-language': 'en-US,en;q=0.9',
                                                authorization: `Bearer ${{token}}`,
                                                'cache-control': 'no-cache',
                                                'content-type': 'application/json',
                                                'oai-device-id': deviceId,
                                                'oai-language': 'en-US',
                                                pragma: 'no-cache',
                                                priority: 'u=1, i',
                                                'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
                                                'sec-ch-ua-mobile': '?0',
                                                'sec-ch-ua-platform': '"macOS"',
                                                'sec-fetch-dest': 'empty',
                                                'sec-fetch-mode': 'cors',
                                                'sec-fetch-site': 'same-origin',
                                            }},
                                            referrer: 'https://sora.chatgpt.com/explore',
                                            credentials: 'include',
                                            body: JSON.stringify({{
                                                phone_number: phone,
                                                verification_expiry_window_ms: null,
                                            }}),
                                        }}
                                    );
                                    
                                    const contentType = response.headers.get('content-type');
                                    let data;
                                    
                                    if (contentType && contentType.includes('application/json')) {{
                                        data = await response.json();
                                    }} else {{
                                        const text = await response.text();
                                        return {{
                                            ok: false,
                                            status: response.status,
                                            statusText: response.statusText,
                                            error: `响应不是 JSON 格式，状态码: ${{response.status}}`,
                                        }};
                                    }}
                                    
                                    return {{
                                        ok: response.ok,
                                        status: response.status,
                                        statusText: response.statusText,
                                        data: data,
                                    }};
                                }}
                            """, formatted_phone, access_token)
                            
                            if not start_response.get("ok"):
                                raise Exception(f'重新发起 Start 请求失败')
                            
                            logger.info('重新发起 Start 请求成功')
                            continue
                        except Exception as e:
                            logger.error(f'重新申请号码失败: {e}')
                            raise
                    else:
                        raise Exception(f'等待验证码超时，已重试 {max_retries} 次')
                else:
                    raise
        
        if not verification_code:
            raise Exception("未能获取验证码")
        
        # 7. 发起 finish 请求
        logger.info('在页面上下文中提交验证码...')
        finish_response = await self.page.evaluate(f"""
            async (phone, code, token) => {{
                try {{
                    const deviceId = document.cookie
                        .split('; ')
                        .find(row => row.startsWith('oai-did='))
                        ?.split('=')[1] || 
                        localStorage.getItem('oai-did') ||
                        localStorage.getItem('oai-device-id') ||
                        'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {{
                            const r = (Math.random() * 16) | 0;
                            const v = c === 'x' ? r : (r & 0x3) | 0x8;
                            return v.toString(16);
                        }});
                    
                    const response = await fetch(
                        'https://sora.chatgpt.com/backend/project_y/phone_number/enroll/finish',
                        {{
                            method: 'POST',
                            headers: {{
                                accept: '*/*',
                                'accept-language': 'en-US,en;q=0.9',
                                authorization: `Bearer ${{token}}`,
                                'cache-control': 'no-cache',
                                'content-type': 'application/json',
                                'oai-device-id': deviceId,
                                'oai-language': 'en-US',
                                pragma: 'no-cache',
                                priority: 'u=1, i',
                                'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
                                'sec-ch-ua-mobile': '?0',
                                'sec-ch-ua-platform': '"macOS"',
                                'sec-fetch-dest': 'empty',
                                'sec-fetch-mode': 'cors',
                                'sec-fetch-site': 'same-origin',
                            }},
                            referrer: 'https://sora.chatgpt.com/explore',
                            credentials: 'include',
                            body: JSON.stringify({{
                                phone_number: phone,
                                verification_code: code,
                            }}),
                        }}
                    );
                    
                    const contentType = response.headers.get('content-type');
                    let data;
                    
                    if (contentType && contentType.includes('application/json')) {{
                        data = await response.json();
                    }} else {{
                        const text = await response.text();
                        return {{
                            ok: false,
                            status: response.status,
                            statusText: response.statusText,
                            error: `响应不是 JSON 格式，状态码: ${{response.status}}`,
                        }};
                    }}
                    
                    return {{
                        ok: response.ok,
                        status: response.status,
                        statusText: response.statusText,
                        data: data,
                    }};
                }} catch (error) {{
                    return {{
                        ok: false,
                        error: error.message,
                    }};
                }}
            }}
        """, formatted_phone, verification_code, access_token)
        
        if not finish_response.get("ok"):
            error_msg = finish_response.get("error") or f"HTTP {finish_response.get('status')} {finish_response.get('statusText', '')}"
            logger.error(f'Finish 请求失败详情: {error_msg}')
            raise Exception(f'Finish 请求失败: {error_msg}')
        
        logger.info(f'Finish 请求成功')
        logger.info(f'响应: {json.dumps(finish_response.get("data"))}')
        
        # 8. 完成接码（根据参数决定是否设置为完成状态）
        if set_complete:
            await sms_service.set_complete()
        else:
            logger.info('跳过设置完成状态，保留手机号以供后续使用')
        
        # 9. 监听 api/auth/session 请求并获取最新的 accessToken
        logger.info('设置监听器以捕获 api/auth/session 请求...')
        latest_access_token = None
        
        async def response_handler(response):
            nonlocal latest_access_token
            url = response.url
            if 'api/auth/session' in url:
                try:
                    logger.info(f'检测到 api/auth/session 请求: {url}, 状态: {response.status}')
                    if response.ok:
                        data = await response.json()
                        if data and data.get("accessToken"):
                            latest_access_token = data["accessToken"]
                            logger.info('从 api/auth/session 获取到最新的 accessToken')
                except Exception as e:
                    logger.warn(f'解析 api/auth/session 响应失败: {e}')
        
        self.page.on("response", response_handler)
        
        # 10. 刷新页面以触发 api/auth/session 请求
        logger.info('刷新页面以获取最新的 accessToken...')
        try:
            await self.page.reload(wait_until="networkidle", timeout=30000)
        except:
            logger.warn('页面刷新超时，继续执行...')
        
        # 等待 api/auth/session 请求完成（最多等待15秒）
        start_time = asyncio.get_event_loop().time()
        max_wait_time = 15
        
        while not latest_access_token and (asyncio.get_event_loop().time() - start_time) < max_wait_time:
            await self._sleep(500)
        
        # 移除监听器
        self.page.remove_listener("response", response_handler)
        
        # 11. 获取 Session Token
        logger.info('正在获取 Session Token (httpOnly cookie)...')
        await self._sleep(2000)
        
        session_token = None
        try:
            cookies = await self.context.cookies()
            session_cookie = next((c for c in cookies if c["name"] == "__Secure-next-auth.session-token"), None)
            
            if session_cookie:
                session_token = session_cookie["value"]
                logger.info('已成功获取 Session Token (httpOnly cookie)')
            else:
                logger.warn('未找到 __Secure-next-auth.session-token cookie')
        except Exception as error:
            logger.warn(f'获取 Session Token 失败: {error}')
        
        # 12. 返回结果
        if latest_access_token:
            logger.info('手机号验证完成，已获取最新的 accessToken')
            return {
                "accessToken": latest_access_token,
                "sessionToken": session_token
            }
        elif access_token:
            logger.warn('未能在15秒内获取到最新的 accessToken，使用当前 accessToken')
            return {
                "accessToken": access_token,
                "sessionToken": session_token
            }
        else:
            raise Exception("无法获取 accessToken，无法保存账号信息")
    
    async def get_session_token(self) -> Dict:
        """获取 Session Token"""
        logger.info('正在获取 Session Token...')
        
        try:
            cookies = await self.context.cookies()
            
            # 筛选出 OpenAI 相关的鉴权 Cookie
            auth_cookies = {}
            relevant_domains = ['.openai.com', '.sora.com', '.chatgpt.com', 'auth.openai.com']
            relevant_names = [
                '__Secure-next-auth.session-token',
                '__Host-next-auth.csrf-token',
                '__cf_bm',
                '_cfuvid',
                'cf_clearance',
                'oai-did',
            ]
            
            for cookie in cookies:
                is_relevant_domain = any(domain.replace('.', '') in cookie.get("domain", "") for domain in relevant_domains)
                
                if is_relevant_domain:
                    if cookie["name"] in relevant_names or 'session' in cookie["name"] or 'token' in cookie["name"]:
                        auth_cookies[cookie["name"]] = {
                            "value": cookie["value"],
                            "domain": cookie.get("domain"),
                            "path": cookie.get("path"),
                        }
            
            # 特别提取最重要的 session token
            session_cookie = next((c for c in cookies if c["name"] == "__Secure-next-auth.session-token"), None)
            
            if session_cookie:
                logger.info('成功获取 Session Token')
                logger.info(f'Session Token 域名: {session_cookie.get("domain")}')
            else:
                logger.warn('未找到 __Secure-next-auth.session-token')
            
            return {
                "sessionToken": session_cookie["value"] if session_cookie else None,
                "allAuthCookies": auth_cookies,
            }
        except Exception as error:
            logger.error(f'获取 Session Token 失败: {error}')
            return {
                "sessionToken": None,
                "allAuthCookies": {},
            }
    
    async def session_to_access_token(self, session_token: str) -> Dict:
        """将 Session Token 转换为 Access Token"""
        logger.info('正在将 Session Token 转换为 Access Token...')
        
        if not session_token:
            logger.error('Session Token 为空，无法转换')
            return {"accessToken": None, "user": None, "expires": None}
        
        try:
            # 使用页面上下文发起请求
            result = await self.page.evaluate(f"""
                async (st) => {{
                    try {{
                        const response = await fetch('https://sora.chatgpt.com/api/auth/session', {{
                            method: 'GET',
                            headers: {{
                                'Accept': 'application/json',
                                'Content-Type': 'application/json',
                                'Cookie': `__Secure-next-auth.session-token=${{st}}`,
                                'Origin': 'https://sora.chatgpt.com',
                                'Referer': 'https://sora.chatgpt.com/'
                            }},
                            credentials: 'include'
                        }});
                        
                        if (!response.ok) {{
                            return {{ error: `HTTP ${{response.status}}: ${{response.statusText}}` }};
                        }}
                        
                        const data = await response.json();
                        return data;
                    }} catch (e) {{
                        return {{ error: e.message }};
                    }}
                }}
            """, session_token)
            
            if result.get("error"):
                logger.warn(f'页面内请求失败: {result["error"]}')
                return {"accessToken": None, "user": None, "expires": None}
            
            if result.get("accessToken"):
                logger.info('成功获取 Access Token')
                logger.info(f'用户邮箱: {result.get("user", {}).get("email", "未知")}')
                return {
                    "accessToken": result["accessToken"],
                    "user": result.get("user"),
                    "expires": result.get("expires")
                }
            
            logger.warn('返回数据中没有 accessToken')
            return {"accessToken": None, "user": result.get("user"), "expires": None}
        except Exception as error:
            logger.error(f'转换 Access Token 失败: {error}')
            return {"accessToken": None, "user": None, "expires": None}
    
    def get_page(self) -> Optional[Page]:
        """获取当前页面"""
        return self.page
    
    async def close(self):
        """关闭页面"""
        try:
            if self.context:
                await self.context.close()
            self.context = None
            self.page = None
        except Exception as e:
            logger.warn(f'关闭页面失败: {e}')
