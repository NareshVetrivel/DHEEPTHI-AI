import win32com.client


def main():
    try:
        word = win32com.client.Dispatch("Word.Application")

        print("SUCCESS: Microsoft Word COM connection established.")
        print("Word Version:", word.Version)

        word.Quit()

    except Exception as e:
        print("FAILED: Could not connect to Microsoft Word.")
        print("ERROR:", e)


if __name__ == "__main__":
    main()