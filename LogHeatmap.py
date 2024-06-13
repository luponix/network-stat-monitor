import os
import re
import sys
import time
from datetime import datetime, timezone
import pyqtgraph as pg
from PyQt5 import QtGui, QtCore
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget, QPushButton, QLabel, QMainWindow, QGridLayout, QFrame
import numpy as np


directory = ""#'./path/to/directory'
pattern = re.compile(r'.*_log\.txt$')

selected_log = -1
selected_year = -1
selected_month = -1

class MainWindow(QMainWindow):
    instance = None

    def __init__(self):
        super().__init__()
        MainWindow.instance = self
        self.setStyleSheet("background-color: black;")
        self.setWindowTitle("Log Heatmap")
        self.setGeometry(100, 100, 750, 1000)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        self.file_label = QLabel("")
        self.file_label.setFont(QtGui.QFont('Arial', 16))
        self.file_label.setAlignment(QtCore.Qt.AlignCenter)
        self.file_label.setStyleSheet("color: white; background-color: black;")

        self.time_label = QLabel("")
        self.time_label.setFont(QtGui.QFont('Arial', 16))
        self.time_label.setAlignment(QtCore.Qt.AlignCenter)
        self.time_label.setStyleSheet("color: white; background-color: black;")

        self.plot_widget = pg.PlotWidget()
        layout.addWidget(self.plot_widget)

        self.plot_widget.setTitle("")
        self.plot_widget.setLabel('left', 'Days')
        self.plot_widget.setLabel('bottom', 'Hours')

        self.plot_widget.invertY(True)
        self.plot_widget.setMouseEnabled(x=False, y=False)
        self.plot_widget.showGrid(x=True, y=True)

        self.image_item = None
        global selected_log, selected_year, selected_month, logs
        for key in logs.keys():
            selected_log = key
            break
        self.set_latest_data_point_as_selection()
        self.draw_month()
        self.plot_widget.addItem(self.image_item)

        grid_layout = QGridLayout()


        grid_layout.addWidget(self.file_label, 0, 0)
        grid_layout.addWidget(self.time_label, 0, 1)

        line1 = QFrame()
        line1.setFrameShape(QFrame.HLine)
        line1.setFrameShadow(QFrame.Sunken)
        line1.setStyleSheet("color: white; background-color: grey;")  # Change color to white
        grid_layout.addWidget(line1, 1, 0, 1, 2)

        self.previous_month_button = QPushButton("previous month")
        self.previous_month_button.setStyleSheet("background-color: grey; color: white;")
        grid_layout.addWidget(self.previous_month_button, 2, 0)

        self.next_month_button = QPushButton("next month")
        self.next_month_button.setStyleSheet("background-color: grey; color: white;")
        grid_layout.addWidget(self.next_month_button, 2, 1)

        self.last_log_button = QPushButton("last log")
        self.last_log_button.setStyleSheet("background-color: grey; color: white;")
        grid_layout.addWidget(self.last_log_button, 3, 0)

        self.next_log_button = QPushButton("next log")
        self.next_log_button.setStyleSheet("background-color: grey; color: white;")
        grid_layout.addWidget(self.next_log_button, 3, 1)
        layout.addLayout(grid_layout)

        self.next_month_button.clicked.connect(self.draw_next_month)
        self.previous_month_button.clicked.connect(self.draw_previous_month)
        self.next_log_button.clicked.connect(self.get_next_log)
        self.last_log_button.clicked.connect(self.get_previous_log)

    def get_next_log(self):
        global selected_log, selected_year
        next_key = self.get_next_key()
        if next_key is not None:
            selected_log = next_key
            if selected_year in logs[next_key].years is None:
                self.set_latest_data_point_as_selection()
            self.draw_month()

    def get_previous_log(self):
        global selected_log, selected_year
        next_key = self.get_previous_key()
        if next_key is not None:
            selected_log = next_key
            if selected_year in logs[next_key].years is None:
                self.set_latest_data_point_as_selection()
            self.draw_month()

    def get_next_key(self):
        global selected_log
        keys = list(logs.keys())
        try:
            current_index = keys.index(selected_log)
            next_index = (current_index + 1) % len(keys)
            return keys[next_index]
        except ValueError:
            return None  # Current key not found

    def get_previous_key(self):
        global selected_log
        keys = list(logs.keys())
        try:
            current_index = keys.index(selected_log)
            previous_index = (current_index - 1) % len(keys)
            return keys[previous_index]
        except ValueError:
            return None  # Current key not found

    def set_latest_data_point_as_selection(self):
        global selected_log, selected_year, selected_month, logs
        latest_year = -1
        for key in logs[selected_log].years.keys():
            if key > latest_year:
                latest_year = key

        latest_month_with_data = 0
        for key in logs[selected_log].years[latest_year].months.keys():
            if len(logs[selected_log].years[latest_year].months[key].days) > 0 and key > latest_month_with_data:
                latest_month_with_data = key
        selected_year = latest_year
        selected_month = latest_month_with_data
        #print(latest_month_with_data)

    def month_number_to_name(self, month_num):
        month_names = {
            1: "January",
            2: "February",
            3: "March",
            4: "April",
            5: "May",
            6: "June",
            7: "July",
            8: "August",
            9: "September",
            10: "October",
            11: "November",
            12: "December"
        }
        if month_num in month_names:
            return month_names[month_num]
        else:
            return "Invalid month number"

    def draw_next_month(self):
        global selected_log, selected_year, selected_month, logs
        if selected_month + 1 <= 12:
            selected_month += 1
            self.draw_month()
            return
        # we reached the end of the year. test wether there is a new lowest but higher year. i should have made years a list...
        next_higher_year = min(filter(lambda x: x > selected_year, logs[selected_log].years.keys()), default=None)
        if next_higher_year is not None:
            selected_year = next_higher_year
            selected_month = 1

    def draw_previous_month(self):
        global selected_log, selected_year, selected_month, logs
        if selected_month - 1 >= 1:
            selected_month -= 1
            self.draw_month()
            return
        # we reached the end of the year. test wether there is a new highest but lower year
        next_previous_year = max(filter(lambda x: x < selected_year, logs[selected_log].years.keys()), default=None)
        if next_previous_year is not None:
            selected_year = next_previous_year
            selected_month = 12


    def draw_month(self):
        # check if the selected month exists
        global selected_log, selected_year, selected_month, logs
        if selected_log not in logs.keys() or selected_year not in logs[selected_log].years:
            print("selected log or selected year does not exist")
            return

        if logs[selected_log].years[selected_year].months[selected_month].image_data is None:
            logs[selected_log].years[selected_year].months[selected_month].create_month_image()

        if MainWindow.instance.image_item is None:
            MainWindow.instance.image_item = pg.ImageItem(image=logs[selected_log].years[selected_year].months[selected_month].image_data)
        else:
            MainWindow.instance.image_item.setImage(image=logs[selected_log].years[selected_year].months[selected_month].image_data)
        MainWindow.instance.plot_widget.getAxis('left').setTicks(
            [[(i, str(i)) for i in range(logs[selected_log].years[selected_year].months[selected_month].amt_of_days)]])
        label_text = selected_log
        if ip_name_dict[logs[selected_log].filename] is not None:
            label_text = ip_name_dict[logs[selected_log].filename]
        self.file_label.setText(label_text)
        self.time_label.setText(f"{str(selected_year)} {self.month_number_to_name(selected_month)}")


