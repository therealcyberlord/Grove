from clients.database import init_db
from clients.storage import ensure_bucket


def main():
    init_db()
    ensure_bucket()
    print("Hello from backend!")


if __name__ == "__main__":
    main()
