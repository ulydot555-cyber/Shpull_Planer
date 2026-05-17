import argparse

from database import DB_PATH, init_database, reset_database


def main():
    parser = argparse.ArgumentParser(description="Создание или пересоздание SQLite-базы планера.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Удалить старые таблицы и заново добавить стартовые данные.",
    )
    parser.add_argument(
        "--with-demo",
        action="store_true",
        help="Add demo tasks to an empty database.",
    )
    args = parser.parse_args()

    if args.reset:
        reset_database(seed_demo=args.with_demo)
        print(f"База пересоздана: {DB_PATH}")
    else:
        init_database(seed_demo=args.with_demo)
        print(f"База готова: {DB_PATH}")


if __name__ == "__main__":
    main()