logs = {}
ip_name_dict = {}

class LogData:
    def __init__(self, filename):
        self.filename = filename
        self.years = {}

class Year:
    def __init__(self, year):
        self.year = year
        self.months = {
            1:Month(31),
            2:Month(29 if self.is_leap_year() else 28),
            3:Month(31),
            4:Month(30),
            5:Month(31),
            6:Month(30),
            7:Month(31),
            8:Month(31),
            9:Month(30),
            10:Month(31),
            11:Month(30),
            12:Month(31)
        }

    def is_leap_year(self):
        return self.year % 4 == 0 and (self.year % 100 != 0 or self.year % 400 == 0)

class Month:
    def __init__(self, days):
        self.amt_of_days = days
        self.days = {}
        self.image_data = None

    def create_month_image(self):
        data = np.zeros((24, self.amt_of_days, 4), dtype=np.uint8)
        for i in range(self.amt_of_days):
            for j in range(24):
                multiplier = -1
                if i in self.days and j in self.days[i].hours:
                    multiplier = self.score_hour(self.days[i].hours[j])
                if multiplier == -1:
                    data[j, i] = [0, 0, 0, 255]
                elif multiplier == 0:
                    data[j, i] = [0, 255, 0, 255]
                else:
                    data[j, i] = [multiplier * 2.55, 220 - (2.2 * multiplier), 0, 255]
        self.image_data = data


    @staticmethod
    def score_hour(hour):
        if hour.amount_of_data_points < 50:
            return -1
        if hour.average_packetloss_rate == 0 and hour.average_jitter < 1.0:
            return 0
        return min((hour.average_jitter / 12) * 100 + (hour.average_packetloss_rate / 0.05) * 100, 100)   # return min((hour.average_jitter / 20) * 100 + (hour.average_packetloss_rate / 0.1) * 100, 100)

