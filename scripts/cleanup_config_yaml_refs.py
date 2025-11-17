#!/usr/bin/env python3
"""
清理文档中的 config.yaml 引用

将文档中的 config.yaml 引用替换为 .env 或标记为已弃用
"""

import re
from pathlib import Path

# 需要清理的文档列表（排除 CONFIGURATION_UPDATE 文档，因为它讨论迁移）
DOCS_TO_CLEAN = [
    "docs/INSTALLATION.md",
    "docs/probe_validation.md",
    "docs/TROUBLESHOOTING.md",
    "docs/ARCHITECTURE_UPDATE.md",
    "docs/architecture.md",
    "docs/probe_workflow.md",
    "docs/LOGGING_CONFIGURATION.md",
    "docs/INTEGRATION_VALIDATION_REPORT.md",
    "docs/INTENT_ENGINE_EXPLAINED.md",
    "docs/ROADMAP_v1.1.0.md",
]

# 替换规则
REPLACEMENTS = [
    # 简单的命令行参数引用
    (r'--config config\.yaml', '--config .env'),
    (r'cortex-probe --config config\.yaml', 'cortex-probe'),

    # 配置文件引用
    (r'`config\.yaml`', '`.env`'),
    (r'config\.example\.yaml', '.env.example'),

    # 编辑配置文件的说明
    (r'编辑.*?`?config\.yaml`?', '编辑 `.env`'),
    (r'修改.*?`?config\.yaml`?', '修改 `.env`'),
    (r'配置.*?`?config\.yaml`?', '配置 `.env`'),

    # 文件路径引用
    (r'\.\/config\.yaml', './.env'),
    (r'config\.yaml 文件', '.env 文件'),
]

def clean_file(file_path: Path) -> tuple[bool, int]:
    """
    清理单个文件中的 config.yaml 引用

    Returns:
        (是否修改, 替换次数)
    """
    if not file_path.exists():
        return False, 0

    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        changes = 0

        for pattern, replacement in REPLACEMENTS:
            matches = len(re.findall(pattern, content, re.IGNORECASE))
            if matches > 0:
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
                changes += matches

        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            return True, changes

        return False, 0

    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        return False, 0


def main():
    """主函数"""
    repo_root = Path(__file__).parent.parent

    print("🔍 清理文档中的 config.yaml 引用...")

    modified_files = []
    total_changes = 0

    for doc_path in DOCS_TO_CLEAN:
        file_path = repo_root / doc_path
        modified, changes = clean_file(file_path)

        if modified:
            modified_files.append(file_path)
            total_changes += changes
            rel_path = file_path.relative_to(repo_root)
            print(f"✅ 清理: {rel_path} ({changes} 处)")
        else:
            rel_path = file_path.relative_to(repo_root)
            if file_path.exists():
                # 检查是否还有残留引用
                content = file_path.read_text(encoding='utf-8')
                remaining = len(re.findall(r'config\.yaml|config\.example\.yaml', content, re.IGNORECASE))
                if remaining > 0:
                    print(f"⚠️  {rel_path} 还有 {remaining} 处需要手动检查")

    # 输出总结
    print("\n" + "="*60)
    print(f"🎉 完成！")
    print(f"   修改文件数: {len(modified_files)}")
    print(f"   总替换数: {total_changes}")

    if modified_files:
        print("\n修改的文件：")
        for file_path in modified_files:
            rel_path = file_path.relative_to(repo_root)
            print(f"   - {rel_path}")

    return 0 if len(modified_files) > 0 else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
