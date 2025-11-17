#!/usr/bin/env python
"""
环境配置初始化脚本

快速设置 Cortex 环境变量：
1. 从 .env.example 复制到 .env
2. 生成安全的随机密钥
3. 提示用户配置必要的值
"""

import os
import secrets
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


def generate_secret_key(length: int = 64) -> str:
    """生成安全的随机密钥"""
    return secrets.token_urlsafe(length)


def generate_registration_token() -> str:
    """生成注册令牌"""
    return secrets.token_urlsafe(32)


def setup_env():
    """设置环境变量文件"""
    env_example = PROJECT_ROOT / ".env.example"
    env_file = PROJECT_ROOT / ".env"

    # 检查 .env.example 是否存在
    if not env_example.exists():
        print(f"❌ 错误: {env_example} 不存在")
        return False

    # 检查 .env 是否已存在
    if env_file.exists():
        response = input(f"⚠️  {env_file} 已存在。是否覆盖？(y/N): ")
        if response.lower() != 'y':
            print("✓ 保留现有 .env 文件")
            return True

    print("📝 正在创建 .env 文件...")

    # 读取 .env.example
    with open(env_example, 'r', encoding='utf-8') as f:
        content = f.read()

    # 生成安全密钥
    secret_key = generate_secret_key()
    registration_token = generate_registration_token()

    # 替换默认值
    content = content.replace(
        'your-secret-key-change-in-production-min-32-chars',
        secret_key
    )
    content = content.replace(
        'your-registration-token-change-me',
        registration_token
    )

    # 写入 .env
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✓ 已创建 {env_file}")
    print(f"✓ 已生成安全密钥（{len(secret_key)} 字符）")
    print(f"✓ 已生成注册令牌（{len(registration_token)} 字符）")

    return True


def print_next_steps():
    """打印后续步骤"""
    print("\n" + "="*60)
    print("📋 后续步骤:")
    print("="*60)
    print()
    print("1. 编辑 .env 文件，配置以下必需项:")
    print("   - ANTHROPIC_API_KEY: 你的 Claude API Key")
    print("   - CORTEX_AGENT_ID: 节点唯一标识")
    print("   - CORTEX_AGENT_NAME: 节点名称")
    print()
    print("2. （可选）如果需要 Telegram 通知，配置:")
    print("   - TELEGRAM_ENABLED=true")
    print("   - TELEGRAM_BOT_TOKEN")
    print("   - TELEGRAM_CHAT_ID")
    print()
    print("3. 初始化数据库和认证系统:")
    print("   python scripts/init_auth.py")
    print()
    print("4. 启动服务:")
    print("   # Monitor (端口 8000)")
    print("   python -m uvicorn cortex.monitor.app:app --host 0.0.0.0 --port 8000")
    print()
    print("   # Probe (端口 8001)")
    print("   python -m uvicorn cortex.probe.app:app --host 0.0.0.0 --port 8001")
    print()
    print("="*60)
    print("⚠️  安全提醒:")
    print("="*60)
    print("- .env 文件包含敏感信息，已被 git 忽略")
    print("- 不要将 .env 文件提交到版本控制")
    print("- 在生产环境部署前，请务必修改所有默认密码和密钥")
    print("="*60)


def main():
    """主函数"""
    print("="*60)
    print("🚀 Cortex 环境配置初始化")
    print("="*60)
    print()

    try:
        if setup_env():
            print_next_steps()
            return 0
        else:
            return 1
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
