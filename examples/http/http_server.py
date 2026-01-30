#!/usr/bin/env python3
"""
FastAPI HTTP 服务框架
功能：提供当前时间获取API
使用 FastAPI + Uvicorn 实现
"""

from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone
import pytz
import uvicorn
from typing import Optional, List
import logging
from pathlib import Path as FilePath

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用实例
app = FastAPI(
    title="时间服务API",
    description="提供各种时间相关功能的HTTP服务",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI 文档地址
    redoc_url="/redoc"  # ReDoc 文档地址
)

# 添加CORS中间件，允许跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据模型定义
class TimeResponse(BaseModel):
    """时间响应模型"""
    current_time: str
    timezone: str
    timestamp: float
    formatted_time: str
    iso_format: str

class TimezoneInfo(BaseModel):
    """时区信息模型"""
    timezone: str
    current_time: str
    offset: str

class HealthCheck(BaseModel):
    """健康检查响应模型"""
    status: str
    timestamp: str
    version: str

# 工具函数
def get_current_time_info(tz_name: str = "UTC") -> dict:
    """
    获取指定时区的当前时间信息
    
    Args:
        tz_name: 时区名称，默认UTC
        
    Returns:
        包含时间信息的字典
    """
    try:
        if tz_name.upper() == "UTC":
            tz = timezone.utc
            current_time = datetime.now(tz)
        else:
            tz = pytz.timezone(tz_name)
            current_time = datetime.now(tz)
        
        return {
            "current_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "timezone": str(tz),
            "timestamp": current_time.timestamp(),
            "formatted_time": current_time.strftime("%A, %B %d, %Y at %I:%M:%S %p"),
            "iso_format": current_time.isoformat()
        }
    except Exception as e:
        logger.error(f"获取时间信息失败: {e}")
        raise HTTPException(status_code=400, detail=f"无效的时区: {tz_name}")

# API 路由定义

@app.get("/", response_class=HTMLResponse)
async def root():
    """根路径 - 返回服务介绍页面"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>时间服务API</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .endpoint { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #007bff; }
            .method { font-weight: bold; color: #007bff; }
            h1 { color: #333; text-align: center; }
            h2 { color: #666; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🕐 时间服务API</h1>
            <p>欢迎使用时间服务API！这个服务提供各种时间相关的功能。</p>
            
            <h2>📚 可用的API端点：</h2>
            
            <div class="endpoint">
                <span class="method">GET</span> <strong>/time</strong> - 获取当前UTC时间
            </div>
            
            <div class="endpoint">
                <span class="method">GET</span> <strong>/time/local</strong> - 获取本地时间
            </div>
            
            <div class="endpoint">
                <span class="method">GET</span> <strong>/time/timezone/{timezone}</strong> - 获取指定时区时间
            </div>
            
            <div class="endpoint">
                <span class="method">GET</span> <strong>/timezones</strong> - 获取支持的时区列表
            </div>
            
            <div class="endpoint">
                <span class="method">GET</span> <strong>/health</strong> - 健康检查
            </div>
            
            <p><a href="/docs" target="_blank">📖 查看完整API文档 (Swagger UI)</a></p>
            <p><a href="/redoc" target="_blank">📋 查看ReDoc文档</a></p>
        </div>
    </body>
    </html>
    """
    return html_content

@app.get("/time", response_model=TimeResponse, summary="获取当前UTC时间")
async def get_current_time():
    """
    获取当前UTC时间
    
    返回当前UTC时间的详细信息，包括：
    - 格式化时间字符串
    - 时区信息
    - 时间戳
    - ISO格式时间
    """
    try:
        time_info = get_current_time_info("UTC")
        logger.info("获取UTC时间成功")
        return TimeResponse(**time_info)
    except Exception as e:
        logger.error(f"获取UTC时间失败: {e}")
        raise HTTPException(status_code=500, detail="获取时间失败")

@app.get("/time/local", response_model=TimeResponse, summary="获取本地时间")
async def get_local_time():
    """
    获取服务器本地时间
    
    返回服务器所在时区的当前时间信息
    """
    try:
        local_tz = datetime.now().astimezone().tzinfo
        current_time = datetime.now(local_tz)
        
        time_info = {
            "current_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "timezone": str(local_tz),
            "timestamp": current_time.timestamp(),
            "formatted_time": current_time.strftime("%A, %B %d, %Y at %I:%M:%S %p"),
            "iso_format": current_time.isoformat()
        }
        
        logger.info("获取本地时间成功")
        return TimeResponse(**time_info)
    except Exception as e:
        logger.error(f"获取本地时间失败: {e}")
        raise HTTPException(status_code=500, detail="获取本地时间失败")

