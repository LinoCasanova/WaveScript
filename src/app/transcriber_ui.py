from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QRadioButton, QButtonGroup,
    QSpinBox, QFileDialog, QProgressBar, QGroupBox, QMessageBox,
    QStackedWidget, QStackedLayout, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from .transcriber_types import (
    TranscriptionSettings, Language, WhisperModel, TranscriptionMode
)
from .transcriber import TranscriptionWorker
from .settings_view import SettingsView, SettingsHelper
from src.util.context import Context
from src.util.media import MediaHandler
from .srt_editor import SrtEditorDialog


class IconButton(QPushButton):
    """Button that changes icon on hover and press."""

    def __init__(self, normal_icon: Path, hover_icon: Path, pressed_icon: Path, size: int = 22, parent=None):
        super().__init__(parent)
        self.normal_icon = QIcon(str(normal_icon))
        self.hover_icon = QIcon(str(hover_icon))
        self.pressed_icon = QIcon(str(pressed_icon))

        self.setIcon(self.normal_icon)
        self.setIconSize(QSize(size, size))
        self.setObjectName("SettingsGearButton")
        self.setFixedSize(40, 40)
        self.setFlat(True)

    def enterEvent(self, event):
        """Mouse enters button - show hover icon."""
        self.setIcon(self.hover_icon)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Mouse leaves button - show normal icon."""
        self.setIcon(self.normal_icon)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Mouse pressed - show pressed icon."""
        self.setIcon(self.pressed_icon)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Mouse released - show hover if still hovering, otherwise normal."""
        if self.rect().contains(event.pos()):
            self.setIcon(self.hover_icon)
        else:
            self.setIcon(self.normal_icon)
        super().mouseReleaseEvent(event)


class TranscriberUI(QWidget):
    """Main UI for audio transcription."""

    def __init__(self) -> None:
        super().__init__()
        self.selected_file: Path | None = None
        self.worker: TranscriptionWorker | None = None
        self.temp_files: set[Path] = set()  # Track all temporary files for cleanup
        # Load saved settings or use defaults
        self.saved_mode = self._load_saved_mode()
        self.saved_model = self._load_saved_model()
        self.saved_settings = self._load_saved_settings()
        self.init_ui()

    def _load_saved_settings(self) -> TranscriptionSettings:
        """Load saved transcription settings from Context.Settings or use defaults."""
        settings_dict = Context.Settings.get("transcription_settings", None)
        if settings_dict:
            try:
                return TranscriptionSettings.from_dict(settings_dict)
            except (ValueError, KeyError):
                # If stored settings are invalid, fall back to defaults
                pass
        return TranscriptionSettings()

    def _load_saved_mode(self) -> TranscriptionMode:
        """Load saved transcription mode from Context.Settings or use default."""
        mode_value = Context.Settings.get("transcription_mode", None)
        if mode_value:
            try:
                return TranscriptionMode(mode_value)
            except ValueError:
                # If stored mode is invalid, fall back to default
                pass
        return TranscriptionMode.OFFLINE

    def _load_saved_model(self) -> WhisperModel:
        """Load saved Whisper model from Context.Settings or use default."""
        model_value = Context.Settings.get("whisper_model", None)
        if model_value:
            try:
                return WhisperModel(model_value)
            except ValueError:
                # If stored model is invalid, fall back to default
                pass
        return WhisperModel.BASE

    def init_ui(self) -> None:
        """Initialize the user interface."""
        self.setWindowTitle("Audio Transcriber")
        self.setMinimumWidth(475)
        self.setMaximumWidth(475)
        self.setMinimumHeight(655)
        self.setMaximumHeight(655)

        # Enable drag and drop
        self.setAcceptDrops(True)

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Top bar with settings gear
        top_bar = QWidget()
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(0, 10, 10, 0)
        top_bar_layout.addStretch()

        # Settings gear button with icon (20px = smaller size)
        icon_dir = Context.assets_dir / "icons"
        self.settings_btn = IconButton(
            normal_icon=icon_dir / "gear.svg",
            hover_icon=icon_dir / "gear_hover.svg",
            pressed_icon=icon_dir / "gear_pressed.svg",
            size=20
        )
        self.settings_btn.clicked.connect(lambda: print("[DEBUG] Settings button clicked!"))
        self.settings_btn.clicked.connect(self.toggle_settings)
        self.settings_btn.setToolTip("Settings")
        top_bar_layout.addWidget(self.settings_btn)

        top_bar.setLayout(top_bar_layout)
        self.top_bar = top_bar
        main_layout.addWidget(top_bar)

        # Header with logo and app name
        self.header_widget = self._create_header()
        main_layout.addWidget(self.header_widget)

        # Stacked widget to switch between main view and settings
        self.stacked_widget = QStackedWidget()

        # Create main transcription view
        main_view = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(15)
        self.content_layout.setContentsMargins(10, 10, 10, 10)

        # File selection section
        file_group = self._create_file_selection_group()
        self.content_layout.addWidget(file_group)

        # Mode selection section
        mode_group = self._create_mode_selection_group()
        self.content_layout.addWidget(mode_group)

        # Settings section
        settings_group = self._create_settings_group()
        self.content_layout.addWidget(settings_group)

        # Add spacer to maintain consistent button position when mode changes
        spacer = QSpacerItem(0, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.content_layout.addItem(spacer)

        # Create a container widget for the stacked layout
        action_container = QWidget()
        action_container.setMinimumHeight(45)
        action_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        # Create a stacked layout to switch between button and progress views
        self.action_stack = QStackedLayout()
        self.action_stack.setContentsMargins(0, 0, 0, 0)

        # Page 0: Transcribe button
        self.transcribe_btn = QPushButton("Start Transcription")
        self.transcribe_btn.setObjectName("TranscribeButton")
        self.transcribe_btn.clicked.connect(self.start_transcription)
        self.transcribe_btn.setFixedHeight(45)
        self.transcribe_btn.setEnabled(False)
        self.action_stack.addWidget(self.transcribe_btn)

        # Page 1: Progress section
        progress_container = QWidget()
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(2)
        progress_layout.setContentsMargins(0, 0, 0, 0)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        progress_layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("margin-left: 1px;")
        progress_layout.addWidget(self.status_label)

        progress_container.setLayout(progress_layout)
        self.action_stack.addWidget(progress_container)

        # Start with button visible (index 0)
        self.action_stack.setCurrentIndex(0)

        # Set the stacked layout on the container
        action_container.setLayout(self.action_stack)

        # Add the container to the main content layout
        self.content_layout.addWidget(action_container)

        main_view.setLayout(self.content_layout)
        self.stacked_widget.addWidget(main_view)  # Index 0

        # Create settings view
        self.settings_view = SettingsView(self)
        self.settings_view.settings_saved.connect(self._on_settings_saved)
        self.settings_view.models_changed.connect(self._on_models_changed)
        self.stacked_widget.addWidget(self.settings_view)  # Index 1

        main_layout.addWidget(self.stacked_widget)

        self.setLayout(main_layout)

        # Update UI based on settings
        self.update_ui_based_on_settings()

    def _create_header(self) -> QWidget:
        """Create the header with centered app name."""
        header = QWidget()
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(20, 0, 20, 20)

        # Centered app name with colored parts
        app_name = QLabel('<span style="color: #00ffee;">wave</span><span style="color: #ea0a54;">script</span>')
        app_name.setObjectName("Title")
        app_name.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header_layout.addWidget(app_name)

        header.setLayout(header_layout)
        # Set fixed height after layout is set to prevent header from expanding vertically
        header.setFixedHeight(header.sizeHint().height())
        return header

    def _create_file_selection_group(self) -> QGroupBox:
        """Create the file selection group."""
        group = QGroupBox("Media File")
        layout = QHBoxLayout()

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("No file selected")
        self.file_path_edit.setReadOnly(True)
        layout.addWidget(self.file_path_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_file)
        layout.addWidget(browse_btn)

        group.setLayout(layout)
        return group

    def _create_mode_selection_group(self) -> QGroupBox:
        """Create the transcription mode selection group."""
        group = QGroupBox("Transcription Mode")
        layout = QVBoxLayout()

        # Radio buttons for mode selection
        mode_layout = QHBoxLayout()
        self.mode_group = QButtonGroup()

        self.offline_radio = QRadioButton("Offline (Local Whisper Model)")
        self.offline_radio.setChecked(self.saved_mode == TranscriptionMode.OFFLINE)
        self.offline_radio.toggled.connect(self.on_mode_changed)
        self.mode_group.addButton(self.offline_radio)
        mode_layout.addWidget(self.offline_radio)

        self.online_radio = QRadioButton("Online (OpenAI API)")
        self.online_radio.setChecked(self.saved_mode == TranscriptionMode.ONLINE)
        self.online_radio.toggled.connect(self.on_mode_changed)
        self.mode_group.addButton(self.online_radio)
        mode_layout.addWidget(self.online_radio)

        layout.addLayout(mode_layout)

        group.setLayout(layout)
        return group

    def _create_settings_group(self) -> QGroupBox:
        """Create the transcription settings group."""
        group = QGroupBox("Settings")
        layout = QVBoxLayout()

        # Fixed width for all input widgets
        widget_width = 200

        # Whisper model selection (only visible for offline mode)
        model_layout = QHBoxLayout()
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_label = QLabel("Whisper Model:")
        self.model_combo = QComboBox()
        self.model_combo.setFixedWidth(widget_width)
        # Models will be populated by update_model_dropdown()
        model_layout.addWidget(model_label)
        model_layout.addStretch()
        model_layout.addWidget(self.model_combo)

        self.model_layout_widget = QWidget()
        self.model_layout_widget.setLayout(model_layout)
        self.model_layout_widget.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.model_layout_widget)

        # Language selection
        lang_layout = QHBoxLayout()
        lang_label = QLabel("Language:")
        self.language_combo = QComboBox()
        self.language_combo.setFixedWidth(widget_width)
        self.language_combo.addItems([lang.value for lang in Language])
        self.language_combo.setCurrentText(self.saved_settings.language.value)
        lang_layout.addWidget(lang_label)
        lang_layout.addStretch()
        lang_layout.addWidget(self.language_combo)
        layout.addLayout(lang_layout)

        # Max lines per subtitle
        lines_layout = QHBoxLayout()
        lines_label = QLabel("Max Lines per Subtitle:")
        self.max_lines_spin = QSpinBox()
        self.max_lines_spin.setFixedWidth(widget_width)
        self.max_lines_spin.setMinimum(1)
        self.max_lines_spin.setMaximum(5)
        self.max_lines_spin.setValue(self.saved_settings.max_line_count)
        lines_layout.addWidget(lines_label)
        lines_layout.addStretch()
        lines_layout.addWidget(self.max_lines_spin)
        layout.addLayout(lines_layout)

        # Max words per line
        words_layout = QHBoxLayout()
        words_label = QLabel("Max Words per Line:")
        self.max_words_spin = QSpinBox()
        self.max_words_spin.setFixedWidth(widget_width)
        self.max_words_spin.setMinimum(1)
        self.max_words_spin.setMaximum(20)
        self.max_words_spin.setValue(self.saved_settings.max_words_per_line)
        words_layout.addWidget(words_label)
        words_layout.addStretch()
        words_layout.addWidget(self.max_words_spin)
        layout.addLayout(words_layout)

        # Add extra spacing before initial prompt
        layout.addSpacing(10)

        # Initial prompt (optional)
        prompt_label = QLabel("Initial Prompt (optional):")
        self.prompt_edit = QLineEdit()
        self.prompt_edit.setPlaceholderText("Provide context to improve accuracy...")
        if self.saved_settings.initial_prompt:
            self.prompt_edit.setText(self.saved_settings.initial_prompt)
        layout.addWidget(prompt_label)
        layout.addWidget(self.prompt_edit)

        group.setLayout(layout)
        return group

    def _on_settings_saved(self) -> None:
        """Handle settings saved signal."""
        # Update UI based on new settings
        self.update_ui_based_on_settings()

        # Return to main view
        self._return_to_main_view()

    def _on_models_changed(self) -> None:
        """Handle models changed signal (install/delete) - stay in settings."""
        # Update UI based on new settings but don't close settings view
        self.update_ui_based_on_settings()

    def toggle_settings(self):
        """Switch to settings view."""
        try:
            print("[DEBUG] toggle_settings called")
            # Load current settings
            self.settings_view.load_settings()
            print("[DEBUG] settings loaded")

            # Hide header and top bar (with gear)
            self.header_widget.setVisible(False)
            self.top_bar.setVisible(False)

            # Switch to settings view
            self.stacked_widget.setCurrentIndex(1)
            print("[DEBUG] switched to settings view")
        except Exception as e:
            print(f"[ERROR] Failed to open settings: {e}")
            import traceback
            traceback.print_exc()

    def _return_to_main_view(self):
        """Return to main transcription view."""
        # Show header and top bar (with gear)
        self.header_widget.setVisible(True)
        self.top_bar.setVisible(True)

        # Switch to main view
        self.stacked_widget.setCurrentIndex(0)

    def update_ui_based_on_settings(self):
        """Update UI elements based on current settings."""
        # Update online mode availability based on API key
        has_api_key = SettingsHelper.has_api_key()
        self.online_radio.setEnabled(has_api_key)

        if not has_api_key and self.online_radio.isChecked():
            # If online was selected but no API key, switch to offline
            self.offline_radio.setChecked(True)

        # Update tooltip for online mode
        if not has_api_key:
            self.online_radio.setToolTip("Please set your API key in Settings to use online mode")
        else:
            self.online_radio.setToolTip("")

        # Update model dropdown to show only installed models
        self.update_model_dropdown()

        # Check if any models are installed for offline mode
        installed_models = SettingsHelper().get_installed_models()
        has_models = len(installed_models) > 0

        self.offline_radio.setEnabled(has_models)
        if not has_models:
            self.offline_radio.setToolTip("Please install a Whisper model in Settings to use offline mode")
            if self.offline_radio.isChecked():
                # Switch to online if available
                if has_api_key:
                    self.online_radio.setChecked(True)
        else:
            self.offline_radio.setToolTip("")

        # Update transcribe button state - only enable if file is selected AND a valid mode is available
        if self.selected_file:
            # Check if currently selected mode is valid
            if self.offline_radio.isChecked() and not has_models:
                self.transcribe_btn.setEnabled(False)
            elif self.online_radio.isChecked() and not has_api_key:
                self.transcribe_btn.setEnabled(False)
            else:
                self.transcribe_btn.setEnabled(True)
        else:
            self.transcribe_btn.setEnabled(False)


    def browse_file(self):
        """Open file dialog to select an audio or video file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio or Video File",
            "",
            "Media Files (*.mp3 *.wav *.m4a *.ogg *.flac *.aac *.wma *.mp4 *.mov *.avi *.mkv *.webm *.flv);;Audio Files (*.mp3 *.wav *.m4a *.ogg *.flac *.aac *.wma);;Video Files (*.mp4 *.mov *.avi *.mkv *.webm *.flv);;All Files (*.*)"
        )

        if file_path:
            self.selected_file = Path(file_path)
            self.file_path_edit.setText(str(self.selected_file))
            self.transcribe_btn.setEnabled(True)
            
    def update_model_dropdown(self):
        """Update the model dropdown to show only installed models."""
        current_selection = self.model_combo.currentText()
        self.model_combo.clear()

        # Get installed models
        installed_models = SettingsHelper().get_installed_models()

        # Add only installed models to dropdown
        available_models = [model for model in WhisperModel if model.value in installed_models]

        if available_models:
            self.model_combo.addItems([model.value for model in available_models])

            # Try to restore previous selection, otherwise use saved model
            if current_selection in [model.value for model in available_models]:
                self.model_combo.setCurrentText(current_selection)
            elif self.saved_model.value in [model.value for model in available_models]:
                self.model_combo.setCurrentText(self.saved_model.value)
        else:
            # No models installed
            self.model_combo.addItem("No models installed")
            self.model_combo.setEnabled(False)
            if self.offline_radio.isChecked():
                self.offline_radio.setToolTip("Please install a Whisper model in Settings")


    def on_mode_changed(self):
        """Handle mode selection changes."""
        is_offline = self.offline_radio.isChecked()
        self.model_layout_widget.setVisible(is_offline)

        # Update transcribe button state based on new mode
        self.update_ui_based_on_settings()


    def start_transcription(self):
        """Start the transcription process."""
        if not self.selected_file:
            QMessageBox.warning(self, "No File", "Please select a media file first.")
            return

        # Prepare audio file (extract from video if needed)
        try:
            audio_file, temp_file = MediaHandler.prepare_audio_file(self.selected_file)

            # Track temp file for cleanup
            if temp_file:
                self.temp_files.add(temp_file)

        except ValueError as e:
            QMessageBox.warning(self, "Unsupported File", str(e))
            return
        except RuntimeError as e:
            QMessageBox.critical(self, "Audio Extraction Failed", str(e))
            return

        # Get settings
        language = Language(self.language_combo.currentText())
        initial_prompt = self.prompt_edit.text() or None

        settings = TranscriptionSettings(
            language=language,
            max_line_count=self.max_lines_spin.value(),
            max_words_per_line=self.max_words_spin.value(),
            initial_prompt=initial_prompt
        )

        # Determine mode and create worker
        mode = TranscriptionMode.OFFLINE if self.offline_radio.isChecked() else TranscriptionMode.ONLINE

        # Store settings and mode in Context.Settings for next time
        Context.Settings.set("transcription_settings", settings.to_dict())
        Context.Settings.set("transcription_mode", mode.value)

        # Determine output filename (use original file name, not temp file name)
        output_name = self.selected_file.name if temp_file else None

        if mode == TranscriptionMode.ONLINE:
            api_key = SettingsHelper.get_stored_api_key()
            if not api_key:
                QMessageBox.warning(
                    self,
                    "No API Key",
                    "Please set your OpenAI API key in Settings before using online mode."
                )
                return
            self.worker = TranscriptionWorker(mode, settings, audio_file, api_key=api_key, output_name=output_name)
        else:
            # Check if any models are installed
            if self.model_combo.currentText() == "No models installed":
                QMessageBox.warning(
                    self,
                    "No Models",
                    "Please install a Whisper model in Settings before using offline mode."
                )
                return
            model_type = WhisperModel(self.model_combo.currentText())
            # Store selected model for next time
            Context.Settings.set("whisper_model", model_type.value)
            self.worker = TranscriptionWorker(mode, settings, audio_file, model_type=model_type, output_name=output_name)

        # Connect signals
        self.worker.finished.connect(self.on_transcription_complete)
        self.worker.error.connect(self.on_transcription_error)
        self.worker.progress.connect(self.on_progress_update)
        self.worker.device_detected.connect(self.on_device_detected)

        # Switch to progress view (index 1)
        self.action_stack.setCurrentIndex(1)
        self.status_label.setText("Initializing...")

        # Start worker thread
        self.worker.start()

    def on_progress_update(self, message: str):
        """Handle progress updates."""
        self.status_label.setText(message)

    def on_device_detected(self, device_info):
        """Handle device detection signal."""
        # Device info is now displayed via progress callback in status_label
        del device_info  # Unused - info is sent via progress callback

    def on_transcription_complete(self, output_path: Path):
        """Handle successful transcription completion."""
        # Switch back to button view (index 0)
        self.action_stack.setCurrentIndex(0)

        # Check if we should open the SRT editor
        open_editor = Context.Settings.get("open_srt_editor_when_done", True)

        if open_editor:
            # Open the SRT editor dialog
            editor = SrtEditorDialog(output_path, self)
            editor.exec()
        else:
            # Just show success message
            QMessageBox.information(
                self,
                "Transcription Complete",
                f"Transcription has been saved to:\n{output_path}"
            )

    def on_transcription_error(self, error_message: str):
        """Handle transcription errors."""
        # Switch back to button view (index 0)
        self.action_stack.setCurrentIndex(0)

        QMessageBox.critical(
            self,
            "Transcription Error",
            error_message
        )

    def resizeEvent(self, event):
        """Handle window resize events."""
        super().resizeEvent(event)

    def closeEvent(self, event):
        """Clean up temporary file when the application closes."""
        # Check if we should remove temp files
        remove_temp = Context.Settings.get("remove_temp_files_on_close", True)
        if remove_temp:
            self._cleanup_temp_file()
        event.accept()

    def _cleanup_temp_file(self):
        """Remove all temporary files created during this session."""
        for temp_file in self.temp_files:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception as e:
                    # Log error but don't prevent closing
                    print(f"Warning: Failed to clean up temporary file {temp_file}: {e}")
        self.temp_files.clear()

    def dragEnterEvent(self, event):
        """Handle drag enter events for drag and drop."""
        if event.mimeData().hasUrls():
            # Check if any of the URLs point to valid media files
            urls = event.mimeData().urls()
            if urls:
                file_path = Path(urls[0].toLocalFile())
                # Check if it's a supported media file
                supported_extensions = {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.wma',
                                       '.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv'}
                if file_path.suffix.lower() in supported_extensions:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        """Handle drop events for drag and drop."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                file_path = Path(urls[0].toLocalFile())
                # Validate and set the file
                supported_extensions = {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.wma',
                                       '.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv'}
                if file_path.exists() and file_path.suffix.lower() in supported_extensions:
                    self.selected_file = file_path
                    self.file_path_edit.setText(str(self.selected_file))
                    # Update transcribe button based on valid mode availability
                    self.update_ui_based_on_settings()
                    event.acceptProposedAction()
                else:
                    QMessageBox.warning(
                        self,
                        "Invalid File",
                        "Please drop a valid audio or video file."
                    )
                    event.ignore()
