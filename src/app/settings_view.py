"""
Settings View - UI for application settings.
Combines settings UI and helper methods.
"""
from __future__ import annotations

from pathlib import Path
import os
import urllib.request
import ssl
import certifi
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QGroupBox, QMessageBox, QListWidget, QListWidgetItem,
    QCheckBox, QProgressDialog, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtCore import Signal as pyqtSignal

from .transcriber_types import WhisperModel
from src.util.context import Context


class ModelDownloadWorker(QThread):
    """Worker thread for downloading Whisper models with progress tracking."""

    progress = pyqtSignal(int)  # Progress percentage (0-100)
    finished = pyqtSignal(bool, str)  # Success flag, error message

    def __init__(self, model_name: str, download_dir: Path):
        super().__init__()
        self.model_name = model_name
        self.download_dir = download_dir
        self._is_cancelled = False
        self._last_reported_percentage = -1

    def run(self):
        """Download the model with progress tracking."""
        try:

            # Whisper model URLs (from whisper/__init__.py)
            _MODELS = {
                "tiny": "https://openaipublic.azureedge.net/main/whisper/models/65147644a518d12f04e32d6f3b26facc3f8dd46e5390956a9424a650c0ce22b9/tiny.pt",
                "base": "https://openaipublic.azureedge.net/main/whisper/models/ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b0e6c6326e34e/base.pt",
                "small": "https://openaipublic.azureedge.net/main/whisper/models/9ecf779972d90ba49c06d968637d720dd632c55bbf19d441fb42bf17a411e794/small.pt",
                "medium": "https://openaipublic.azureedge.net/main/whisper/models/345ae4da62f9b3d59415adc60127b97c714f32e89e936602e85993674d08dcb1/medium.pt",
                "turbo": "https://openaipublic.azureedge.net/main/whisper/models/aff26ae408abcba5fbf8813c21e62b0941638c5f6eebfb145be0c9839262a19a/large-v3-turbo.pt",
                "large": "https://openaipublic.azureedge.net/main/whisper/models/e5b1a55b89c1367dacf97e3e19bfd829a01529dbfdeefa8caeb59b3f1b81dadb/large-v3.pt",
            }

            url = _MODELS.get(self.model_name)
            if not url:
                self.finished.emit(False, f"Unknown model: {self.model_name}")
                return

            # Prepare download path
            self.download_dir.mkdir(parents=True, exist_ok=True)
            output_path = self.download_dir / f"{self.model_name}.pt"

            # Download with progress tracking using SSL context
            ssl_context = ssl.create_default_context(cafile=certifi.where())

            # Open URL with SSL context
            with urllib.request.urlopen(url, context=ssl_context) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0
                chunk_size = 8192

                with open(output_path, 'wb') as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Emit progress updates
                        if total_size > 0:
                            percentage = min(int((downloaded / total_size) * 100), 100)
                            if percentage != self._last_reported_percentage:
                                self._last_reported_percentage = percentage
                                self.progress.emit(percentage)

            self.finished.emit(True, "")

        except Exception as e:
            self.finished.emit(False, str(e))


