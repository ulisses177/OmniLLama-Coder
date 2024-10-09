# canvas.py

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QSplitter, QLineEdit, QMenuBar, QAction, QSizePolicy, QPlainTextEdit,
    QToolBar, QFileDialog, QLabel
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QEvent
from PyQt5.QtGui import QIcon, QMovie, QSyntaxHighlighter, QTextCharFormat, QColor, QFont
import sys
import markdown
import json
import re
from coder_core import CoderCore

class Worker(QThread):
    finished = pyqtSignal(str, list)

    def __init__(self, user_query, chat_history, existing_code):
        super().__init__()
        self.user_query = user_query
        self.chat_history = chat_history
        self.existing_code = existing_code
        self.coder_core = CoderCore()

    def run(self):
        response, steps = self.coder_core.process_query(
            self.user_query, self.chat_history, self.existing_code
        )
        self.finished.emit(response, steps)

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.highlighting_rules = []

        # Palavras-chave do Python
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))
        keyword_format.setFontWeight(QFont.Bold)
        keywords = [
            "def", "class", "if", "elif", "else", "while", "for", "try",
            "except", "import", "from", "return", "with", "as", "pass",
            "break", "continue", "raise", "in", "is", "not", "and", "or"
        ]
        for word in keywords:
            pattern = r'\b' + word + r'\b'
            self.highlighting_rules.append((re.compile(pattern), keyword_format))

        # Strings
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#D69D85"))
        self.highlighting_rules.append((re.compile(r'\".*\"'), string_format))
        self.highlighting_rules.append((re.compile(r'\'.*\''), string_format))

        # Comentários
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))
        self.highlighting_rules.append((re.compile(r'#.*'), comment_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)

class ChatbotCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.coder_core = CoderCore()  # Instantiate CoderCore for processing queries
        self.undo_stack = []  # Stack to manage undo actions
        self.redo_stack = []  # Stack to manage redo actions
        self.updating_code = False  # Flag to indicate AI updates
        self.initUI()

    def initUI(self):
        # Main layout for the interface
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins to minimize spacing
        main_layout.setSpacing(0)  # Remove spacing between widgets
        self.setContentsMargins(0, 0, 0, 0)  # Ensure widget itself has no margins

        # Menu bar with settings, save, and load actions
        menubar = QMenuBar(self)
        settings_action = QAction("⚙️ Settings", self)
        save_action = QAction("💾 Salvar Sessão", self)
        load_action = QAction("📂 Carregar Sessão", self)
        menubar.addAction(settings_action)
        menubar.addAction(save_action)
        menubar.addAction(load_action)
        main_layout.addWidget(menubar)

        # Conectar ações de salvar e carregar
        save_action.triggered.connect(self.save_session)
        load_action.triggered.connect(self.load_session)

        # Toolbar with undo and redo buttons
        toolbar = QToolBar("Edit Tools")
        undo_action = QAction("⮪ Undo", self)
        undo_action.triggered.connect(self.undo_action)
        redo_action = QAction("⮫ Redo", self)
        redo_action.triggered.connect(self.redo_action)
        toolbar.addAction(undo_action)
        toolbar.addAction(redo_action)
        main_layout.addWidget(toolbar)

        # Splitter to separate chat and code editor areas
        splitter = QSplitter(Qt.Horizontal)
        splitter.setContentsMargins(0, 0, 0, 0)

        # Chat area (left side)
        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setPlaceholderText("Chat with the bot...")
        self.chat_area.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")
        splitter.addWidget(self.chat_area)

        # Code area (right side)
        self.code_area = QTextEdit()  # Use QTextEdit for better code formatting and syntax highlighting
        self.code_area.setPlaceholderText("Code editor...")
        self.code_area.setAcceptRichText(False)
        self.code_area.setStyleSheet("font-family: 'Courier New', monospace; font-size: 12pt; background-color: #1e1e1e; color: #ffffff;")
        self.code_area.textChanged.connect(self.track_code_changes)
        splitter.addWidget(self.code_area)

        # Aplicar destaque de sintaxe
        self.highlighter = PythonHighlighter(self.code_area.document())

        # Setting the stretch factor to make it look like the canvas you described
        splitter.setStretchFactor(0, 1)  # Chat area occupies one-third
        splitter.setStretchFactor(1, 2)  # Code area occupies two-thirds

        # Set anchors to minimize the blank area issue
        splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Combine the main content layout
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins to reduce spacing
        content_layout.setSpacing(0)  # No spacing for tight layout
        content_layout.addWidget(splitter)

        # Input area for sending messages
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(5, 5, 5, 5)
        input_layout.setSpacing(5)
        self.user_input = QPlainTextEdit()
        self.user_input.setFixedHeight(80)
        self.user_input.setPlaceholderText("Type your message here...")
        self.user_input.installEventFilter(self)  # Install event filter for key handling
        send_button = QPushButton("✈️")
        send_button.clicked.connect(self.sendMessage)

        # Arrange the input layout
        input_layout.addWidget(self.user_input)
        input_layout.addWidget(send_button)

        # Combine the layouts
        content_layout.addLayout(input_layout)
        main_layout.addLayout(content_layout)

        # Loading indicator
        self.loading_label = QLabel(self)
        self.loading_label.setVisible(False)
        loading_movie = QMovie("loading.gif")  # Certifique-se de ter um GIF de carregamento no diretório
        self.loading_label.setMovie(loading_movie)
        self.loading_label.setAlignment(Qt.AlignCenter)
        loading_movie.start()
        self.loading_label.setMovie(loading_movie)
        main_layout.addWidget(self.loading_label)

        # Set the main widget layout
        self.setLayout(main_layout)
        self.setWindowTitle("Chatbot Canvas Interface")
        self.setGeometry(100, 100, 1200, 800)
        self.applyTheme("dark")

    def eventFilter(self, source, event):
        if source is self.user_input and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ShiftModifier):
                self.sendMessage()
                return True
        return super().eventFilter(source, event)

    def sendMessage(self):
        # Get the user's input text
        user_text = self.user_input.toPlainText().strip()
        if user_text:
            # Display the user's message in the chat area
            user_message_html = f"<b>User:</b> {markdown.markdown(user_text)}"
            self.chat_area.append(user_message_html)

            # Mostrar o indicador de carregamento
            self.loading_label.setVisible(True)

            # Iniciar o worker para processar a consulta
            self.worker = Worker(user_text, self.get_chat_history(), self.code_area.toPlainText())
            self.worker.finished.connect(self.handle_response)
            self.worker.start()

            # Limpar o campo de entrada
            self.user_input.clear()
            self.chat_area.append("<b>Chatbot:</b> Processando sua solicitação...")

    def handle_response(self, response, steps):
        # Ocultar o indicador de carregamento
        self.loading_label.setVisible(False)

        # Remover a mensagem de carregamento
        chat_text = self.chat_area.toPlainText()
        chat_lines = chat_text.split('\n')
        if chat_lines and "Processando sua solicitação..." in chat_lines[-1]:
            self.chat_area.clear()
            for line in chat_lines[:-1]:
                self.chat_area.append(line)

        # Exibir a resposta da IA
        chatbot_message_html = f"<b>Chatbot:</b> {markdown.markdown(response)}"
        self.chat_area.append(chatbot_message_html)

        # Gerar ou atualizar a solução de código
        existing_code = self.code_area.toPlainText()
        final_answer = response
        code_solution = self.coder_core.create_code_solution_if_empty(
            self.worker.user_query, "\n".join(steps), final_answer, existing_code
        )
        if code_solution:
            self.undo_stack.append(existing_code)  # Save current state before updating
            self.redo_stack.clear()  # Clear redo stack after new action
            self.updating_code = True
            self.code_area.blockSignals(True)  # Avoid triggering textChanged
            self.code_area.setPlainText(code_solution)
            self.code_area.blockSignals(False)
            self.updating_code = False

    def track_code_changes(self):
        """
        Track code changes for undo and redo functionality.
        """
        if self.updating_code:
            return  # Ignore changes made by the AI
        current_code = self.code_area.toPlainText()
        if not self.undo_stack or self.undo_stack[-1] != current_code:
            self.undo_stack.append(current_code)
            # Limitar o tamanho da pilha para evitar consumo excessivo de memória
            if len(self.undo_stack) > 50:
                self.undo_stack.pop(0)

    def undo_action(self):
        """
        Undo the last change made in the code area.
        """
        if self.undo_stack:
            current_state = self.code_area.toPlainText()
            self.redo_stack.append(current_state)  # Save current state to redo stack
            previous_state = self.undo_stack.pop()  # Get the previous state
            self.updating_code = True
            self.code_area.blockSignals(True)  # Block signals to avoid triggering textChanged
            self.code_area.setPlainText(previous_state)
            self.code_area.blockSignals(False)
            self.updating_code = False

    def redo_action(self):
        """
        Redo the last undone change in the code area.
        """
        if self.redo_stack:
            current_state = self.code_area.toPlainText()
            self.undo_stack.append(current_state)  # Save current state to undo stack
            next_state = self.redo_stack.pop()  # Get the next state
            self.updating_code = True
            self.code_area.blockSignals(True)  # Block signals to avoid triggering textChanged
            self.code_area.setPlainText(next_state)
            self.code_area.blockSignals(False)
            self.updating_code = False

    def get_chat_history(self):
        """
        Retrieve the chat history as a list of messages.
        """
        chat_text = self.chat_area.toPlainText()
        return chat_text.split('\n') if chat_text else []

    def applyTheme(self, theme):
        if theme == "dark":
            self.setStyleSheet("background-color: #2e2e2e; color: #ffffff;")
            self.chat_area.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")
            self.code_area.setStyleSheet("background-color: #1e1e1e; color: #ffffff; font-family: 'Courier New', monospace; font-size: 12pt;")
            self.user_input.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")
        else:
            self.setStyleSheet("background-color: #ffffff; color: #000000;")
            self.chat_area.setStyleSheet("background-color: #f5f5f5; color: #000000;")
            self.code_area.setStyleSheet("background-color: #f5f5f5; color: #000000; font-family: 'Courier New', monospace; font-size: 12pt;")
            self.user_input.setStyleSheet("background-color: #ffffff; color: #000000;")

    def save_session(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Salvar Sessão", "", "JSON Files (*.json)", options=options
        )
        if file_path:
            session_data = {
                "chat_history": self.chat_area.toPlainText(),
                "code": self.code_area.toPlainText()
            }
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(session_data, f, ensure_ascii=False, indent=4)
                logging.info(f"Sessão salva em {file_path}")
                self.chat_area.append("<b>Chatbot:</b> Sessão salva com sucesso.")
            except Exception as e:
                logging.error(f"Erro ao salvar sessão: {str(e)}")
                self.chat_area.append("<b>Chatbot:</b> Erro ao salvar sessão.")

    def load_session(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Carregar Sessão", "", "JSON Files (*.json)", options=options
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                self.chat_area.setPlainText(session_data.get("chat_history", ""))
                self.code_area.setPlainText(session_data.get("code", ""))
                logging.info(f"Sessão carregada de {file_path}")
                self.chat_area.append("<b>Chatbot:</b> Sessão carregada com sucesso.")
            except Exception as e:
                logging.error(f"Erro ao carregar sessão: {str(e)}")
                self.chat_area.append("<b>Chatbot:</b> Erro ao carregar sessão.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    chatbot_canvas = ChatbotCanvas()
    chatbot_canvas.show()
    sys.exit(app.exec_())
