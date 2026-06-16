from pathlib import Path

from app.config import SUPPORTED_TABLE_EXTENSIONS


def scan_data_directory(data_dir: str | Path) -> list[dict]:
    """
    Ищет таблицы в папке data.
    Пока поддерживаем только .csv и .xlsx.
    """

    data_dir = Path(data_dir)

    if not data_dir.exists():
        raise FileNotFoundError(f"Папка не найдена: {data_dir}")

    files = []

    for path in sorted(data_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in SUPPORTED_TABLE_EXTENSIONS:
            files.append(
                {
                    "file_name": path.name,
                    "path": str(path),
                    "extension": path.suffix.lower(),
                    "size_mb": round(path.stat().st_size / 1024 / 1024, 3),
                }
            )

    return files
