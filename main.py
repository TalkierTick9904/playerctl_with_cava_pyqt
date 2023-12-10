# комментарии "type: ignore" в конце некоторых строк нужны, чтобы у меня pyright не ругался
# на них не нужно обращать внимание

# библиотеки для взаимодейсвия с плеерами
import gi  # type: ignore
gi.require_version("Playerctl", "2.0")
from gi.repository import Playerctl, GLib  # type: ignore
# для скачивания обложки трека
import requests
# для копирования обложки трека
import shutil
# для запуска shell команд
import subprocess
# для одновременной работы циклов и приложения
import threading
# для записи конфига в временный файл
import tempfile
# для записи сохраненных треков в дб
import sqlite3
from PyQt5.QtWidgets import QComboBox, QLabel, QPushButton, QSlider, QFileDialog, QTableWidgetItem
from PyQt5.QtWidgets import QApplication, QMainWindow, QMenu, QAction, QTableWidget, QMessageBox
from PyQt5.QtCore import QDir, QTimer, Qt
from PyQt5.QtGui import QPainter, QIcon
import sys
import time

# конфиг для визуализатора звука
config = """
[general]
framerate = 60
bars = 10
[output]
method = raw
raw_target = /dev/stdout
data_format = ascii
ascii_max_range = 39
"""
# глобальная переменная для смены процесса, который отслеживает текущее время трека
event = True


class Cava:
    def __init__(self, parent):
        self.parent = parent

    def run(self):
        with tempfile.NamedTemporaryFile() as config_file:
            config_file.write(config.encode())
            config_file.flush()
            # запуск визуализатора звука
            process = subprocess.Popen(["cava", "-p", config_file.name], stdout=subprocess.PIPE)
            source = process.stdout
            while True:
                # построчное чтение потока значений столбцов визуализатора
                data = source.readline()  # type: ignore
                sample = list(map(int, data.decode("utf-8").split(";")[:-1]))
                # процесс слишком быстрый и после закрытия окна вызывает объект, который уже удален
                try:
                    self.parent.bars = sample
                    self.parent.update()
                except:
                    return


