#!/usr/bin/env python
"""
数据库备份脚本

支持 SQLite 数据库的自动备份、压缩和旧备份清理
"""

import argparse
import gzip
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path


def backup_database(
    db_path: str,
    backup_dir: str = "backups",
    compress: bool = True,
    keep_days: int = 30,
) -> Path:
    """
    备份 SQLite 数据库

    Args:
        db_path: 数据库文件路径
        backup_dir: 备份目录
        compress: 是否压缩备份文件
        keep_days: 保留备份的天数

    Returns:
        备份文件路径
    """
    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    # 创建备份目录
    backup_path = Path(backup_dir)
    backup_path.mkdir(parents=True, exist_ok=True)

    # 生成备份文件名（带时间戳）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{db_file.stem}_backup_{timestamp}.db"

    if compress:
        backup_filename += ".gz"
        backup_file = backup_path / backup_filename

        # 压缩备份
        print(f"Creating compressed backup: {backup_file}")
        with open(db_file, "rb") as f_in:
            with gzip.open(backup_file, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
    else:
        backup_file = backup_path / backup_filename

        # 直接复制
        print(f"Creating backup: {backup_file}")
        shutil.copy2(db_file, backup_file)

    print(f"✓ Backup created successfully: {backup_file}")
    print(f"  Original size: {db_file.stat().st_size / 1024:.2f} KB")
    print(f"  Backup size: {backup_file.stat().st_size / 1024:.2f} KB")

    # 清理旧备份
    if keep_days > 0:
        cleanup_old_backups(backup_path, keep_days)

    return backup_file


def cleanup_old_backups(backup_dir: Path, keep_days: int):
    """
    清理超过指定天数的旧备份

    Args:
        backup_dir: 备份目录
        keep_days: 保留天数
    """
    cutoff_date = datetime.now() - timedelta(days=keep_days)

    deleted_count = 0
    total_size = 0

    for backup_file in backup_dir.glob("*_backup_*.db*"):
        # 检查文件修改时间
        if datetime.fromtimestamp(backup_file.stat().st_mtime) < cutoff_date:
            file_size = backup_file.stat().st_size
            backup_file.unlink()
            deleted_count += 1
            total_size += file_size
            print(f"  Deleted old backup: {backup_file.name}")

    if deleted_count > 0:
        print(
            f"✓ Cleaned up {deleted_count} old backups (total: {total_size / 1024:.2f} KB)"
        )
    else:
        print("  No old backups to clean up")


def restore_database(backup_path: str, target_path: str):
    """
    从备份恢复数据库

    Args:
        backup_path: 备份文件路径
        target_path: 目标数据库路径
    """
    backup_file = Path(backup_path)
    if not backup_file.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    target_file = Path(target_path)

    # 如果目标文件存在，先备份当前文件
    if target_file.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_backup = target_file.parent / f"{target_file.stem}_before_restore_{timestamp}.db"
        print(f"Backing up current database to: {temp_backup}")
        shutil.copy2(target_file, temp_backup)

    # 恢复备份
    print(f"Restoring from backup: {backup_file}")

    if backup_file.suffix == ".gz":
        # 解压缩
        with gzip.open(backup_file, "rb") as f_in:
            with open(target_file, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
    else:
        # 直接复制
        shutil.copy2(backup_file, target_file)

    print(f"✓ Database restored successfully to: {target_file}")


def list_backups(backup_dir: str = "backups"):
    """
    列出所有备份文件

    Args:
        backup_dir: 备份目录
    """
    backup_path = Path(backup_dir)

    if not backup_path.exists():
        print(f"Backup directory not found: {backup_dir}")
        return

    backups = sorted(
        backup_path.glob("*_backup_*.db*"), key=lambda x: x.stat().st_mtime
    )

    if not backups:
        print("No backups found")
        return

    print(f"\n📦 Backups in {backup_dir}:")
    print(f"{'File':<50} {'Size':<15} {'Date'}")
    print("-" * 85)

    for backup in backups:
        size_kb = backup.stat().st_size / 1024
        mtime = datetime.fromtimestamp(backup.stat().st_mtime)
        print(f"{backup.name:<50} {size_kb:>10.2f} KB   {mtime.strftime('%Y-%m-%d %H:%M:%S')}")

    print(f"\nTotal: {len(backups)} backups")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Cortex Database Backup Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backup database
  python scripts/backup_db.py backup cortex.db

  # Backup with custom backup directory
  python scripts/backup_db.py backup cortex.db --backup-dir /path/to/backups

  # Backup without compression
  python scripts/backup_db.py backup cortex.db --no-compress

  # Restore from backup
  python scripts/backup_db.py restore backups/cortex_backup_20240101_120000.db.gz cortex.db

  # List all backups
  python scripts/backup_db.py list
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Backup command
    backup_parser = subparsers.add_parser("backup", help="Backup database")
    backup_parser.add_argument("db_path", help="Path to database file")
    backup_parser.add_argument(
        "--backup-dir",
        default="backups",
        help="Backup directory (default: backups)",
    )
    backup_parser.add_argument(
        "--no-compress", action="store_true", help="Do not compress backup"
    )
    backup_parser.add_argument(
        "--keep-days",
        type=int,
        default=30,
        help="Keep backups for N days (default: 30)",
    )

    # Restore command
    restore_parser = subparsers.add_parser("restore", help="Restore database")
    restore_parser.add_argument("backup_path", help="Path to backup file")
    restore_parser.add_argument("target_path", help="Target database path")

    # List command
    list_parser = subparsers.add_parser("list", help="List all backups")
    list_parser.add_argument(
        "--backup-dir",
        default="backups",
        help="Backup directory (default: backups)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "backup":
            backup_database(
                db_path=args.db_path,
                backup_dir=args.backup_dir,
                compress=not args.no_compress,
                keep_days=args.keep_days,
            )
        elif args.command == "restore":
            restore_database(args.backup_path, args.target_path)
        elif args.command == "list":
            list_backups(args.backup_dir)

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
