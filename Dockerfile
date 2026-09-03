FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目
COPY . .

# 创建数据目录
RUN mkdir -p /app/data /app/logs

# 暴露 API 端口
EXPOSE 8080

# 启动 API 服务（首次会自动初始化题库）
CMD ["python", "-m", "src.main", "--mode", "api", "--host", "0.0.0.0", "--port", "8080"]
