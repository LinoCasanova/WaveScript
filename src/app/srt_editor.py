"""
SRT Editor Dialog - Edit subtitle files section by section.
"""
from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QWidget, QMessageBox
)
from PySide6.QtCore import Qt


@dataclass
class SrtSection:
    """Represents a single SRT subtitle section."""
    index: int
    start_time: str
    end_time: str
    text: str


class SrtParser:
    """Parse and write SRT files."""

    @staticmethod
    def parse_srt_file(file_path: Path) -> list[SrtSection]:
        """Parse an SRT file into sections."""
        sections = []

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Split by double newlines to get individual sections
        raw_sections = content.strip().split('\n\n')

        for raw_section in raw_sections:
            lines = raw_section.strip().split('\n')

            if len(lines) < 3:
                continue  # Skip malformed sections

            try:
                index = int(lines[0])
                times = lines[1].split(' --> ')
                start_time = times[0].strip()
                end_time = times[1].strip()
                text = '\n'.join(lines[2:])

                sections.append(SrtSection(
                    index=index,
                    start_time=start_time,
                    end_time=end_time,
                    text=text
                ))
            except (ValueError, IndexError):
                continue  # Skip malformed sections

        return sections

    @staticmethod
    def write_srt_file(file_path: Path, sections: list[SrtSection]) -> None:
        """Write sections to an SRT file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            for i, section in enumerate(sections):
                # Re-index sections in case any were deleted
                f.write(f"{i + 1}\n")
                f.write(f"{section.start_time} --> {section.end_time}\n")
                f.write(f"{section.text}\n")

                # Add blank line between sections (except after last)
                if i < len(sections) - 1:
                    f.write("\n")


class SrtEditorDialog(QDialog):
    """Dialog for editing SRT subtitle files."""

    def __init__(self, srt_file_path: Path, parent=None):
        super().__init__(parent)
        self.srt_file_path = srt_file_path
        self.sections: list[SrtSection] = []
        self.current_index = 0
        self.modified = False

        # Parse the SRT file
        try:
            self.sections = SrtParser.parse_srt_file(srt_file_path)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Loading SRT",
                f"Failed to load SRT file: {str(e)}"
            )
            self.reject()
            return

        if not self.sections:
            QMessageBox.warning(
                self,
                "Empty File",
                "The SRT file contains no valid sections."
            )
            self.reject()
            return

        self.init_ui()
        self.load_section(0)

    def init_ui(self):
        """Initialize the editor UI."""
        self.setWindowTitle(f"SRT Editor - {self.srt_file_path.name}")
        self.setMinimumWidth(600)
        self.setMinimumHeight(240)  # 40% smaller than 400

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Navigation section (centered section number with prev/next buttons)
        nav_layout = QHBoxLayout()
        nav_layout.addStretch()

        self.prev_btn = QPushButton("<")
        self.prev_btn.setFixedWidth(50)
        self.prev_btn.clicked.connect(self.previous_section)
        nav_layout.addWidget(self.prev_btn)

        self.section_label = QLabel()
        self.section_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.section_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        nav_layout.addWidget(self.section_label)

        self.next_btn = QPushButton(">")
        self.next_btn.setFixedWidth(50)
        self.next_btn.clicked.connect(self.next_section)
        nav_layout.addWidget(self.next_btn)

        nav_layout.addStretch()
        layout.addLayout(nav_layout)

        # Timestamps section (start, arrow, end)
        time_layout = QHBoxLayout()

        self.start_time_label = QLabel()
        self.start_time_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.start_time_label.setStyleSheet("font-size: 14px;")
        time_layout.addWidget(self.start_time_label)

        arrow_label = QLabel("→")
        arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow_label.setStyleSheet("font-size: 18px;")
        time_layout.addWidget(arrow_label)

        self.end_time_label = QLabel()
        self.end_time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.end_time_label.setStyleSheet("font-size: 14px;")
        time_layout.addWidget(self.end_time_label)

        layout.addLayout(time_layout)

        # Text edit section
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Subtitle text...")
        # Set maximum height to half of the previous default
        self.text_edit.setMaximumHeight(100)
        layout.addWidget(self.text_edit)

        # Save/Cancel buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_changes)
        buttons_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.cancel_changes)
        buttons_layout.addWidget(cancel_btn)

        layout.addLayout(buttons_layout)

        self.setLayout(layout)

    def load_section(self, index: int):
        """Load a section into the editor."""
        if index < 0 or index >= len(self.sections):
            return

        self.current_index = index
        section = self.sections[index]

        # Update section label
        self.section_label.setText(f"Section {index + 1} / {len(self.sections)}")

        # Update timestamps
        self.start_time_label.setText(section.start_time)
        self.end_time_label.setText(section.end_time)

        # Update text
        self.text_edit.setPlainText(section.text)

        # Update navigation buttons
        self.prev_btn.setEnabled(index > 0)
        self.next_btn.setEnabled(index < len(self.sections) - 1)

    def save_current_section(self):
        """Save the current section's text."""
        if 0 <= self.current_index < len(self.sections):
            new_text = self.text_edit.toPlainText()
            if self.sections[self.current_index].text != new_text:
                self.sections[self.current_index].text = new_text
                self.modified = True

    def previous_section(self):
        """Navigate to the previous section."""
        self.save_current_section()
        if self.current_index > 0:
            self.load_section(self.current_index - 1)

    def next_section(self):
        """Navigate to the next section."""
        self.save_current_section()
        if self.current_index < len(self.sections) - 1:
            self.load_section(self.current_index + 1)

    def save_changes(self):
        """Save all changes to the SRT file."""
        self.save_current_section()

        if not self.modified:
            self.accept()
            return

        try:
            SrtParser.write_srt_file(self.srt_file_path, self.sections)
            QMessageBox.information(
                self,
                "Saved",
                "Changes saved successfully!"
            )
            self.modified = False
            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Save Error",
                f"Failed to save changes: {str(e)}"
            )

    def cancel_changes(self):
        """Cancel editing and close without saving."""
        if self.modified:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Are you sure you want to close?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.reject()
        else:
            self.reject()

    def closeEvent(self, event):
        """Handle window close event."""
        if self.modified:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Are you sure you want to close?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