class SettingsHelper:
    """Helper class for settings-related operations."""

    # Approximate model sizes in MB (from OpenAI Whisper documentation)
    MODEL_SIZES = {
        "tiny": 75,
        "base": 145,
        "small": 466,
        "medium": 1500,
        "turbo": 1600,
        "large": 2900
    }

    @staticmethod
    def get_model_directory() -> Path:
        """Get the configured model directory or use default."""
        # Check if user has configured a custom path
        custom_path = Context.Settings.get("whisper_models_path", "")
        if custom_path and Path(custom_path).exists():
            return Path(custom_path)

        # Use default Whisper cache location
        cache_dir = os.getenv('XDG_CACHE_HOME', str(Path.home() / ".cache"))
        return Path(cache_dir) / "whisper"

    @staticmethod
    def get_installed_models() -> set:
        """Check which Whisper models are already installed."""
        installed = set()
        download_root = SettingsHelper.get_model_directory()

        if download_root and download_root.exists():
            for model in WhisperModel:
                # Check if model file exists - Whisper downloads with .pt extension
                model_file = download_root / f"{model.value}.pt"
                if model_file.exists():
                    installed.add(model.value)

        return installed

    @staticmethod
    def delete_model(model_name: str) -> bool:
        """Delete a specific Whisper model file."""
        download_root = SettingsHelper.get_model_directory()
        model_file = download_root / f"{model_name}.pt"

        if model_file.exists():
            try:
                model_file.unlink()
                return True
            except Exception:
                return False
        return False

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
    # Signal emitted when models change (install/delete) - doesn't close settings
    models_changed = Signal()

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

        # Model directory path
        path_layout = QHBoxLayout()
        path_label = QLabel("Models Directory:")
        path_layout.addWidget(path_label)

        self.model_path_edit = QLineEdit()
        self.model_path_edit.setPlaceholderText("Default: ~/.cache/whisper")
        self.model_path_edit.setReadOnly(True)
        path_layout.addWidget(self.model_path_edit)

        browse_path_btn = QPushButton("Browse")
        browse_path_btn.clicked.connect(self._browse_model_path)
        path_layout.addWidget(browse_path_btn)

        models_layout.addLayout(path_layout)

        self.models_list = QListWidget()
        self.models_list.setSelectionMode(QListWidget.SingleSelection)
        self.models_list.setMaximumHeight(150)
        models_layout.addWidget(self.models_list)

        # Button layout for model actions
        model_buttons_layout = QHBoxLayout()

        install_btn = QPushButton("Install Selected Model")
        install_btn.clicked.connect(self._install_selected_model)
        model_buttons_layout.addWidget(install_btn)

        delete_btn = QPushButton("Delete Selected Model")
        delete_btn.clicked.connect(self._delete_selected_model)
        model_buttons_layout.addWidget(delete_btn)

        models_layout.addLayout(model_buttons_layout)

        models_group.setLayout(models_layout)
        layout.addWidget(models_group)

        layout.addStretch()

        # Close button at the bottom
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self._on_close)
        buttons_layout.addWidget(close_btn)

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

        # Load model path - check if custom path still exists
        model_path = Context.Settings.get("whisper_models_path", "")
        if model_path and Path(model_path).exists():
            self.model_path_edit.setText(model_path)
        else:
            # If custom path doesn't exist or is empty, use default and clear custom setting
            if model_path and not Path(model_path).exists():
                # Custom path was set but directory was deleted/moved - clear the setting
                Context.Settings.delete("whisper_models_path")
            default_path = SettingsHelper.get_model_directory()
            self.model_path_edit.setText(str(default_path))

        self._refresh_models_list()

    def _save_settings(self) -> None:
        """Save all settings to persistent storage."""
        Context.Settings.set("api_key", self.api_key_edit.text())
        Context.Settings.set("open_srt_editor_when_done", self.open_editor_checkbox.isChecked())
        Context.Settings.set("remove_temp_files_on_close", self.remove_temp_checkbox.isChecked())

        # Save model path (only if it's not the default)
        model_path = self.model_path_edit.text()
        default_cache = os.getenv('XDG_CACHE_HOME', str(Path.home() / ".cache"))
        default_path = str(Path(default_cache) / "whisper")
        if model_path and model_path != default_path:
            Context.Settings.set("whisper_models_path", model_path)
        else:
            # Clear custom path if set to default
            if Context.Settings.contains("whisper_models_path"):
                Context.Settings.delete("whisper_models_path")

    def _on_close(self) -> None:
        """Save settings and close."""
        self._save_settings()
        self.settings_saved.emit()

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

        # Get model size
        size_mb = SettingsHelper.MODEL_SIZES.get(model_name, 0)
        if size_mb >= 1000:
            size_str = f"{size_mb / 1000:.1f} GB"
        else:
            size_str = f"{size_mb} MB"

        reply = QMessageBox.question(
            self,
            "Install Model",
            f"Download and install the '{model_name}' model?\n\n"
            f"Download size: {size_str}",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._download_model(model_name)

    def _download_model(self, model_name: str) -> None:
        """Download a Whisper model with progress tracking."""
        # Create progress dialog with determinate progress (0-100)
        self.download_progress = QProgressDialog("Initializing download...", "Cancel", 0, 100, self)
        self.download_progress.setWindowTitle("Installing Model")
        self.download_progress.setWindowModality(Qt.WindowModal)
        self.download_progress.setMinimumDuration(0)
        self.download_progress.setValue(0)
        self.download_progress.canceled.connect(self._cancel_download)
        self.download_progress.show()

        # Create and start download worker
        model_dir = SettingsHelper.get_model_directory()
        self.download_worker = ModelDownloadWorker(model_name, model_dir)

        # Connect signals
        self.download_worker.progress.connect(self._on_download_progress)
        self.download_worker.finished.connect(self._on_download_finished)

        self.download_worker.start()

    def _on_download_progress(self, percentage: int) -> None:
        """Update download progress."""
        if hasattr(self, 'download_progress') and self.download_progress:
            self.download_progress.setValue(percentage)
            self.download_progress.setLabelText("Downloading model...")

    def _on_download_finished(self, success: bool, error_message: str) -> None:
        """Handle download completion."""
        # Clean up the worker thread immediately when finished signal is received
        if hasattr(self, 'download_worker') and self.download_worker:
            # Disconnect all signals first
            try:
                self.download_worker.progress.disconnect()
                self.download_worker.finished.disconnect()
            except (TypeError, RuntimeError):
                pass

            # Schedule thread for deletion
            self.download_worker.deleteLater()
            self.download_worker = None

        if hasattr(self, 'download_progress') and self.download_progress:
            self.download_progress.close()
            self.download_progress = None

        if success:
            QMessageBox.information(self, "Success", "Model downloaded successfully!")
            self._refresh_models_list()
            self.models_changed.emit()
        else:
            QMessageBox.critical(self, "Error", f"Failed to download model: {error_message}")

    def _cancel_download(self) -> None:
        """Cancel the ongoing download."""
        # Close and disconnect the progress dialog first
        if hasattr(self, 'download_progress') and self.download_progress:
            try:
                self.download_progress.canceled.disconnect(self._cancel_download)
            except (TypeError, RuntimeError):
                pass

            self.download_progress.close()
            self.download_progress = None

        # Terminate the worker thread and clean up
        if hasattr(self, 'download_worker') and self.download_worker:
            # Disconnect signals to prevent callbacks after cancellation
            try:
                self.download_worker.progress.disconnect()
                self.download_worker.finished.disconnect()
            except (TypeError, RuntimeError):
                pass

            self.download_worker.terminate()
            self.download_worker.wait()
            self.download_worker.deleteLater()
            self.download_worker = None

    def _browse_model_path(self) -> None:
        """Browse for a custom model directory."""
        current_path = self.model_path_edit.text()
        if not current_path:
            current_path = str(Path.home())

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Whisper Models Directory",
            current_path,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if directory:
            self.model_path_edit.setText(directory)
            Context.Settings.set("whisper_models_path", directory)
            self._refresh_models_list()

    def _delete_selected_model(self) -> None:
        """Delete the selected Whisper model."""
        current_item = self.models_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a model to delete.")
            return

        is_installed = current_item.data(Qt.UserRole)
        if not is_installed:
            QMessageBox.information(self, "Not Installed", "This model is not installed.")
            return

        model_name = current_item.text().replace(" ✓", "").strip()

        reply = QMessageBox.question(
            self,
            "Delete Model",
            f"Are you sure you want to delete the '{model_name}' model?\n\n"
            f"This will permanently remove the model file from your system.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if SettingsHelper.delete_model(model_name):
                QMessageBox.information(self, "Success", f"Model '{model_name}' deleted successfully!")
                self._refresh_models_list()
                self.models_changed.emit()
            else:
                QMessageBox.critical(self, "Error", f"Failed to delete model '{model_name}'.")