@app.get("/time/timezone/{timezone_name}", response_model=TimeResponse, summary="获取指定时区时间")
async def get_timezone_time(
    timezone_name: str = Path(..., description="时区名称，如：Asia/Shanghai, America/New_York")
):
    """
    获取指定时区的当前时间
    
    参数:
    - timezone_name: 时区名称，例如 Asia/Shanghai, America/New_York, Europe/London
    
    常用时区：
    - Asia/Shanghai (中国)
    - America/New_York (美国东部)
    - Europe/London (英国)
    - Asia/Tokyo (日本)
    """
    try:
        time_info = get_current_time_info(timezone_name)
        logger.info(f"获取时区 {timezone_name} 时间成功")
        return TimeResponse(**time_info)
    except Exception as e:
        logger.error(f"获取时区 {timezone_name} 时间失败: {e}")
        raise HTTPException(status_code=400, detail=f"无效的时区名称: {timezone_name}")

@app.get("/time/format", response_model=dict, summary="获取自定义格式时间")
async def get_formatted_time(
    format_str: str = Query("%Y-%m-%d %H:%M:%S", description="时间格式字符串"),
    timezone_name: str = Query("UTC", description="时区名称")
):
    """
    获取自定义格式的时间
    
    参数:
    - format_str: Python datetime格式字符串，默认 "%Y-%m-%d %H:%M:%S"
    - timezone_name: 时区名称，默认 "UTC"
    
    常用格式示例：
    - %Y-%m-%d %H:%M:%S (2024-01-01 12:30:45)
    - %Y/%m/%d %I:%M:%S %p (2024/01/01 12:30:45 PM)
    - %A, %B %d, %Y (Monday, January 01, 2024)
    """
    try:
        if timezone_name.upper() == "UTC":
            tz = timezone.utc
            current_time = datetime.now(tz)
        else:
            tz = pytz.timezone(timezone_name)
            current_time = datetime.now(tz)
        
        formatted_time = current_time.strftime(format_str)
        
        result = {
            "formatted_time": formatted_time,
            "format_string": format_str,
            "timezone": timezone_name,
            "timestamp": current_time.timestamp()
        }
        
        logger.info(f"获取自定义格式时间成功: {format_str}")
        return result
        
    except ValueError as e:
        logger.error(f"时间格式错误: {e}")
        raise HTTPException(status_code=400, detail=f"无效的时间格式: {format_str}")
    except Exception as e:
        logger.error(f"获取自定义格式时间失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/timezones", response_model=List[str], summary="获取支持的时区列表")
async def get_supported_timezones(
    filter_region: Optional[str] = Query(None, description="过滤地区，如：Asia, America, Europe")
):
    """
    获取支持的时区列表
    
    参数:
    - filter_region: 可选的地区过滤器，如 "Asia", "America", "Europe"
    """
    try:
        all_timezones = list(pytz.all_timezones)
        
        if filter_region:
            filtered_timezones = [
                tz for tz in all_timezones 
                if tz.startswith(filter_region)
            ]
            logger.info(f"获取 {filter_region} 地区时区列表成功，共 {len(filtered_timezones)} 个")
            return sorted(filtered_timezones)
        
        logger.info(f"获取所有时区列表成功，共 {len(all_timezones)} 个")
        return sorted(all_timezones)
        
    except Exception as e:
        logger.error(f"获取时区列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取时区列表失败")

@app.get("/health", response_model=HealthCheck, summary="健康检查")
async def health_check():
    """
    服务健康检查
    
    返回服务状态和版本信息
    """
    try:
        current_time = datetime.now(timezone.utc)
        return HealthCheck(
            status="healthy",
            timestamp=current_time.isoformat(),
            version="1.0.0"
        )
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        raise HTTPException(status_code=500, detail="服务不健康")

# 错误处理
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """404错误处理"""
    return JSONResponse(
        status_code=404,
        content={"detail": f"API端点未找到: {request.url.path}"}
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """500错误处理"""
    logger.error(f"内部服务器错误: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "内部服务器错误"}
    )

# 应用启动和关闭事件
@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("🚀 时间服务API启动成功!")
    logger.info("📖 API文档地址: http://localhost:8000/docs")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("⏹️  时间服务API已关闭")

# 服务器配置
class ServerConfig:
    """服务器配置"""
    HOST = "0.0.0.0"  # 监听所有网络接口
    PORT = 8080       # 端口号
    RELOAD = True     # 开发模式自动重载
    LOG_LEVEL = "info"  # 日志级别

def run_server():
    """运行服务器"""
    logger.info("启动FastAPI服务器...")
    uvicorn.run(
        app,
        host=ServerConfig.HOST,
        port=ServerConfig.PORT,
        log_level=ServerConfig.LOG_LEVEL
    )

if __name__ == "__main__":
    run_server()
