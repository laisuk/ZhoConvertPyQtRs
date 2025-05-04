import pyperclip

def set_clipboard_text(text):
    """Sets the given text to the clipboard (cross-platform)."""
    try:
        pyperclip.copy(text)
        return True
    except Exception as e:
        print(f"Error copying to clipboard: {e}")
        return False

def get_clipboard_text():
    """Gets text from the clipboard (cross-platform)."""
    try:
        text = pyperclip.paste()
        return text
    except Exception as e:
        print(f"Error pasting from clipboard: {e}")
        return ""

# Example usage (still works the same way):
if __name__ == "__main__":
    text_to_copy = "Hello from cross-platform clipboard!"  # Example text
    if set_clipboard_text(text_to_copy):
        print("Text copied to clipboard successfully.")

        retrieved_text = get_clipboard_text()
        if retrieved_text:
            print(f"Retrieved text from clipboard: {retrieved_text}")
        else:
            print("Failed to retrieve text from clipboard.")
    else:
        print("Failed to copy text to clipboard.")
