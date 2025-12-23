"""
Settings View - UI for application settings.
Combines settings UI and helper methods.
"""
from __future__ import annotations

from pathlib import Path
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QGroupBox, QMessageBox, QListWidget, QListWidgetItem,
    QCheckBox, QProgressDialog
)
from PySide6.QtCore import Qt, Signal

from .transcriber_types import WhisperModel
from src.util.context import Context


class SettingsHelper:
    """Helper class for settings-related operations."""

    @staticmethod
    def get_installed_models() -> set:
        """Check which Whisper models are already installed."""
        import whisper
        installed = set()

        # Get Whisper's download root - try multiple locations
        download_root = None
        if hasattr(whisper, '_MODELS_DIR'):
            download_root = Path(whisper._MODELS_DIR)
        else:
            # Try default cache locations
            cache_dir = os.getenv('XDG_CACHE_HOME', str(Path.home() / ".cache"))
            download_root = Path(cache_dir) / "whisper"

        if download_root and download_root.exists():
            for model in WhisperModel:
                # Check if model file exists - Whisper downloads with .pt extension
                model_file = download_root / f"{model.value}.pt"
                if model_file.exists():
                    installed.add(model.value)

        return installed

    @staticmethod
    def get_stored_api_key() -> str:
        """Get the stored API key from settings."""
        return Context.Settings.get("api_key", "")

    @staticmethod
    def has_api_key() -> bool:
        """Check if an API key is stored."""
        return bool(SettingsHelper.get_stored_api_key())


class SettingsView(QWidget):
    """Settings view widget."""

    # Signal emitted when settings are saved
    settings_saved = Signal()
    # Signal emitted when user cancels settings
    settings_cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the settings UI."""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("Settings")
        title.setObjectName("SettingsTitle")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        # General settings
        general_group = QGroupBox("General")
        general_layout = QVBoxLayout()

        self.open_editor_checkbox = QCheckBox("Open SRT editor when transcription is done")
        general_layout.addWidget(self.open_editor_checkbox)

        self.remove_temp_checkbox = QCheckBox("Remove temporary files when closing app")
        general_layout.addWidget(self.remove_temp_checkbox)

        general_group.setLayout(general_layout)
        layout.addWidget(general_group)

        # API Key settings
        api_group = QGroupBox("OpenAI API Key")
        api_layout = QVBoxLayout()

        info_label = QLabel("Enter your OpenAI API key for online transcription:")
        info_label.setWordWrap(True)
        api_layout.addWidget(info_label)

        key_layout = QHBoxLayout()
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("sk-...")
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        key_layout.addWidget(self.api_key_edit)

        show_key_btn = QPushButton("Show")
        show_key_btn.setCheckable(True)
        show_key_btn.toggled.connect(self._toggle_api_key_visibility)
        key_layout.addWidget(show_key_btn)

        api_layout.addLayout(key_layout)

        clear_btn = QPushButton("Clear API Key")
        clear_btn.clicked.connect(self._clear_api_key)
        api_layout.addWidget(clear_btn)

        api_group.setLayout(api_layout)
        layout.addWidget(api_group)

        # Whisper Models settings
        models_group = QGroupBox("Local Whisper Models")
        models_layout = QVBoxLayout()

        self.models_list = QListWidget()
        self.models_list.setSelectionMode(QListWidget.SingleSelection)
        self.models_list.setMaximumHeight(150)
        models_layout.addWidget(self.models_list)

        install_btn = QPushButton("Install Selected Model")
        install_btn.clicked.connect(self._install_selected_model)
        models_layout.addWidget(install_btn)

        models_group.setLayout(models_layout)
        layout.addWidget(models_group)

        layout.addStretch()

        # Save and Cancel buttons at the bottom
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self._on_cancel)
        buttons_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self._on_save)
        buttons_layout.addWidget(save_btn)

        layout.addLayout(buttons_layout)

        self.setLayout(layout)

    def load_settings(self) -> None:
        """Load current settings into the view."""
        # Load API key
        api_key = Context.Settings.get("api_key", "")
        self.api_key_edit.setText(api_key)

        # Load checkboxes
        open_editor = Context.Settings.get("open_srt_editor_when_done", True)
        self.open_editor_checkbox.setChecked(open_editor)

        remove_temp = Context.Settings.get("remove_temp_files_on_close", True)
        self.remove_temp_checkbox.setChecked(remove_temp)

        # Refresh models list
        self._refresh_models_list()

    def _on_save(self) -> None:
        """Save settings and emit signal."""
        Context.Settings.set("api_key", self.api_key_edit.text())
        Context.Settings.set("open_srt_editor_when_done", self.open_editor_checkbox.isChecked())
        Context.Settings.set("remove_temp_files_on_close", self.remove_temp_checkbox.isChecked())

        self.settings_saved.emit()

    def _on_cancel(self) -> None:
        """Cancel settings changes and emit signal."""
        self.settings_cancelled.emit()

    def _toggle_api_key_visibility(self, checked: bool) -> None:
        """Toggle API key visibility."""
        if checked:
            self.api_key_edit.setEchoMode(QLineEdit.Normal)
        else:
            self.api_key_edit.setEchoMode(QLineEdit.Password)

    def _clear_api_key(self) -> None:
        """Clear the API key."""
        reply = QMessageBox.question(
            self,
            "Clear API Key",
            "Are you sure you want to clear the stored API key?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.api_key_edit.clear()

    def _refresh_models_list(self) -> None:
        """Refresh the list of Whisper models."""
        self.models_list.clear()
        installed_models = SettingsHelper.get_installed_models()

        for model in WhisperModel:
            if model.value in installed_models:
                item = QListWidgetItem(f"{model.value} ✓")
                item.setData(Qt.UserRole, True)
            else:
                item = QListWidgetItem(model.value)
                item.setData(Qt.UserRole, False)
            self.models_list.addItem(item)

    def _install_selected_model(self) -> None:
        """Install the selected Whisper model."""
        current_item = self.models_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a model to install.")
            return

        is_installed = current_item.data(Qt.UserRole)
        if is_installed:
            QMessageBox.information(self, "Already Installed", "This model is already installed.")
            return

        model_name = current_item.text().split()[0]

        reply = QMessageBox.question(
            self,
            "Install Model",
            f"Download and install the '{model_name}' model?\n\n"
            f"This may take several minutes depending on your connection.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._download_model(model_name)

    def _download_model(self, model_name: str) -> None:
        """Download a Whisper model."""
        progress = QProgressDialog("Downloading model...", "Cancel", 0, 0, self)
        progress.setWindowTitle("Installing Model")
        progress.setWindowModality(Qt.WindowModal)
        progress.setCancelButton(None)
        progress.show()

        try:
            import whisper
            whisper.load_model(model_name)
            progress.close()
            QMessageBox.information(self, "Success", f"Model '{model_name}' downloaded successfully!")
            self._refresh_models_list()
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Error", f"Failed to download model: {str(e)}")
