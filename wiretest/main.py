#好代码
import sys
import csv
import matplotlib.pyplot as plt
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget,QTextEdit
from PyQt5.QtCore import QThread, pyqtSignal

import socket
import struct

class TcpThread(QThread):
    data_received = pyqtSignal(list)  # 仅通知数据接收，不触发绘图
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.client_socket = None
        self.server_socket = None
        self.size = 0
        self.data_buffer = []  # 修改这里以缓存接收到的所有数据

    def run(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind(('0.0.0.0', 8080))
            self.server_socket.listen(1)
            self.log_signal.emit("Listening on port 8080...")
            while self.running:
                self.client_socket, addr = self.server_socket.accept()
                self.log_signal.emit(f"Connection from: {addr}")
                self.handle_connection()
        except Exception as e:
            self.log_signal.emit(f"Error occurred: {e}")

    def handle_connection(self):
        state = 'WAIT_CMD'
        num = 0
        while self.running:
            if state == 'WAIT_CMD':
                header = self.client_socket.recv(1024).decode('utf-8').strip()
                if header == "prepared":
                    self.client_socket.sendall('1'.encode())
                    self.log_signal.emit("Sent: ok")
                elif header == "succeed":
                    self.log_signal.emit("Communication is established, waiting for size...")
                    self.client_socket.sendall('2'.encode())
                elif header == "sizecoming":
                    self.log_signal.emit("Size is coming...")
                    state = 'receive_size'
            elif state == 'receive_size':
                size_data = self.client_socket.recv(1)
                if len(size_data) == 1:
                    if size_data[0] == 0:
                        state = 'await_start'
                    else :
                        self.size = size_data[0]
                        self.client_socket.sendall('3'.encode())
                        self.log_signal.emit(f"Length of the array received: {self.size}")
            elif state == 'await_start':
                self.log_signal.emit("Start command sent, initiating data reception...")
                self.client_socket.sendall('4'.encode())
                header = self.client_socket.recv(1024).decode('utf-8').strip()
                if header == "ready":
                    state = 'receive_data'
            elif state == 'receive_data':
                self.log_signal.emit(f"data_number: {num}")
                num += 1
                self.receive_data(self.size)

    def receive_data(self, size):
        expected_bytes = size * 8
        received_data = b''


        while len(received_data) < expected_bytes and self.running:
            try:
                chunk = self.client_socket.recv(expected_bytes - len(received_data))
                if not chunk:
                    break
                received_data += chunk
            except Exception as e:
                break

        if len(received_data) == expected_bytes:
            try:
                data = struct.unpack('<' + 'd' * size, received_data)
                self.data_buffer.append(data)  # 缓存解包后的数据
            except Exception as e:
                self.log_signal.emit(f"Error during data reception or unpacking: {e}")

    def stop(self):
        self.running = False
        try:
            if self.client_socket:
                self.client_socket.shutdown(socket.SHUT_RDWR)
                self.client_socket.close()
        except Exception as e:
            pass
        try:
            if self.server_socket:
                self.server_socket.close()
        except Exception as e:
            pass
        self.quit()
        self.wait()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.tcp_thread = TcpThread()
        self.tcp_thread.log_signal.connect(self.log_message)
        self.init_ui()
        self.tcp_thread.start()

    def init_ui(self):
        self.setWindowTitle('Real-time Data Plot')
        self.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()  # 创建 QVBoxLayout 实例

        self.log_editor = QTextEdit()
        self.log_editor.setReadOnly(True)  # 设置为只读
        layout.addWidget(self.log_editor)

        self.stop_button = QPushButton('Stop Receiving Data and save data')
        self.stop_button.clicked.connect(self.on_stop_receiving)
        layout.addWidget(self.stop_button)  # 添加按钮到布局

        self.plot_button = QPushButton('plot')
        self.plot_button.clicked.connect(self.plot)
        layout.addWidget(self.plot_button)  # 添加按钮到布局

        self.reset_button = QPushButton('Reset')
        self.reset_button.clicked.connect(self.on_reset)
        layout.addWidget(self.reset_button)

        self.container = QWidget()  # 创建一个容器 QWidget
        self.container.setLayout(layout)  # 将布局设置到容器中
        self.setCentralWidget(self.container)  # 将容器设置为窗口的中央小部件

    def log_message(self, message):
        self.log_editor.append(message)  # 在 QTextEdit 控件中追加消息

    def on_stop_receiving(self):
        self.tcp_thread.stop()  # 停止接收数据
        self.save_data_to_csv()  # 保存数据到CSV

    def plot(self):

        self.plot_csv_to_photo()  # 绘图

    def save_data_to_csv(self):
        filename = "received_data.csv"
        with open(filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            for data_set in self.tcp_thread.data_buffer:
                writer.writerow(data_set)
        self.log_message(f"Data saved to {filename}")

    def plot_csv_to_photo(self):
        filename = "received_data.csv"
        data = []
        try:
            with open(filename, mode='r', newline='') as file:
                reader = csv.reader(file)
                for row in reader:
                    data.append([float(x) for x in row])  # 假设每行都是数值数据

            # 数据转置，使每列变为一个独立的数据系列
            data = list(zip(*data))

            # 确定子图布局
            num_series = len(data)
            num_cols = 3  # 每行最多三个子图
            num_rows = (num_series + num_cols - 1) // num_cols  # 计算需要多少行

            plt.figure(figsize=(15, 5 * num_rows))  # 动态调整整个图形的大小

            # 为每个数据系列创建一个子图
            for index, series in enumerate(data):
                ax = plt.subplot(num_rows, num_cols, index + 1)
                ax.plot(series)
                ax.set_title(f'Series {index}')
                ax.set_xlabel('Index')
                ax.set_ylabel('Value')

            plt.tight_layout()  # 调整子图布局，防止重叠
            plt.savefig('plots.png')  # 将所有子图保存为单个图片文件
            plt.close()

            self.log_message("All plots finished and saved to 'plots.png'.")
        except Exception as e:
            self.log_message(f"Error reading from CSV or plotting: {e}")

    def on_reset(self):
        # 停止并清理当前线程
        self.tcp_thread.stop()
        self.tcp_thread.wait()

        # 清空日志和数据缓冲区
        self.log_editor.clear()
        self.tcp_thread.data_buffer.clear()

        # 重新创建并启动新的线程
        self.tcp_thread = TcpThread()
        self.tcp_thread.log_signal.connect(self.log_message)
        self.tcp_thread.start()

        # 记录重置操作
        self.log_message("Application has been reset.")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
