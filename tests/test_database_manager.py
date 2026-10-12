from database.database_manager import DatabaseManager


def main():

    database = DatabaseManager()

    database.insert_application(
        name="chrome",
        exe_name="chrome.exe",
        full_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    )

    application = database.get_application(
        "chrome"
    )

    print(application)

    database.close()


if __name__ == "__main__":
    main()