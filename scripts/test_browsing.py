from InquirerPy import inquirer

def browse_files():
    directory = inquirer.filepath(
        message="Select a file to open:",
        only_files=True,
        base_directory="."
    ).execute()

    print(f"File chosen: {directory}")

# Call the file browsing function within your project flow
def main():
    # Other initialization code for your UV project
    browse_files()
    # Continue with the rest of your project logic

if __name__ == "__main__":
    main()