class Day:
    def __init__(self):
        self.hours = {}

class Hour:
    def __init__(self, average_jitter, average_packetloss_rate, amount_of_data_points):
        self.average_jitter = average_jitter
        self.average_packetloss_rate = average_packetloss_rate
        self.amount_of_data_points = amount_of_data_points



def load_all_logs():
    for filename in os.listdir(os.getcwd()):
        if pattern.match(filename):
            filepath = os.path.join(directory, filename)
            load_log(filepath)

def load_log(filepath):
    #print(filepath)
    with open(filepath, 'r') as file:
        datetime_of_timestamp = None
        amount_of_data_points = 0
        accumulated_jitter = 0
        accumulated_packetloss = 0.0
        invalid_data_points = 0

        for line in file:
            parts = line.strip().split(';')
            if len(parts) == 5:
                try:
                    # parse out the values of this line
                    timestamp = float(parts[0])
                    average_ping = int(parts[1])
                    minimum_ping = int(parts[2])
                    maximum_ping = int(parts[3])
                    packetloss_rate = float(parts[4])

                    #Add the values to the data of the current hour
                    datetime_of_packet = datetime.fromtimestamp(timestamp)
                    if datetime_of_timestamp is None: # if this is the first line in this file
                        datetime_of_timestamp = datetime_of_packet
                    if not (datetime_of_timestamp.year == datetime_of_packet.year #  if we are starting a new hour then send the accumulated data away, reset the hour stats and start a new one
                        and datetime_of_timestamp.month == datetime_of_packet.month
                        and datetime_of_timestamp.day == datetime_of_packet.day
                        and datetime_of_timestamp.hour == datetime_of_packet.hour):

                        average_packetloss_rate = accumulated_packetloss / amount_of_data_points
                        average_jitter = accumulated_jitter / (amount_of_data_points - invalid_data_points)
                        add_processed_hour(filepath, datetime_of_timestamp, average_jitter, average_packetloss_rate, amount_of_data_points)
                        amount_of_data_points = 0
                        accumulated_jitter = 0
                        accumulated_packetloss = 0.0
                        datetime_of_timestamp = datetime_of_packet
                        invalid_data_points = 0
                    # add the data of the current line
                    if average_ping != -1:
                        accumulated_jitter += (maximum_ping - minimum_ping)
                    else:
                        invalid_data_points += 1
                    amount_of_data_points += 1
                    accumulated_packetloss += packetloss_rate
                except ValueError:
                    continue

def add_processed_hour(filepath, datetime, average_jitter, average_packetloss_rate, amount_of_data_points):
    # add the stats of this hour to the tree of years, months, days
    #print(f"{datetime.year}:{datetime.month}:{datetime.day}:{datetime.hour}: [{amount_of_data_points}, {average_jitter}, {average_packetloss_rate}]")
    if filepath not in logs:
        logs[filepath] = LogData(filepath)
    if datetime.year not in logs[filepath].years:
        logs[filepath].years[datetime.year] = Year(datetime.year)
    if datetime.day not in logs[filepath].years[datetime.year].months[datetime.month].days:
        logs[filepath].years[datetime.year].months[datetime.month].days[datetime.day] = Day()
    logs[filepath].years[datetime.year].months[datetime.month].days[datetime.day].hours[datetime.hour] = Hour(average_jitter, average_packetloss_rate, amount_of_data_points)


def parse_servertxt_file(file_path):
    result_dict = {}
    try:
        with open(file_path, 'r') as file:
            for line in file:
                # Strip any leading/trailing whitespace (including newline characters)
                line = line.strip()

                # Split the line by the semicolon character
                parts = line.split(';')

                # Check if the line has at least two parts
                if len(parts) >= 2:
                    ip_part = parts[0]
                    name_part = parts[1]

                    # Replace dots in the IP part with underscores
                    processed_ip = ip_part.replace('.', '_') + '_log.txt'

                    # Add the processed IP and name to the dictionary
                    result_dict[processed_ip] = name_part
                else:
                    print(f"Skipping malformed line: {line}")

    except FileNotFoundError:
        print(f"File not found: {file_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

    return result_dict



if __name__ == '__main__':
    load_all_logs()
    ip_name_dict = parse_servertxt_file('servers.txt')
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
