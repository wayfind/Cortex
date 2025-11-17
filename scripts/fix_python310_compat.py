#!/usr/bin/env python3
"""
修复 Python 3.10 兼容性问题

主要修复：
1. datetime.timezone.utc (Python 3.11+) → timezone.utc (Python 3.10+)
2. datetime.now(timezone.utc) (已弃用) → datetime.now(timezone.utc)
"""

import re
import sys
from pathlib import Path


def fix_file(file_path: Path) -> tuple[bool, int]:
    """
    修复单个文件的兼容性问题

    Returns:
        (是否修改, 修改次数)
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        changes = 0

        # 1. 修复 import 语句: datetime.timezone.utc → timezone.utc
        # from datetime import datetime, timedelta, timezone
        # → from datetime import datetime, timedelta, timezone
        if re.search(r'from datetime import.*\bUTC\b', content):
            content = re.sub(
                r'from datetime import (.*?)\bUTC\b',
                r'from datetime import \1timezone',
                content
            )
            changes += 1

        # 2. 修复 timezone.utc 使用: timezone.utc → timezone.utc
        # datetime.now(timezone.utc) → datetime.now(timezone.utc)
        content = re.sub(r'\b(?<!timezone\.)timezone.utc\b', r'timezone.utc', content)

        # 3. 修复 datetime.now(timezone.utc) → datetime.now(timezone.utc)
        old_utcnow_count = content.count('datetime.now(timezone.utc)')
        content = content.replace('datetime.now(timezone.utc)', 'datetime.now(timezone.utc)')
        changes += old_utcnow_count

        # 4. 确保导入了 timezone
        if 'timezone.utc' in content and 'from datetime import' in content:
            # 检查是否已经导入 timezone
            if not re.search(r'from datetime import.*\btimezone\b', content):
                # 找到第一个 from datetime import 并添加 timezone
                content = re.sub(
                    r'(from datetime import [^)\n]+)',
                    lambda m: m.group(1) + ', timezone' if '(' not in m.group(1) else m.group(1),
                    content,
                    count=1
                )
                changes += 1

        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            return True, changes

        return False, 0

    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}", file=sys.stderr)
        return False, 0


def main():
    """主函数"""
    repo_root = Path(__file__).parent.parent

    # 需要扫描的目录
    scan_dirs = [
        repo_root / 'cortex',
        repo_root / 'tests',
        repo_root / 'scripts',
    ]

    print("🔍 扫描 Python 文件...")
    python_files = []
    for scan_dir in scan_dirs:
        if scan_dir.exists():
            python_files.extend(scan_dir.rglob('*.py'))

    print(f"📝 找到 {len(python_files)} 个 Python 文件")

    # 修复文件
    modified_files = []
    total_changes = 0

    for file_path in python_files:
        modified, changes = fix_file(file_path)
        if modified:
            modified_files.append(file_path)
            total_changes += changes
            rel_path = file_path.relative_to(repo_root)
            print(f"✅ 修复: {rel_path} ({changes} 处)")

    # 输出总结
    print("\n" + "="*60)
    print(f"🎉 完成！")
    print(f"   修改文件数: {len(modified_files)}")
    print(f"   总修改数: {total_changes}")

    if modified_files:
        print("\n修改的文件：")
        for file_path in modified_files:
            rel_path = file_path.relative_to(repo_root)
            print(f"   - {rel_path}")

    return 0 if total_changes > 0 else 1


if __name__ == '__main__':
    sys.exit(main())