class Project(QMainWindow):
    def __init__(self):
        super().__init__()
        # размер окна не должен меняться, потому что все объекты привязаны к фиксированным координатам
        self.setFixedSize(720, 400)
        # переменная, содержащая значения столбцов визуализатора звука
        self.bars = [0, 0, 0, 0, 0, 0, 0]
        # переменная, помогающая отображать время в определенной точке при перемещении слайдера
        self.holding = False
        # переменная, помогающая сохранять и удалять треки из дб с помощью одной функции
        self.track_saved = False
        # меню расширенных настроек
        self.menu = QMenu(self)
        # опция, которая может включать или выключать always on top
        self.always_on_top_action = QAction("Always on top", self)
        self.always_on_top_action.setCheckable(True)
        self.always_on_top_action.triggered.connect(self.always_on_top)
        self.menu.addAction(self.always_on_top_action)
        # добавление разделителя
        self.menu.addSeparator()
        # опция, позволяющая сохранить обложку играющего трека
        self.save_art_action = QAction("Save current song art", self)
        self.save_art_action.setDisabled(True)
        self.save_art_action.triggered.connect(self.save_art)
        self.menu.addAction(self.save_art_action)
        # опция, позволяющая сохранить название играющего трека в буфер
        self.copy_title_action = QAction("Copy current song title", self)
        self.copy_title_action.setDisabled(True)
        self.copy_title_action.triggered.connect(self.copy_title)
        self.menu.addAction(self.copy_title_action)
        # опция, позволяющая сохранить имена авторов играющего трека в буфер
        self.copy_artists_action = QAction("Copy current song artists", self)
        self.copy_artists_action.setDisabled(True)
        self.copy_artists_action.triggered.connect(self.copy_artists)
        self.menu.addAction(self.copy_artists_action)
        # добавление разделителя
        self.menu.addSeparator()
        # опция, позволяющая открыть окно редактора дб
        self.edit_db_action = QAction("Edit saved tracks", self)
        self.edit_db_action.triggered.connect(self.edit_db)
        self.menu.addAction(self.edit_db_action)
        # опция, позволяющая сохранить содержимое дб в текстовый файл
        self.export_db_action = QAction("Export saved tracks", self)
        self.export_db_action.triggered.connect(self.export_db)
        self.menu.addAction(self.export_db_action)
        # кнопка расширенных настроек
        self.opts_btn = QPushButton(self)
        icon = QIcon.fromTheme("preferences-desktop-symbolic")
        self.opts_btn.setIcon(icon)
        self.opts_btn.resize(60, 40)
        self.opts_btn.move(10, 10)
        self.opts_btn.setMenu(self.menu)
        self.opts_btn.setFocusPolicy(Qt.NoFocus)  # type: ignore
        # меню со всеми доступными плеерами
        self.all_players = QComboBox(self)
        self.all_players.resize(630, 40)
        self.all_players.move(80, 10)
        self.all_players.setFocusPolicy(Qt.NoFocus)  # type: ignore
        # дефолтное значение, при котором окно меняет свой размер
        self.all_players.addItem("~")
        # название трека
        self.title = QLabel(self)
        self.title.resize(540, 40)
        self.title.move(10, 60)
        self.title.setAlignment(Qt.AlignLeft)  # type: ignore
        self.title.setStyleSheet("""
        font-size: 30px;
        font-weight: 600;
        """)
        # автор трека
        self.artist = QLabel(self)
        self.artist.resize(540, 40)
        self.artist.move(10, 110)
        self.artist.setAlignment(Qt.AlignLeft)  # type: ignore
        self.artist.setStyleSheet("""
        font-size: 25px;
        font-weight: 500;
        """)
        # время трека в данный момент
        self.time_now = QLabel(self)
        self.time_now.resize(50, 20)
        self.time_now.move(610, 370)
        self.time_now.setAlignment(Qt.AlignLeft)  # type: ignore
        # время трека
        self.time_end = QLabel(self)
        self.time_end.resize(50, 20)
        self.time_end.move(660, 370)
        self.time_end.setAlignment(Qt.AlignRight)  # type: ignore
        # знак, который отделяет время в данный момент от времени трека
        self.delimeter = QLabel("/", self)
        self.delimeter.resize(6, 20)
        self.delimeter.move(658, 370)
        self.delimeter.setAlignment(Qt.AlignCenter)  # type: ignore
        # обложка трека
        self.cover = QLabel(self)
        self.cover.resize(200, 200)
        self.cover.move(10, 161)
        self.cover.setStyleSheet("""
        border-radius: 6px;
        border-image: url('.cover.png') 0 0 0 0 stretch stretch;
        """)
        # слайдер, отвечающий за отображение таймлайна трека
        self.slider = QSlider(Qt.Horizontal, self)  # type: ignore
        self.slider.resize(590, 20)
        self.slider.move(10, 370)
        self.slider.sliderPressed.connect(self.slider_hold)
        self.slider.sliderReleased.connect(self.slider_release)
        self.slider.setFocusPolicy(Qt.NoFocus)  # type: ignore
        # кнопка, отвечающая за скип назад
        self.prev_btn = QPushButton(self)
        icon = QIcon.fromTheme("media-skip-backward")
        self.prev_btn.setIcon(icon)
        self.prev_btn.resize(40, 40)
        self.prev_btn.move(570, 60)
        self.prev_btn.clicked.connect(self.previous_track)
        self.prev_btn.setFocusPolicy(Qt.NoFocus)  # type: ignore
        # кнопка, отвечающая за изменение статуса воспроизведения
        self.play_pause_btn = QPushButton(self)
        self.play_pause_btn.resize(40, 40)
        self.play_pause_btn.move(620, 60)
        self.play_pause_btn.clicked.connect(self.playback_change)
        self.play_pause_btn.setFocusPolicy(Qt.NoFocus)  # type: ignore
        # кнопка, отвечающая за скип вперед
        self.next_btn = QPushButton(self)
        self.next_btn.resize(40, 40)
        self.next_btn.move(670, 60)
        icon = QIcon.fromTheme("media-skip-forward")
        self.next_btn.setIcon(icon)
        self.next_btn.clicked.connect(self.next_track)
        self.next_btn.setFocusPolicy(Qt.NoFocus)  # type: ignore
        # кнопка, отвечающая за сохранение или удаление трека из дб
        self.save_btn = QPushButton(self)
        icon = QIcon.fromTheme("add")
        self.save_btn.setIcon(icon)
        self.save_btn.resize(40, 40)
        self.save_btn.move(570, 110)
        self.save_btn.clicked.connect(self.save_to_db)
        self.save_btn.setFocusPolicy(Qt.NoFocus)  # type: ignore
        # кнопка, отвечающая за изменение статуса репита
        self.loop_btn = QPushButton(self)
        self.loop_btn.resize(40, 40)
        self.loop_btn.move(620, 110)
        self.loop_btn.clicked.connect(self.loop)
        self.loop_btn.setFocusPolicy(Qt.NoFocus)  # type: ignore
        # кнопка, отвечающая за перемешивание в плейлисте
        self.shuffle_btn = QPushButton(self)
        self.shuffle_btn.resize(40, 40)
        self.shuffle_btn.move(670, 110)
        self.shuffle_btn.clicked.connect(self.shuffle)
        self.shuffle_btn.setFocusPolicy(Qt.NoFocus)  # type: ignore
        # объект класса, отвечающего за управление плеерами
        self.player = PlayerManager(self)
        # способ подключить процесс менеджера плееров к процессу окна
        player_loop = QTimer()
        player_loop.timeout.connect(self.player.run)
        player_loop.start()
        # обновление данных при смене плеера
        self.all_players.currentIndexChanged.connect(self.player_change)
        # объект класса, отвечающего за визуализатор звука
        self.cava = Cava(self)
        # запуск визуализатора звука
        cava_thread = threading.Thread(target=self.cava.run)
        cava_thread.start()

    # переключение режима always on top
    def always_on_top(self, _):
        self.setWindowFlags(self.windowFlags() ^ Qt.WindowStaysOnTopHint)  # type: ignore
        self.show()

    # сохранение обложки трека
    def save_art(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save image", f"{QDir.homePath()}/cover.png", "Images (*.png)")
        if filename != "":
            shutil.copyfile(".art.png", filename)

    # копирование названия трека
    def copy_title(self):
        player = self.player.get_chosen_player()
        metadata = player.props.metadata  # type: ignore
        QApplication.clipboard().setText(metadata["xesam:title"])  # type: ignore

    # копирование авторов трека
    def copy_artists(self):
        player = self.player.get_chosen_player()
        metadata = player.props.metadata  # type: ignore
        QApplication.clipboard().setText(", ".join(metadata["xesam:artist"]))  # type: ignore

    # открытие окна редактирования дб
    def edit_db(self):
        edit_widget = EditWidget(self)
        edit_widget.show()

    # сохранение содержимого дб в текстовый файл
    def export_db(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Export saved tracks", f"{QDir.homePath()}/tracks.txt", "Text files (*.txt)")
        if filename == "":
            return
        con = sqlite3.connect("saved_tracks.sqlite")
        cur = con.cursor()
        res = cur.execute("SELECT * FROM Tracks").fetchall()
        with open(filename, "w", encoding="utf8") as file:
            file.write("Your saved tracks :D\nFormat: artists - title (art_url)\n")
            for line in res:
                title = line[1]
                artists = line[2]
                art_url = line[3]
                if title == "":
                    title = "Not found :("
                if artists == "":
                    artists = "Not found :("
                if art_url == "":
                    art_url = "No cover :("
                file.write(f"{artists} - {title} ({art_url})\n")
        con.close()
    # сохранение или удаление трека из дб, если он там есть
    def save_to_db(self):
        player = self.player.get_chosen_player()
        metadata = player.props.metadata  # type: ignore
        title, artist, art_url = "\"\"", "\"\"", "\"\""
        if "xesam:title" in metadata.keys():
            title = f"\"{metadata['xesam:title']}\""
        if "xesam:artist" in metadata.keys():
            artist = f"\"{', '.join(metadata['xesam:artist'])}\""
        if "mpris:artUrl" in metadata.keys():
            art_url = f"\"{metadata['mpris:artUrl']}\""
        if title == "\"\"" and artist == "\"\"":
            return
        con = sqlite3.connect("saved_tracks.sqlite")
        cur = con.cursor()
        if not self.track_saved:
            que = f"INSERT INTO Tracks(title, artist, art_url) VALUES ({title}, {artist}, {art_url})"
            icon = QIcon.fromTheme("remove")
            self.track_saved = True
        else:
            que = f"DELETE FROM Tracks WHERE title = {title} AND artist = {artist}"
            icon = QIcon.fromTheme("add")
            self.track_saved = False
        cur.execute(que)
        con.commit()
        con.close()
        self.save_btn.setIcon(icon)


    # смена статуса воспроизведения трека по кнопке
    def playback_change(self):
        player = self.player.get_chosen_player()
        # если плеер не поддерживает смену статуса воспроизведения, ничего не происходит
        try:
            player.play_pause()  # type: ignore
        except:
            pass

    # следующий трек в плейлисте по кнопке
    def next_track(self):
        player = self.player.get_chosen_player()
        # если трек не в плейлисте, то ничего не происходит
        try:
            player.next()  # type: ignore
        except:
            pass

    # предыдущий трек в плейлисте по кнопке
    def previous_track(self):
        player = self.player.get_chosen_player()
        # если трек не в плейлисте, то ничего не происходит
        try:
            player.previous()  # type: ignore
        except:
            pass

    # смена иконки на кнопке и статуса репита по нажатию
    def loop(self):
        player = self.player.get_chosen_player()
        player_name = player.props.player_name  # type: ignore
        # текущий статус репита (метод плеера не распознает репит, поставленный не через метод в этой программе, поэтому использую команду)
        status = subprocess.run(["playerctl", "-p", player_name, "loop"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        status = status.stdout.decode("utf-8").rstrip("\n")
        # если плеер не поддерживает репит, ничего не происходит
        if status == "None":
            try:
                player.set_loop_status(1)  # type: ignore
                icon = QIcon.fromTheme("media-playlist-repeat-song-symbolic")
                self.loop_btn.setIcon(icon)
            except:
                pass
            return
        elif status == "Track":
            try:
                player.set_loop_status(2)  # type: ignore
                icon = QIcon.fromTheme("media-playlist-repeat-symbolic")
                self.loop_btn.setIcon(icon)
            except:
                pass
            return
        try:
            player.set_loop_status(0)  # type: ignore
            icon = QIcon.fromTheme("media-playlist-no-repeat-symbolic")
            self.loop_btn.setIcon(icon)
        except:
            return

    # смена иконки на кнопке и статуса перемешивания в плейлисте по нажатию
    def shuffle(self):
        player = self.player.get_chosen_player()
        status = player.props.shuffle  # type: ignore
        # если перемешивание не поддерживается плеером, то ничего не происходит
        if status:
            try:
                player.set_shuffle(0)  # type: ignore
                icon = QIcon.fromTheme("media-playlist-no-shuffle-symbolic")
                self.shuffle_btn.setIcon(icon)
            except:
                pass
            return
        try:
            player.set_shuffle(1)  # type: ignore
            icon = QIcon.fromTheme("media-playlist-shuffle-symbolic")
            self.shuffle_btn.setIcon(icon)
        except:
            pass

    # текущее время трека
    def count(self, player_name):
        while True:
            # флаг для завершения процесса при определенных условиях
            global event
            if not event:
                break
            # условие при котором процесс запускаетсяя в первый раз
            if player_name == "":
                time.sleep(0.3)
                continue
            # если пользователь перемещает слайдер, то показывается время в точке, куда указал пользователь
            if self.holding:
                # форматирование числа секунд в читаемое время
                num = self.slider.value()
                hrs = num // 3600
                used = hrs * 3600
                mins = (num - used) // 60
                used += mins * 60
                secs = num - used
                if hrs < 10:
                    hrs = f"0{hrs}"
                if mins < 10:
                    mins = f"0{mins}"
                if secs < 10:
                    secs = f"0{secs}"
                # если трек не идет больше часа, можно не занимать лишнее место нулями
                if hrs == "00" and len(self.time_end.text()) == 5:
                    self.time_now.setText(f"{mins}:{secs}")
                else:
                    self.time_now.setText(f"{hrs}:{mins}:{secs}")
                time.sleep(0.3)
                continue
            # текущая позиция трека (метод объекта плеера не работает с перемоткой, а просто прибавляет единицы, поэтому использую команду)
            result = subprocess.run(["playerctl", "-p", player_name, "position"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = result.stdout.decode("utf-8").rstrip("\n")
            # если плеер не поддерживает вычисление позиции, то заменить все на нули
            if result == "":
                self.slider.resize(542, 20)
                self.time_now.resize(70, 20)
                self.time_now.move(562, 370)
                self.time_now.setText("00:00:00")
                self.delimeter.move(633, 370)
                self.time_end.resize(70, 20)
                self.time_end.move(640, 370)
                self.time_end.setText(f"00:00:00")
            else:
                # форматирование числа секунд в читаемое время
                num = int(float(result))
                hrs = num // 3600
                used = hrs * 3600
                mins = (num - used) // 60
                used += mins * 60
                secs = num - used
                if hrs < 10:
                    hrs = f"0{hrs}"
                if mins < 10:
                    mins = f"0{mins}"
                if secs < 10:
                    secs = f"0{secs}"
                # если трек не идет больше часа, можно не занимать лишнее место нулями
                if hrs == "00" and len(self.time_end.text()) == 5:
                    self.time_now.setText(f"{mins}:{secs}")
                else:
                    self.time_now.setText(f"{hrs}:{mins}:{secs}")
                self.slider.setValue(num)
            time.sleep(0.5)

    # изменение значения переменной, которая используется в других функциях
    def slider_hold(self):
        self.holding = True

    # изменение позиции трека после перемещения слайдера
    def slider_release(self):
        player = self.player.get_chosen_player()
        # если пользователь перемещал слайдер и текущий плеер пропал
        if player is None:
            self.holding = False
            return
        name, position = player.props.player_name, self.slider.value()
        subprocess.run(["playerctl", "-p", name, "position", str(position)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.holding = False

    # проверка статуса перемешивание при смене трека или плеера
    def check_shuffle(self, player):
        status = player.props.shuffle
        if status:
            icon = QIcon.fromTheme("media-playlist-shuffle-symbolic")
            self.shuffle_btn.setIcon(icon)
            return
        icon = QIcon.fromTheme("media-playlist-no-shuffle-symbolic")
        self.shuffle_btn.setIcon(icon)

    # проверка статуса репита при смене трека или плеера
    def check_loop(self, player_name):
        status = subprocess.run(["playerctl", "-p", player_name, "loop"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        status = status.stdout.decode("utf-8").rstrip("\n")
        if status == "Track":
            icon = QIcon.fromTheme("media-playlist-repeat-song-symbolic")
            self.loop_btn.setIcon(icon)
            return
        elif status == "Playlist":
            icon = QIcon.fromTheme("media-playlist-repeat-symbolic")
            self.loop_btn.setIcon(icon)
            return
        icon = QIcon.fromTheme("media-playlist-no-repeat-symbolic")
        self.loop_btn.setIcon(icon)

    # обновление данных трека при смене плеера
    def player_change(self):
        player = self.player.get_chosen_player()
        if player is None:
            # если выбрано дефолтное значение, запускается функция без метаданных плеера
            self.player.on_metadata_changed(None, None)
            return
        self.player.on_metadata_changed(player, player.props.metadata)  # type: ignore

    # отрисовка визуализатора звука
    def paintEvent(self, _):
        p = QPainter()
        p.begin(self)
        p.setBrush(self.palette().windowText().color())
        for i, bar in enumerate(self.bars):
            p.drawRect(220 + i * 50, 360, 40, -5 + -bar * 5)
        p.end()

    # определение горячих клавиш
    def keyPressEvent(self, event):
        player = self.player.get_chosen_player()
        if player is None:
            return
        if event.key() == Qt.Key_S:  # type: ignore
            self.shuffle_btn.click()
        if event.key() == Qt.Key_R:  # type: ignore
            self.loop_btn.click()
        if event.key() == Qt.Key_Space:  # type: ignore
            self.play_pause_btn.click()
        if event.key() == Qt.Key_Greater:  # type: ignore
            self.next_btn.click()
        if event.key() == Qt.Key_Less:  # type: ignore
            self.prev_btn.click()
        if event.key() == Qt.Key_F:  # type: ignore
            self.save_btn.click()
        if event.key() == Qt.Key_Right:  # type: ignore
            subprocess.run(["playerctl", "-p", player.props.player_name, "position", "5+"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if event.key() == Qt.Key_Left:  # type: ignore
            subprocess.run(["playerctl", "-p", player.props.player_name, "position", "5-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

class EditWidget(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent  # type: ignore
        self.setFixedSize(600, 375)
        # переменная, которая помогает отслеживать изменения в таблице
        self.modified = False
        # подключение к дб с сохраненными треками
        self.con = sqlite3.connect("saved_tracks.sqlite")
        # таблица, отображающая дб
        self.table = QTableWidget(self)
        self.table.resize(600, 300)
        self.table.move(0, 60)
        self.table.itemChanged.connect(self.item_changed)
        # кнопка удаления выбранных треков
        self.delete_btn = QPushButton("Delete", self)
        self.delete_btn.resize(100, 40)
        self.delete_btn.move(10, 10)
        self.delete_btn.clicked.connect(self.delete_items)
        icon = QIcon.fromTheme("trash-full")
        self.delete_btn.setIcon(icon)
        # кнопка обновления содержания таблицы
        self.update_btn = QPushButton("Update", self)
        self.update_btn.resize(100, 40)
        self.update_btn.move(120, 10)
        self.update_btn.clicked.connect(self.load_db)
        icon = QIcon.fromTheme("gtk-refresh")
        self.update_btn.setIcon(icon)
        # кнопка сохранения изменений в таблице
        self.save_btn = QPushButton("Save", self)
        self.save_btn.resize(100, 40)
        self.save_btn.move(380, 10)
        self.save_btn.clicked.connect(self.save_items)
        icon = QIcon.fromTheme("gtk-save")
        self.save_btn.setIcon(icon)
        # кнопка выхода из режима редактирования дб
        self.exit_btn = QPushButton("Exit", self)
        self.exit_btn.resize(100, 40)
        self.exit_btn.move(490, 10)
        self.exit_btn.clicked.connect(self.close)  # type: ignore
        icon = QIcon.fromTheme("exit")
        self.exit_btn.setIcon(icon)
        # загрузка содержимого дб в таблицу
        self.load_db()

    # действия при изменении значений в таблице
    def item_changed(self):
        self.modified = True

    # загрузка содержимого дб в таблицу
    def load_db(self):
        # если значения в таблице были изменены и не сохранены, появится предупреждение
        if self.modified:
            valid = QMessageBox.question(self, "", "Reset changed data?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if valid == QMessageBox.No:
                return
        cur = self.con.cursor()
        result = cur.execute("SELECT * FROM Tracks").fetchall()
        self.table.clear()
        self.table.setRowCount(len(result))
        self.table.setColumnCount(4)
        for i, elem in enumerate(result):
            for j, val in enumerate(elem):
                self.table.setItem(i, j, QTableWidgetItem(str(val)))
        self.modified = False

    # сохранение измененных данных в дб
    def save_items(self):
        # если с последнего сохранения ничего не изменилось, ничего не произойдет
        if not self.modified:
            self.statusBar().showMessage("Nothing changed")  # type: ignore
            return
        ids, titles, artists, art_urls = [], [], [], []
        for i in range(self.table.rowCount()):
            # если пользователь неправильно указал id, изменения не сохранятся
            if not self.table.item(i, 0).text().isdigit():  # type: ignore
                self.statusBar().showMessage("Id can only be a number")  # type: ignore
                return
            ids.append(int(self.table.item(i, 0).text()))  # type: ignore
            titles.append(f"\"{self.table.item(i, 1).text()}\"")  # type: ignore
            artists.append(f"\"{self.table.item(i, 2).text()}\"")  # type: ignore
            art_urls.append(f"\"{self.table.item(i, 3).text()}\"")  # type: ignore
        tmp = []
        for i in range(self.table.rowCount()):
            tmp.append([ids[i], titles[i], artists[i], art_urls[i]])
        tmp.sort(key=lambda x: x[0])
        ids = list(map(str, ids))
        elems = []
        for i in tmp:
            elems.append(f"({i[0]}, {i[1]}, {i[2]}, {i[3]})")
        # предупреждение о том, что данные в дб будут перезаписаны
        valid = QMessageBox.question(self, "", "Overwrite existing data?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if valid == QMessageBox.No:
            return
        cur = self.con.cursor()
        que = f"DELETE FROM Tracks WHERE id IN ({', '.join(ids)})"
        cur.execute(que)
        que = f"INSERT INTO Tracks VALUES {', '.join(elems)}"
        cur.execute(que)
        self.con.commit()
        self.statusBar().showMessage("")  # type: ignore
        self.modified = False
        # обновление статуса сохранения трека
        player = self.parent.player.get_chosen_player()
        if player is not None:
            self.parent.player.on_metadata_changed(player, player.props.metadata)

    # удаление выбранных элементов из дб
    def delete_items(self):
        rows = list(set([i.row() for i in self.table.selectedItems()]))
        # если ничего не выбрано, дб не изменится
        if not rows:
            self.statusBar().showMessage("Nothing to delete")  # type: ignore
            return
        # загрузка данных из дб в таблицу, чтобы избежать ошибки при несохраненных изменениях
        self.load_db()
        ids = [self.table.item(i, 0).text() for i in rows]  # type: ignore
        if len(ids) == 1:
            msg = f"Delete element with id {ids[0]}?"
        else:
            msg = f"Delete elements with id {', '.join(ids)}?"
        # предупреждение об удалении данных из дб
        valid = QMessageBox.question(self, "", msg,
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if valid == QMessageBox.No:
            return
        cur = self.con.cursor()
        que = f"DELETE FROM Tracks WHERE id IN ({', '.join(ids)})"
        cur.execute(que)
        self.con.commit()
        self.statusBar().showMessage("")  # type: ignore
        player = self.parent.player.get_chosen_player()
        # обновление статуса сохранения трека
        if player is not None:
            self.parent.player.on_metadata_changed(player, player.props.metadata)

    # переопределение ивента закрытия окна, чтобы не потерять измененные данные
    def closeEvent(self, event):
        if not self.modified:
            event.accept()
        else:
            # предупреждение о потере изменений при выходе
            valid = QMessageBox.question(self, "", "Exit without saving?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if valid == QMessageBox.Yes:
                self.modified = False
                event.accept()
            else:
                event.ignore()


class PlayerManager:
    def __init__(self, parent):
        # создание объекта менеджера плееров
        self.manager = Playerctl.PlayerManager()
        # создание объекта цикла, позволяющего отслеживать плееры
        self.loop = GLib.MainLoop()
        # подключение сигналов менеджера к определенным функциям
        self.manager.connect("name-appeared", lambda *args: self.on_player_appeared(*args))
        self.manager.connect("player-vanished", lambda *args: self.on_player_vanished(*args))
        # определение объекта приложения
        self.parent = parent
        # запуск процесса определения текущего времени трека
        self.dum = threading.Thread(target=self.parent.count, args=("",))
        self.dum.start()
        # переменная, отвечающая за данные предыдущего плеера
        self.prev = [None, "", ""]
        self.init_players()

    # инициализации доступных плееров
    def init_players(self):
        for player in self.manager.props.player_names:
            self.init_player(player)

    # инициализация нового плеера
    def init_player(self, player):
        # добавления названия в выпадающее меню
        self.parent.all_players.addItem(player.name)
        # подключение сигналов плеера к определенным функциям
        player = Playerctl.Player.new_from_name(player)
        player.connect("metadata", self.on_metadata_changed, None)
        player.connect("playback-status", self.on_playback_status_changed, None)
        self.manager.manage_player(player)
        self.on_metadata_changed(player, player.props.metadata)

    # возвращение списка доступных плееров
    def get_players(self):
        return self.manager.props.players

    # возвращение объекта плеера, выбранного через выпадающее меню
    def get_chosen_player(self):
        players = self.get_players()
        chosen_name = self.parent.all_players.currentText()
        for player in players:
            if player.props.player_name == chosen_name:
                return player
        return None

    # вывод данных текущего трека на экран
    def write_output(self, title, artists, art):
        # пытается скачать обложку, если она есть и заменяет текущую картинку
        if art[0]:
            try:
                response = requests.get(art[1])
                open(".art.png", "wb").write(response.content)
                self.parent.cover.setStyleSheet("""
                border-radius: 6px;
                border-image: url('.art.png') 0 0 0 0 stretch stretch;
                """)
            except:
                self.parent.cover.setStyleSheet("""
                border-radius: 6px;
                border-image: url('.cover.png') 0 0 0 0 stretch stretch;
                """)
                # выключение возможности сохранять обложку если не удалось ее скачать
                self.parent.save_art_action.setDisabled(True)
        else:
            self.parent.cover.setStyleSheet("""
            border-radius: 6px;
            border-image: url('.cover.png') 0 0 0 0 stretch stretch;
            """)
        # меняет текст названия и исполнителя
        self.parent.title.setText(title)
        self.parent.artist.setText(artists)

    # действия при смене статуса воспроизведения плеера
    def on_playback_status_changed(self, player, status, _=None):
        # если это не выбранный плеер, то ничего не происходит
        current_playing = self.get_chosen_player()
        if current_playing is None:
            return
        if current_playing.props.player_name != player.props.player_name:  # type: ignore
            return
        # изменение иконки на кнопке
        if status == Playerctl.PlaybackStatus(1):
            icon = QIcon.fromTheme("media-play")
        else:
            icon = QIcon.fromTheme("media-pause")
        self.parent.play_pause_btn.setIcon(icon)

    # действия при смене метаданных плеера
    def on_metadata_changed(self, player, metadata, _=None):
        global event
        # изменение размера, если выбирается любой плеер
        self.parent.setFixedSize(720, 400)
        current_playing = self.get_chosen_player()
        if current_playing is None:
            # замена переменных, если выбирается дефолтное значение плеера
            artists = ""
            title = ""
            art = [False, ""]
            # выключение возможности сохранять обложку при смене трека или плеера
            self.parent.save_art_action.setDisabled(True)
            # выключение возможности скопировать название при смене трека или плеера
            self.parent.copy_title_action.setDisabled(True)
            # выключение возможности скопировать автора при смене трека или плеера
            self.parent.copy_artists_action.setDisabled(True)
            self.prev = [None, title, artists]
            event = False
            self.write_output(title, artists, art)
            # изменение размера окна, так как показывать больше нечего
            self.parent.setFixedSize(720, 60)
            return
        # если это не выбранный плеер, то ничего не происходит
        elif current_playing.props.player_name != player.props.player_name:  # type: ignore
            return
        # подстановка названия трека и исполнителя из метаданных плеера
        artists = "Not found :("
        title = "Not found :("
        if "xesam:artist" in metadata.keys():
            tmp = metadata["xesam:artist"]
            if len(tmp) > 0 and tmp != [""]:
                artists = ", ".join(tmp)
        if "xesam:title" in metadata.keys():
            tmp = metadata["xesam:title"]
            if len(tmp) > 0 and tmp != [""]:
                title = tmp
        # если функция вызвана изменением статуса воспроизведения трека, то обновится только статус сохранения трека,
        # чтобы не сбивать визуализатор звука и лишний раз не скачивать обложку
        if [player, title, artists] == self.prev:
            tmp_title = f"\"{title}\""
            tmp_artists = f"\"{artists}\""
            con = sqlite3.connect("saved_tracks.sqlite")
            cur = con.cursor()
            que = f"SELECT * FROM Tracks WHERE title = {tmp_title} AND artist = {tmp_artists}"
            res = cur.execute(que).fetchone()
            if res:
                self.parent.track_saved = True
                icon = QIcon.fromTheme("remove")
            else:
                self.parent.track_saved = False
                icon = QIcon.fromTheme("add")
            con.close()
            self.parent.save_btn.setIcon(icon)
            return
        # выключение возможности сохранять обложку при смене трека или плеера
        self.parent.save_art_action.setDisabled(True)
        # выключение возможности скопировать название при смене трека или плеера
        self.parent.copy_title_action.setDisabled(True)
        # выключение возможности скопировать автора при смене трека или плеера
        self.parent.copy_artists_action.setDisabled(True)
        # сохранение ссылки на обложку, если она есть в метаданных
        if "mpris:artUrl" in metadata.keys():
            art = [True, metadata["mpris:artUrl"]]
            self.parent.save_art_action.setEnabled(True)
        else:
            art = [False, ""]
        if title != "Not found :(":
            self.parent.copy_title_action.setEnabled(True)
        if artists != "Not found :(":
            self.parent.copy_artists_action.setEnabled(True)
        # повторный вызов фунцкии, отвечающей за действия при изменении статуса воспроизведения трека,
        # чтобы избежать неправильную иконку на кнопке
        status = player.props.playback_status
        self.on_playback_status_changed(player, status)
        # смена иконок на кнопках репита и перемешивания по необходимости
        self.parent.check_shuffle(player)
        self.parent.check_loop(player.props.player_name)
        # выведение данных трека на экран
        self.write_output(title, artists, art)
        # проверка статуса сохранения трека
        tmp_title = f"\"{title}\""
        tmp_artists = f"\"{artists}\""
        con = sqlite3.connect("saved_tracks.sqlite")
        cur = con.cursor()
        que = f"SELECT * FROM Tracks WHERE title = {tmp_title} AND artist = {tmp_artists}"
        res = cur.execute(que).fetchone()
        if res:
            self.parent.track_saved = True
            icon = QIcon.fromTheme("remove")
        else:
            self.parent.track_saved = False
            icon = QIcon.fromTheme("add")
        con.close()
        self.parent.save_btn.setIcon(icon)
        # перезапуск процесса отслеживания текущего времени трека при смене плеера
        if player != self.prev[0]:
            event = False
            self.dum.join()
            event = True
            self.dum = threading.Thread(target=self.parent.count, args=(player.props.player_name,))
            self.dum.start()
        # вывод конечного времени трека на экран, если она есть в метаданных 
        if "mpris:length" in metadata.keys():
            # форматирование числа секунд в читаемое время
            lenght = int(str(metadata["mpris:length"])[:-6])
            hrs = lenght // 3600
            used = hrs * 3600
            mins = (lenght - used) // 60
            used += mins * 60
            secs = lenght - used
            if hrs < 10:
                hrs = f"0{hrs}"
            if mins < 10:
                mins = f"0{mins}"
            if secs < 10:
                secs = f"0{secs}"
            # если трек не идет больше часа, можно не занимать лишнее место нулями
            if hrs == "00":
                self.parent.slider.resize(590, 20)
                self.parent.time_now.resize(50, 20)
                self.parent.time_now.move(610, 370)
                self.parent.delimeter.move(658, 370)
                self.parent.time_end.resize(50, 20)
                self.parent.time_end.move(660, 370)
                self.parent.time_end.setText(f"{mins}:{secs}")
            else:
                self.parent.slider.resize(542, 20)
                self.parent.time_now.resize(70, 20)
                self.parent.time_now.move(562, 370)
                self.parent.delimeter.move(633, 370)
                self.parent.time_end.resize(70, 20)
                self.parent.time_end.move(640, 370)
                self.parent.time_end.setText(f"{hrs}:{mins}:{secs}")
        else:
            lenght = 0
        # изменение количества значений, принимаемых слайдером в зависимости от длины трека 
        self.parent.slider.setRange(0, lenght)
        # запись данных в специальную переменную, чтобы при следующем вызове использовались предыдушие значения
        self.prev = [player, title, artists]

    # инициализация нового плеера при его появлении
    def on_player_appeared(self, _, player):
        self.init_player(player)

    # удаление названия плеера из выпадающего меню при пропаже плеера
    # и замена на дефолтное значение, если пропал текущий плеер
    def on_player_vanished(self, _, player):
        current_name = self.parent.all_players.currentText()
        name = player.props.player_name
        for ind in range(self.parent.all_players.count()):
            if self.parent.all_players.itemText(ind) == name:
                self.parent.all_players.removeItem(ind)
                if name == current_name:
                    self.parent.all_players.setCurrentText("~")
                return

    # запуск цикла менеджера плееров
    def run(self):
        self.loop.run()


def except_hook(cls, exception, traceback):
    sys.__excepthook__(cls, exception, traceback)


# запуск приложения
def main():
    global event
    app = QApplication(sys.argv)
    ex = Project()
    ex.show()
    sys.excepthook = except_hook
    app.exec()
    # смена значения переменной для закрытия цикла отслеживания текущего времени трека
    event = False
    sys.exit()


if __name__ == "__main__":
    main()
