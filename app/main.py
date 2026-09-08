from app.config.settings import settings


def main() -> None:
    print("wiki-embeddings app starting")
    print(f"Environment: {settings.app_env}")
    print(f"Database URL: {settings.database_url}")
    print(f"Qdrant URL: {settings.qdrant_url}")


if __name__ == "__main__":
    main()
