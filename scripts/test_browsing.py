from pathlib import Path
from InquirerPy.prompts import FilePathPrompt

def browse_files() -> Path:
    """Browse and select a file from the current directory."""
    directory: str = FilePathPrompt(
        message="Select a file to open:",
        only_files=True,
        base_directory="."
    ).execute()

    return Path(directory)

def main() -> None:
    """Main entry point for the file browser."""
    # Other initialization code for your UV project
    chosen_file = browse_files()
    print(f"File chosen: {chosen_file}")
    # Continue with the rest of your project logic

if __name__ == "__main__":
    main()
