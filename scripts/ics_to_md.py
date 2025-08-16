#!/usr/bin/env python3
"""
Convert ICS calendar files to individual Markdown documents.
Each event in the ICS file(s) will be converted to a separate Markdown file.
"""

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional


class ICSEvent:
    """Represents a single calendar event from an ICS file."""

    def __init__(self):
        self.summary: Optional[str] = None
        self.description: Optional[str] = None
        self.location: Optional[str] = None
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.uid: Optional[str] = None
        self.created: Optional[datetime] = None
        self.last_modified: Optional[datetime] = None
        self.organizer: Optional[str] = None
        self.attendees: List[str] = []
        self.categories: List[str] = []
        self.status: Optional[str] = None
        self.priority: Optional[str] = None
        self.url: Optional[str] = None


class ICSParser:
    """Parser for ICS calendar files."""

    def __init__(self):
        self.events: List[ICSEvent] = []

    def parse_file(self, file_path: Path) -> List[ICSEvent]:
        """Parse an ICS file and return list of events."""
        self.events = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try with different encodings
            for encoding in ["latin-1", "cp1252"]:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError(f"Could not decode file {file_path}")

        # Unfold lines (ICS files can have line continuations)
        content = self._unfold_lines(content)

        # Split into lines and process
        lines = content.strip().split("\n")
        current_event = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line == "BEGIN:VEVENT":
                current_event = ICSEvent()
            elif line == "END:VEVENT":
                if current_event:
                    self.events.append(current_event)
                    current_event = None
            elif current_event and ":" in line:
                self._parse_event_line(current_event, line)

        return self.events

    def _unfold_lines(self, content: str) -> str:
        """Unfold ICS lines that are continued with leading whitespace."""
        lines = content.split("\n")
        unfolded_lines = []

        for line in lines:
            if line.startswith(" ") or line.startswith("\t"):
                # Continuation line
                if unfolded_lines:
                    unfolded_lines[-1] += line[1:]
            else:
                unfolded_lines.append(line)

        return "\n".join(unfolded_lines)

    def _parse_event_line(self, event: ICSEvent, line: str):
        """Parse a single line of event data."""
        # Split on first colon
        if ":" not in line:
            return

        prop_part, value = line.split(":", 1)

        # Handle parameters (e.g., DTSTART;TZID=America/New_York:20230101T120000)
        if ";" in prop_part:
            prop_name, params = prop_part.split(";", 1)
        else:
            prop_name = prop_part
            params = ""

        prop_name = prop_name.upper()

        # Parse different property types
        if prop_name == "SUMMARY":
            event.summary = self._decode_value(value)
        elif prop_name == "DESCRIPTION":
            event.description = self._decode_value(value)
        elif prop_name == "LOCATION":
            event.location = self._decode_value(value)
        elif prop_name == "DTSTART":
            event.start_time = self._parse_datetime(value, params)
        elif prop_name == "DTEND":
            event.end_time = self._parse_datetime(value, params)
        elif prop_name == "UID":
            event.uid = value
        elif prop_name == "CREATED":
            event.created = self._parse_datetime(value, params)
        elif prop_name == "LAST-MODIFIED":
            event.last_modified = self._parse_datetime(value, params)
        elif prop_name == "ORGANIZER":
            event.organizer = self._parse_person(value)
        elif prop_name == "ATTENDEE":
            event.attendees.append(self._parse_person(value))
        elif prop_name == "CATEGORIES":
            event.categories.extend([cat.strip() for cat in value.split(",")])
        elif prop_name == "STATUS":
            event.status = value
        elif prop_name == "PRIORITY":
            event.priority = value
        elif prop_name == "URL":
            event.url = value

    def _decode_value(self, value: str) -> str:
        """Decode ICS value, handling escape sequences."""
        # Unescape common ICS escape sequences
        value = value.replace("\\n", "\n")
        value = value.replace("\\,", ",")
        value = value.replace("\\;", ";")
        value = value.replace("\\\\", "\\")

        # Remove Google Meet boilerplate
        value = self._remove_google_meet_boilerplate(value)

        return value

    def _remove_google_meet_boilerplate(self, text: str) -> str:
        """Remove Google Meet boilerplate text from descriptions."""
        if not text:
            return text

        # Pattern to match Google Meet boilerplate sections
        # Matches the decorative lines and the content between them
        meet_pattern = r"-::~:~::~.*?-::~:~::~.*?-"
        text = re.sub(meet_pattern, "", text, flags=re.DOTALL)

        # Also remove standalone Google Meet links and related text
        meet_patterns = [
            r"Join with Google Meet: https://meet\.google\.com/[a-z0-9-]+",
            r"Learn more about Meet at: https://support\.google\.com/[^\n]*",
            r"Please do not edit this section\.",
            r"\n+─+\n+",  # Various dash/line separators
            r"\n+-+\n+",
        ]

        for pattern in meet_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # Clean up excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()

        return text

    def _parse_datetime(self, value: str, params: str) -> Optional[datetime]:
        """Parse ICS datetime value."""
        try:
            # Remove timezone info for now (basic parsing)
            if value.endswith("Z"):
                value = value[:-1]

            # Try different datetime formats
            formats = [
                "%Y%m%dT%H%M%S",  # 20230101T120000
                "%Y%m%d",  # 20230101 (date only)
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue

        except Exception:
            pass

        return None

    def _parse_person(self, value: str) -> str:
        """Parse person field (organizer/attendee)."""
        # Extract email and name from formats like:
        # MAILTO:john@example.com
        # CN=John Doe:MAILTO:john@example.com
        if "MAILTO:" in value:
            email = value.split("MAILTO:")[1]
        else:
            email = value

        if "CN=" in value:
            name = value.split("CN=")[1].split(":")[0]
            return f"{name} <{email}>"

        return email


class MarkdownGenerator:
    """Generate Markdown documents from ICS events."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_markdown(self, event: ICSEvent, source_file: str) -> Path:
        """Generate a Markdown file for a single event."""
        # Create filename from summary and UID
        filename = self._create_filename(event)
        output_path = self.output_dir / f"{filename}.md"

        # Generate markdown content
        content = self._generate_content(event, source_file)

        # Write to file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return output_path

    def _create_filename(self, event: ICSEvent) -> str:
        """Create a safe filename from event data."""
        # Use summary or UID for filename
        if event.summary:
            base = event.summary
        elif event.uid:
            base = event.uid
        else:
            base = "untitled_event"

        # Add date prefix if available
        if event.start_time:
            date_prefix = event.start_time.strftime("%Y%m%d")
            base = f"{date_prefix}_{base}"

        # Clean filename
        filename = re.sub(r"[^\w\-_\.]", "_", base)
        filename = re.sub(r"_+", "_", filename)
        filename = filename.strip("_")

        # Limit length
        if len(filename) > 100:
            filename = filename[:100]

        return filename

    def _generate_content(self, event: ICSEvent, source_file: str) -> str:
        """Generate markdown content for an event."""
        lines = []

        # Title
        title = event.summary or "Untitled Event"
        lines.append(f"# {title}")
        lines.append("")

        # Metadata table
        lines.append("## Event Details")
        lines.append("")

        if event.start_time:
            start_str = event.start_time.strftime("%Y-%m-%d %H:%M")
            lines.append(f"**Start:** {start_str}")

        if event.end_time:
            end_str = event.end_time.strftime("%Y-%m-%d %H:%M")
            lines.append(f"**End:** {end_str}")

        if event.location:
            lines.append(f"**Location:** {event.location}")

        if event.organizer:
            lines.append(f"**Organizer:** {event.organizer}")

        if event.attendees:
            lines.append(f"**Attendees:** {', '.join(event.attendees)}")

        if event.categories:
            lines.append(f"**Categories:** {', '.join(event.categories)}")

        if event.status:
            lines.append(f"**Status:** {event.status}")

        if event.priority:
            lines.append(f"**Priority:** {event.priority}")

        if event.url:
            lines.append(f"**URL:** {event.url}")

        lines.append("")

        # Description
        if event.description:
            lines.append("## Description")
            lines.append("")
            lines.append(event.description)
            lines.append("")

        # Metadata
        lines.append("## Metadata")
        lines.append("")
        lines.append(f"**Source File:** {source_file}")

        if event.uid:
            lines.append(f"**UID:** {event.uid}")

        if event.created:
            created_str = event.created.strftime("%Y-%m-%d %H:%M")
            lines.append(f"**Created:** {created_str}")

        if event.last_modified:
            modified_str = event.last_modified.strftime("%Y-%m-%d %H:%M")
            lines.append(f"**Last Modified:** {modified_str}")

        return "\n".join(lines)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Convert ICS calendar files to Markdown documents")
    parser.add_argument("input_path", help="Path to ICS file or directory containing ICS files")
    parser.add_argument(
        "-o", "--output", default="./markdown_events", help="Output directory for Markdown files (default: ./markdown_events)"
    )

    args = parser.parse_args()

    input_path = Path(args.input_path)
    output_dir = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input path '{input_path}' does not exist")
        return 1

    # Find ICS files
    ics_files = []
    if input_path.is_file():
        if input_path.suffix.lower() == ".ics":
            ics_files.append(input_path)
        else:
            print(f"Error: '{input_path}' is not an ICS file")
            return 1
    elif input_path.is_dir():
        ics_files = list(input_path.glob("*.ics"))
        ics_files.extend(list(input_path.glob("*.ICS")))
        if not ics_files:
            print(f"No ICS files found in directory '{input_path}'")
            return 1

    print(f"Found {len(ics_files)} ICS file(s)")

    # Initialize components
    parser_obj = ICSParser()
    generator = MarkdownGenerator(output_dir)

    total_events = 0

    # Process each ICS file
    for ics_file in ics_files:
        print(f"Processing {ics_file.name}...")

        try:
            events = parser_obj.parse_file(ics_file)
            print(f"  Found {len(events)} event(s)")

            for event in events:
                output_path = generator.generate_markdown(event, ics_file.name)
                print(f"  Created {output_path.name}")
                total_events += 1

        except Exception as e:
            print(f"  Error processing {ics_file.name}: {e}")

    print(f"\nConversion complete!")
    print(f"Total events processed: {total_events}")
    print(f"Markdown files saved to: {output_dir}")

    return 0


if __name__ == "__main__":
    exit(main())
