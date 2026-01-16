FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（Playwright 需要）
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright 浏览器（Chromium 和 Chrome）
RUN playwright install chromium
RUN playwright install chrome
RUN playwright install-deps chromium
RUN playwright install-deps chrome

COPY . .

EXPOSE 8000

CMD ["python", "main.py"]
